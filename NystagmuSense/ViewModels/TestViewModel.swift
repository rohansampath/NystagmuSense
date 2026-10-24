import ARKit
import AVFoundation
import Combine
import UIKit
import SwiftUI
import Darwin

@MainActor
final class TestViewModel: ObservableObject {
    @Published var shadeLevel: Double = 0
    @Published var running = false
    @Published var status = "Preparing camera…"
    @Published var sampleCount = 0
    @Published var exportURL: URL?
    @Published var finished = false
    @Published var exportFailed = false

    private let eyeSession = EyeTrackingSession()
    private var recording: GazeRecording?
    private var deadline: Task<Void, Never>?
    private var firstTimestamp: TimeInterval?
    private var started = false

    func start() async {
        guard !started else { return }
        started = true
        let stimulusVisibleUptime = ProcessInfo.processInfo.systemUptime
        guard ARFaceTrackingConfiguration.isSupported else {
            status = "Face tracking is unsupported on this device. Use a supported physical iPhone."
            finished = true
            return
        }
        let allowed: Bool
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: allowed = true
        case .notDetermined: allowed = await AVCaptureDevice.requestAccess(for: .video)
        default: allowed = false
        }
        guard !Task.isCancelled, !finished else { return }
        guard allowed else {
            status = "Camera access denied. Enable Camera in Settings for NystagmuSense, then start a new test."
            finished = true
            return
        }
        recording = GazeRecording(deviceModel: Self.hardwareModel(),
                                  systemVersion: UIDevice.current.systemVersion,
                                  beginTime: .now,
                                  stimulusVisibleUptime: stimulusVisibleUptime)
        running = true
        status = "Waiting for camera frames…"
        eyeSession.onSample = { [weak self] in self?.ingest($0) }
        eyeSession.onFailure = { [weak self] in self?.finish(reason: $0) }
        eyeSession.start()
        // Do not wait forever if ARKit starts but never produces frames.
        scheduleStop(after: 15, reason: "No camera frames received within 15 seconds.")
    }

    private func scheduleStop(after seconds: Double, reason: String) {
        deadline?.cancel()
        deadline = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(seconds)) }
            catch { return }
            self?.finish(reason: reason)
        }
    }

    private func ingest(_ sample: GazeSample) {
        guard running, sample.timestamp.isFinite else { return }
        if firstTimestamp == nil {
            firstTimestamp = sample.timestamp
            recording?.recordingStartUptime = ProcessInfo.processInfo.systemUptime
            scheduleStop(after: 10, reason: "Completed ten-second recording.")
        }
        guard let firstTimestamp else { return }
        if sample.timestamp - firstTimestamp >= 10 {
            finish(reason: "Completed ten-second recording.")
            return
        }
        guard sample.timestamp >= (recording?.samples.last?.timestamp ?? firstTimestamp) else { return }
        recording?.samples.append(sample)
        if sample.valid { sampleCount += 1 }
        status = "Recording 10 seconds · \(sampleCount) valid estimates"
    }

    func finish(reason: String = "Cancelled; recording is partial.") {
        guard !finished else { return }
        finished = true
        running = false
        deadline?.cancel()
        deadline = nil
        eyeSession.stop()
        guard var recording else {
            status = reason
            return
        }
        recording.endTime = .now
        recording.recordingEndUptime = ProcessInfo.processInfo.systemUptime
        recording.stimulusHiddenUptime = recording.recordingEndUptime
        recording.stopReason = reason
        self.recording = recording
        status = "\(reason) \(sampleCount) valid estimates / \(recording.samples.count) frames."
        if sampleCount == 0 {
            status += " No usable gaze captured. Check face position, lighting, and device support."
        }
        export()
    }

    func export() {
        guard let recording, finished else { return }
        do {
            let folder = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask,
                                                     appropriateFor: nil, create: true)
                .appendingPathComponent("GazeRecordings", isDirectory: true)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let url = folder.appendingPathComponent("gaze-\(UUID().uuidString).json")
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(recording).write(to: url, options: .atomic)
            exportURL = url
            exportFailed = false
        } catch {
            exportFailed = true
            status += " Export failed: \(error.localizedDescription). Use Retry Export."
        }
    }

    private static func hardwareModel() -> String {
        var info = utsname()
        uname(&info)
        return withUnsafeBytes(of: &info.machine) { bytes in
            String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self)
        }
    }
}
