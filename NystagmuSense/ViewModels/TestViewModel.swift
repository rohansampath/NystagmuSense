//
//  TestViewModel.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//  Lightweight session coordinator:
//  start gaze provider → first frame starts clock + stimulus → record for
//  `duration` → stop → export CSV/JSON → report outcome.
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
        case starting                       // provider started, waiting for first frame
        case recording
        case finished(RecordingSummary)
        case failed(String)
        case cancelled
    }

    @Published private(set) var phase: Phase = .idle
    /// Stimulus onset on the system-uptime clock; nil until the first camera frame.
    @Published private(set) var stimulusStartTime: TimeInterval?
    @Published private(set) var faceTracked = false

    let stimulus: StimulusEngine
    let duration: TimeInterval

    private let provider: GazeProvider
    private let startupTimeout: TimeInterval
    private let outputDirectory: URL
    private let now: () -> TimeInterval
    private var recorder: SessionRecorder?
    private var timer: Task<Void, Never>?

    init(provider: GazeProvider = ARKitGazeProvider(),
         stimulus: StimulusEngine = StimulusEngine(),
         duration: TimeInterval = 10,
         startupTimeout: TimeInterval = 5,
         outputDirectory: URL = SessionRecorder.defaultDirectory,
         now: @escaping () -> TimeInterval = CACurrentMediaTime) {
        self.provider        = provider
        self.stimulus        = stimulus
        self.duration        = duration
        self.startupTimeout  = startupTimeout
        self.outputDirectory = outputDirectory
        self.now             = now
    }

    // MARK: - Lifecycle

    /// Safe to call repeatedly (e.g. from `onAppear`); only the first call starts a session.
    func start() {
        guard phase == .idle else { return }
        guard provider.isSupported else { fail(.unsupportedDevice); return }

        // ARKitGazeProvider delivers callbacks on the main thread.
        provider.onSample = { [weak self] s in MainActor.assumeIsolated { self?.ingest(s) } }
        provider.onError  = { [weak self] e in MainActor.assumeIsolated { self?.handle(e) } }

        phase = .starting
        provider.start()                    // may report an error synchronously
        if phase == .starting {
            schedule(after: startupTimeout) { [weak self] in
                if self?.phase == .starting { self?.fail(.noFramesReceived) }
            }
        }
    }

    /// Stops tracking and exports. Idempotent: only the first call while recording has any effect.
    func finish() {
        guard phase == .recording, let recorder else { return }
        stopCapture()

        guard !recorder.samples.isEmpty else {
            phase = .failed(RecordingError.noSamples.localizedDescription)
            return
        }
        do {
            let files = try recorder.export(to: outputDirectory, device: DeviceInfo.current())
            phase = .finished(RecordingSummary(files: files,
                                               sampleCount: recorder.samples.count,
                                               trackedCount: recorder.trackedCount,
                                               sampleRateHz: recorder.observedSampleRate,
                                               issues: recorder.issues))
        } catch {
            phase = .failed("Recording could not be saved: \(error.localizedDescription)")
        }
    }

    /// App left the foreground: camera capture can't continue honestly, so stop
    /// now. Data already recorded is saved and marked partial.
    func appBecameInactive() {
        switch phase {
        case .starting:
            stopCapture()
            phase = .failed("The app left the foreground before recording started.")
        case .recording:
            recorder?.note("App left the foreground; recording is partial.")
            finish()
        default:
            break
        }
    }

    /// Called when the user leaves early. Discards the partial recording.
    func cancel() {
        guard phase == .starting || phase == .recording else { return }
        stopCapture()
        phase = .cancelled
    }

    // MARK: - Provider events

    private func ingest(_ s: EyeMovementSample) {
        if phase == .starting { beginRecording() }
        guard phase == .recording else { return }
        recorder?.record(s)
        if faceTracked != s.isTracked { faceTracked = s.isTracked }
    }

    private func beginRecording() {
        let t0 = now()
        recorder          = SessionRecorder(startUptime: t0, duration: duration, stimulus: stimulus)
        stimulusStartTime = t0
        phase             = .recording
        schedule(after: duration) { [weak self] in self?.finish() }
    }

    private func handle(_ error: GazeTrackingError) {
        switch phase {
        case .starting:
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

    private func fail(_ error: GazeTrackingError) {
        stopCapture()
        phase = .failed(error.localizedDescription)
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
