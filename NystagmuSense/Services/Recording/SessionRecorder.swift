//
//  SessionRecorder.swift
//  NystagmuSense
//
//  Accumulates raw gaze samples for one recording, tags each with the
//  scheduled stimulus state, and exports CSV + JSON sidecar.
//  Independent of ARKit, SwiftUI, Core Data and OKN detection.
//

import Foundation

/// One gaze sample on the session timeline. This is the input type for
/// future signal processing (see docs/ARCHITECTURE.md).
struct RecordedSample: Equatable {
    /// Seconds since session start (monotonic clock).
    let t: TimeInterval
    let gaze: EyeMovementSample
    /// Stimulus state *scheduled* for time `t` (not a confirmed displayed frame).
    let stimulus: StimulusSnapshot
}

struct RecordingFiles: Equatable {
    let directory: URL
    let csv: URL
    let metadata: URL
}

enum RecordingError: Error, Equatable, LocalizedError {
    case noSamples

    var errorDescription: String? { "No eye-tracking samples were recorded." }
}

struct SessionRecorder {
    let sessionID: UUID
    /// Session start on the system-uptime clock; also the stimulus onset.
    let startUptime: TimeInterval
    /// Wall-clock start, for humans only. Never used for timing.
    let startedAt: Date
    let duration: TimeInterval
    let stimulus: StimulusEngine

    private(set) var samples: [RecordedSample] = []
    private(set) var droppedOutsideWindow = 0
    private(set) var issues: [String] = []

    init(sessionID: UUID = UUID(), startUptime: TimeInterval, startedAt: Date = .now,
         duration: TimeInterval, stimulus: StimulusEngine) {
        self.sessionID   = sessionID
        self.startUptime = startUptime
        self.startedAt   = startedAt
        self.duration    = duration
        self.stimulus    = stimulus
    }

    /// Adds a sample if it falls inside [0, duration]. Returns whether it was kept.
    @discardableResult
    mutating func record(_ gaze: EyeMovementSample) -> Bool {
        let t = gaze.timestamp - startUptime
        guard t >= 0, t <= duration else { droppedOutsideWindow += 1; return false }
        samples.append(RecordedSample(t: t, gaze: gaze, stimulus: stimulus.snapshot(at: t)))
        return true
    }

    mutating func note(_ issue: String) { issues.append(issue) }

    // MARK: - Summary statistics

    var trackedCount: Int { samples.filter(\.gaze.isTracked).count }

    /// Time between first and last kept sample.
    var recordedSpan: TimeInterval {
        guard let first = samples.first, let last = samples.last else { return 0 }
        return last.t - first.t
    }

    /// Mean sampling rate over the recorded span (Hz); nil with < 2 samples.
    var observedSampleRate: Double? {
        guard samples.count >= 2, recordedSpan > 0 else { return nil }
        return Double(samples.count - 1) / recordedSpan
    }

    // MARK: - CSV

    static let csvColumns = [
        "t_s", "host_time_s", "tracked",
        "lookat_x_m", "lookat_y_m", "lookat_z_m",
        "left_dir_x", "left_dir_y", "left_dir_z",
        "right_dir_x", "right_dir_y", "right_dir_z",
        "blink_left", "blink_right",
        "stim_bg_gray", "stim_displacement_pt",
    ]

    func csv() -> String {
        var lines = [Self.csvColumns.joined(separator: ",")]
        lines.reserveCapacity(samples.count + 1)
        for s in samples {
            var fields = [String(format: "%.6f", s.t),
                          String(format: "%.6f", s.gaze.timestamp),
                          s.gaze.isTracked ? "1" : "0"]
            for v in [s.gaze.lookAtPoint, s.gaze.leftEyeDirection, s.gaze.rightEyeDirection] {
                // Empty fields = missing data (untracked frame), never zeros.
                fields += v.map { [$0.x, $0.y, $0.z].map { "\($0)" } } ?? ["", "", ""]
            }
            for b in [s.gaze.blinkLeft, s.gaze.blinkRight] {
                fields.append(b.map { "\($0)" } ?? "")
            }
            fields.append(String(format: "%.6f", s.stimulus.backgroundGray))
            fields.append(String(format: "%.3f", s.stimulus.displacementPoints))
            lines.append(fields.joined(separator: ","))
        }
        return lines.joined(separator: "\n") + "\n"
    }

    // MARK: - Export

    func metadata(device: DeviceInfo) -> SessionMetadata {
        SessionMetadata(
            sessionID: sessionID,
            startedAt: startedAt,
            device: device,
            plannedDurationSeconds: duration,
            recordedSpanSeconds: recordedSpan,
            sampleCount: samples.count,
            trackedSampleCount: trackedCount,
            droppedOutsideWindowCount: droppedOutsideWindow,
            observedSampleRateHz: observedSampleRate,
            stimulus: stimulus.config,
            issues: issues
        )
    }

    /// Writes `<stem>.csv` and `<stem>.json` into a new folder under `baseDirectory`.
    func export(to baseDirectory: URL, device: DeviceInfo) throws -> RecordingFiles {
        guard !samples.isEmpty else { throw RecordingError.noSamples }

        let stem = Self.fileStem(startedAt: startedAt, sessionID: sessionID)
        let dir  = baseDirectory.appendingPathComponent(stem, isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        let csvURL  = dir.appendingPathComponent("\(stem).csv")
        let jsonURL = dir.appendingPathComponent("\(stem).json")
        try Data(csv().utf8).write(to: csvURL, options: .atomic)
        try SessionMetadata.encoder.encode(metadata(device: device)).write(to: jsonURL, options: .atomic)
        return RecordingFiles(directory: dir, csv: csvURL, metadata: jsonURL)
    }

    static func fileStem(startedAt: Date, sessionID: UUID) -> String {
        let f = DateFormatter()
        f.locale     = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyyMMdd-HHmmss"
        return "NS_\(f.string(from: startedAt))_\(sessionID.uuidString.prefix(8))"
    }

    /// Documents/Recordings — visible in the Files app (UIFileSharingEnabled).
    static var defaultDirectory: URL {
        URL.documentsDirectory.appendingPathComponent("Recordings", isDirectory: true)
    }
}
