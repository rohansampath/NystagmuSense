//
//  TestViewModel.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//  Lightweight session coordinator:
//  optional positioning (camera on, face-distance gate) → arm → first tracked
//  frame starts clock + stimulus → record for
//  `duration` → stop → export CSV/JSON → report outcome → upload to the Mac
//  (optional; see Services/Transfer). The local files are always kept.
//
//  OKN detection and scoring are intentionally NOT part of this path
//  (see Services/Analysis and docs/ARCHITECTURE.md).
//

import QuartzCore
import SwiftUI

@MainActor
final class TestViewModel: ObservableObject {
    struct RecordingSummary: Equatable {
        let files: RecordingFiles
        let sampleCount: Int
        let trackedCount: Int
        let sampleRateHz: Double?
        let issues: [String]
    }

    enum Phase: Equatable {
        case idle
        case positioning                    // camera on, showing face distance; not armed
        case starting                       // armed, waiting for the first tracked frame
        case recording
        case finished(RecordingSummary)
        case failed(String)
        case cancelled
    }

    /// Mac transfer of a saved recording. Only ever set after a local export succeeded.
    enum UploadStatus: Equatable {
        case notConfigured                  // saved locally; no Mac set up
        case uploading
        case uploaded                       // the Mac confirmed both files were written
        case failed(String)                 // still saved locally; can retry
    }

    @Published private(set) var phase: Phase = .idle
    /// Stimulus onset on the system-uptime clock; nil until the first tracked camera frame.
    @Published private(set) var stimulusStartTime: TimeInterval?
    @Published private(set) var faceTracked = false
    /// Face-tracked samples kept so far in this session (live progress).
    @Published private(set) var trackedCount = 0
    /// True after a failed export; samples stay in memory for `retryExport()`.
    @Published private(set) var canRetryExport = false
    @Published private(set) var viewport: StimulusViewport?
    /// nil until a recording has been saved locally.
    @Published private(set) var upload: UploadStatus?
    /// The in-flight upload, exposed so tests can await it.
    private(set) var uploadTask: Task<Void, Never>?
    /// Pre-trial face-distance readout (`.positioning` only).
    @Published private(set) var positioning: DistanceGate.Status = .noFace

    var isLandscape: Bool { viewport?.isLandscape == true }

    let stimulus: StimulusEngine
    let duration: TimeInterval
    /// Test type and participant, fixed when this trial screen was created
    /// (before recording); the saved name and metadata use exactly these.
    let selection: TrialSelection

    private let provider: GazeProvider
    private let startupTimeout: TimeInterval
    private let outputDirectory: URL
    private let makeUploader: () -> RecordingUploading?
    private let experiment: ExperimentLog
    private let now: () -> TimeInterval
    private var recorder: SessionRecorder?
    private var timer: Task<Void, Never>?
    /// Whether any camera frame (tracked or not) has arrived since the camera started.
    private var framesSeen = false
    private var gate = DistanceGate()
    private var distanceCheck: FaceDistanceSummary.Check = .notPerformed

    init(provider: GazeProvider = ARKitGazeProvider(),
         stimulus: StimulusEngine = StimulusEngine(),
         duration: TimeInterval = 10,
         startupTimeout: TimeInterval = 5,
         outputDirectory: URL = SessionRecorder.defaultDirectory,
         uploader: @escaping () -> RecordingUploading? = RecordingUploader.fromSavedSettings,
         experiment: ExperimentLog = ExperimentLog(),
         selection: TrialSelection? = nil,
         now: @escaping () -> TimeInterval = CACurrentMediaTime) {
        self.provider        = provider
        self.stimulus        = stimulus
        self.duration        = duration
        self.startupTimeout  = startupTimeout
        self.outputDirectory = outputDirectory
        self.makeUploader    = uploader
        self.experiment      = experiment
        self.selection       = selection ?? experiment.selection
        self.now             = now
    }

    // MARK: - Lifecycle

    /// Turns the camera on and shows the face distance before a trial. Uses the
    /// same provider/ARSession that then records.
    func startPositioning() {
        guard phase == .idle, isLandscape, selectionIsComplete() else { return }
        startCamera(as: .positioning)
    }

    /// Arms the recording: the next tracked frame starts the clock and stimulus.
    /// From `.positioning` this needs the distance gate to be ready, unless
    /// `bypassDistanceCheck` (recorded as such in the sidecar). From `.idle` it
    /// starts the camera directly (no positioning; recorded as notPerformed).
    /// Safe to call repeatedly; only the first effective call arms.
    func start(bypassDistanceCheck: Bool = false) {
        switch phase {
        case .idle:
            guard isLandscape, selectionIsComplete() else { return }
            distanceCheck = .notPerformed
            startCamera(as: .starting)
        case .positioning:
            guard bypassDistanceCheck || gate.status.isReady else { return }
            distanceCheck = bypassDistanceCheck ? .bypassed : .passed
            phase = .starting
            // The camera is already running; keep the no-frames timeout until it is.
            if framesSeen { scheduleNoTrackedFaceTimeout() }
        default:
            break
        }
    }

    private func startCamera(as next: Phase) {
        guard provider.isSupported else { fail(.unsupportedDevice); return }

        // ARKitGazeProvider delivers callbacks on the main thread.
        provider.onSample = { [weak self] s in MainActor.assumeIsolated { self?.ingest(s) } }
        provider.onError  = { [weak self] e in MainActor.assumeIsolated { self?.handle(e) } }

        phase = next
        framesSeen = false
        gate = DistanceGate()
        positioning = gate.status
        provider.start()                    // may report an error synchronously
        if phase == next { scheduleNoFramesTimeout() }
    }

    /// Clears a failed session (other than a failed export, which keeps its
    /// samples for `retryExport()`) so the user can start again in place.
    func tryAgain() {
        guard canTryAgain else { return }
        resetToIdle()
    }

    var canTryAgain: Bool {
        if case .failed = phase { return !canRetryExport }
        return false
    }

    /// A change of surface size invalidates the original stimulus geometry.
    /// Stop rather than mixing portrait and landscape samples in one trial.
    func updateViewport(width: Double, height: Double) {
        let next = StimulusViewport(widthPoints: width, heightPoints: height)
        guard viewport != next else { return }
        viewport = next
        switch phase {
        case .starting where !next.isLandscape, .positioning where !next.isLandscape:
            stopCapture()
            resetToIdle()
        case .recording:
            recorder?.note("Stimulus surface changed size or orientation; recording is partial.")
            finish()
        default:
            break
        }
    }

    /// Stops tracking and exports. Idempotent: only the first call while recording has any effect.
    func finish() {
        guard phase == .recording, recorder != nil else { return }
        stopCapture()

        guard recorder?.samples.isEmpty == false else {
            phase = .failed(RecordingError.noSamples.localizedDescription)
            return
        }
        // Named once; Retry Export reuses the name. The counter advances only
        // when the files are saved locally (export), not on upload.
        if recorder?.name == nil, let startedAt = recorder?.startedAt {
            recorder?.name = RecordingName(experimentID: selection.testType.code,
                                           participantID: selection.participant?.rawValue,
                                           trialNumber: experiment.nextTrialNumber,
                                           stimulus: stimulus.config, startedAt: startedAt)
        }
        if let recorder { export(recorder) }
    }

    /// Re-attempts a failed export of the samples still held in memory.
    func retryExport() {
        guard canRetryExport, let recorder else { return }
        export(recorder)
    }

    /// Re-sends a recording whose upload failed. The local files are unchanged.
    func retryUpload() {
        guard case .failed = upload, case .finished(let summary) = phase else { return }
        startUpload(summary.files)
    }

    /// Reacts to the app's scene phase.
    /// - While recording, any loss of the active state (Control Center, a call,
    ///   backgrounding) stops capture; data so far is saved and marked partial.
    /// - While starting, `.inactive` is expected: ARKit's camera-permission alert
    ///   causes it. The no-frames timeout is paused until the app is active
    ///   again. Only `.background` abandons the start, returning to readiness.
    func scenePhaseChanged(_ scene: ScenePhase) {
        switch (scene, phase) {
        case (.inactive, .recording), (.background, .recording):
            recorder?.note("App left the foreground; recording is partial.")
            finish()
        case (.background, .starting), (.background, .positioning):
            stopCapture()
            resetToIdle()
        case (.inactive, .starting) where !framesSeen, (.inactive, .positioning) where !framesSeen:
            timer?.cancel()
            timer = nil
        case (.active, .starting) where !framesSeen, (.active, .positioning) where !framesSeen:
            scheduleNoFramesTimeout()
        default:
            break
        }
    }

    /// Called when the user leaves early. Discards the partial recording.
    func cancel() {
        guard phase == .positioning || phase == .starting || phase == .recording else { return }
        stopCapture()
        phase = .cancelled
    }

    // MARK: - Provider events

    private func ingest(_ s: EyeMovementSample) {
        if phase == .positioning {
            if !framesSeen {
                // The camera works. Positioning waits for the user, so no face timeout.
                framesSeen = true
                timer?.cancel()
                timer = nil
            }
            gate.update(distanceCm: s.isTracked ? s.faceDistanceMeters.map { Double($0) * 100 } : nil,
                        at: s.timestamp)
            if positioning != gate.status { positioning = gate.status }
            if faceTracked != s.isTracked { faceTracked = s.isTracked }
            return
        }
        if phase == .starting, !framesSeen {
            // The camera is running; now give the user time to be found.
            framesSeen = true
            scheduleNoTrackedFaceTimeout()
        }
        if phase == .starting, s.isTracked { beginRecording() }
        guard phase == .recording else { return }
        if recorder?.record(s) == true, s.isTracked { trackedCount += 1 }
        if faceTracked != s.isTracked { faceTracked = s.isTracked }
    }

    private func export(_ recorder: SessionRecorder) {
        do {
            let files = try recorder.export(to: outputDirectory, device: DeviceInfo.current())
            if let trial = recorder.name?.trialNumber { experiment.commitTrialNumber(trial) }
            canRetryExport = false
            phase = .finished(RecordingSummary(files: files,
                                               sampleCount: recorder.samples.count,
                                               trackedCount: recorder.trackedCount,
                                               sampleRateHz: recorder.observedSampleRate,
                                               issues: recorder.issues))
            startUpload(files)
        } catch {
            canRetryExport = true
            phase = .failed("Recording could not be saved: \(error.localizedDescription)")
        }
    }

    /// Runs after capture has stopped and both files are on disk, so it can't
    /// affect tracking or stimulus timing. Network I/O happens off the main actor.
    private func startUpload(_ files: RecordingFiles) {
        guard let uploader = makeUploader() else { upload = .notConfigured; return }
        upload = .uploading
        uploadTask = Task { [weak self] in
            do {
                try await uploader.upload(files)
                self?.upload = .uploaded
            } catch {
                self?.upload = .failed(error.localizedDescription)
            }
        }
    }

    private func beginRecording() {
        let t0 = now()
        recorder          = SessionRecorder(startUptime: t0, duration: duration, stimulus: stimulus,
                                            viewport: viewport)
        recorder?.distanceCheck = distanceCheck
        stimulusStartTime = t0
        phase             = .recording
        schedule(after: duration) { [weak self] in self?.finish() }
    }

    private func handle(_ error: GazeTrackingError) {
        switch phase {
        case .starting, .positioning:
            fail(error)
        case .recording:
            // Keep what was captured; the gap/failure is recorded in the sidecar.
            recorder?.note(error.localizedDescription)
            if error != .interrupted { finish() }
        default:
            break
        }
    }

    // MARK: - Helpers

    /// A pilot trial without a participant is never recorded, so it can't
    /// be saved or uploaded under an incomplete name.
    private func selectionIsComplete() -> Bool {
        guard selection.isComplete else {
            phase = .failed("Choose the participant on the menu before recording a \(selection.testType.displayName) trial.")
            return false
        }
        return true
    }

    private func fail(_ error: GazeTrackingError) {
        stopCapture()
        phase = .failed(error.localizedDescription)
    }

    private func scheduleNoFramesTimeout() {
        schedule(after: startupTimeout) { [weak self] in
            if self?.phase == .starting || self?.phase == .positioning { self?.fail(.noFramesReceived) }
        }
    }

    private func scheduleNoTrackedFaceTimeout() {
        schedule(after: startupTimeout) { [weak self] in
            if self?.phase == .starting { self?.fail(.noTrackedFace) }
        }
    }

    private func resetToIdle() {
        recorder          = nil
        stimulusStartTime = nil
        faceTracked       = false
        trackedCount      = 0
        framesSeen        = false
        gate              = DistanceGate()
        positioning       = gate.status
        distanceCheck     = .notPerformed
        phase             = .idle
    }

    private func stopCapture() {
        timer?.cancel()
        timer = nil
        provider.stop()
    }

    private func schedule(after seconds: TimeInterval, _ action: @escaping @MainActor () -> Void) {
        timer?.cancel()
        timer = Task { @MainActor in
            try? await Task.sleep(for: .seconds(seconds))
            guard !Task.isCancelled else { return }
            action()
        }
    }
}
