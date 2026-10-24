//
//  SessionMetadata.swift
//  NystagmuSense
//
//  JSON sidecar written next to each session CSV.
//

import Foundation
import UIKit

struct DeviceInfo: Codable, Equatable {
    let model: String          // hardware identifier, e.g. "iPhone15,2"
    let systemName: String
    let systemVersion: String
    let appVersion: String

    @MainActor
    static func current() -> DeviceInfo {
        DeviceInfo(model: hardwareIdentifier(),
                   systemName: UIDevice.current.systemName,
                   systemVersion: UIDevice.current.systemVersion,
                   appVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown")
    }

    private static func hardwareIdentifier() -> String {
        if let sim = ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] { return sim }
        var info = utsname()
        uname(&info)
        return withUnsafeBytes(of: &info.machine) { raw in
            String(decoding: raw.prefix { $0 != 0 }, as: UTF8.self)
        }
    }
}

struct SessionMetadata: Codable, Equatable {
    var schemaVersion = 1
    let sessionID: UUID
    let startedAt: Date
    let device: DeviceInfo
    let plannedDurationSeconds: Double
    let recordedSpanSeconds: Double
    let sampleCount: Int
    let trackedSampleCount: Int
    let droppedOutsideWindowCount: Int
    let observedSampleRateHz: Double?
    let stimulus: StimulusConfig
    let issues: [String]
    var gazeSource = "ARKit ARFaceTrackingConfiguration (TrueDepth)"
    var columns = SessionMetadata.columnDescriptions
    var timingNotes = """
        t_s = ARFrame.timestamp - session start, both on the system-uptime clock. \
        Session start is when the first camera frame was received; the stimulus animation \
        uses the same reference. stim_* columns are the stimulus state scheduled for t_s, \
        not a confirmed displayed frame: display latency and camera exposure/processing \
        latency (typically tens of ms) are not compensated.
        """

    static let columnDescriptions: [String: String] = [
        "t_s": "seconds since session start (monotonic)",
        "host_time_s": "ARFrame.timestamp, system uptime clock, seconds",
        "tracked": "1 if ARFaceAnchor.isTracked for this frame, else 0; gaze fields empty when 0",
        "lookat_x_m": "ARFaceAnchor.lookAtPoint, face-anchor coordinates, metres (+x = subject's left)",
        "lookat_y_m": "ARFaceAnchor.lookAtPoint, face-anchor coordinates, metres (+y = up)",
        "lookat_z_m": "ARFaceAnchor.lookAtPoint, face-anchor coordinates, metres (+z = out of face)",
        "left_dir_x": "unit z-axis of leftEyeTransform, face-anchor coordinates, unitless",
        "left_dir_y": "unit z-axis of leftEyeTransform, face-anchor coordinates, unitless",
        "left_dir_z": "unit z-axis of leftEyeTransform, face-anchor coordinates, unitless",
        "right_dir_x": "unit z-axis of rightEyeTransform, face-anchor coordinates, unitless",
        "right_dir_y": "unit z-axis of rightEyeTransform, face-anchor coordinates, unitless",
        "right_dir_z": "unit z-axis of rightEyeTransform, face-anchor coordinates, unitless",
        "stim_bg_gray": "scheduled background grey level, sRGB code value 0 (black)..1 (white); not photometric luminance",
        "stim_displacement_pt": "scheduled cumulative stripe displacement, SwiftUI points (+ = rightward on screen)",
    ]

    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }()
}
