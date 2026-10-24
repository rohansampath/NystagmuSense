import Foundation

struct GazeSample: Codable {
    let timestamp: TimeInterval
    let x: Float?
    let y: Float?
    let z: Float?
    let faceTracked: Bool
    let valid: Bool
    let blinkLeft: Float?
    let blinkRight: Float?
}

struct GazeRecording: Encodable {
    let schemaVersion = 1
    let source = "ARKit ARFaceAnchor.lookAtPoint (real device estimates)"
    let units = "meters"
    let coordinateReference = "Face-local: +x viewer right (subject left), +y up, +z outward. Not screen position or visual angle."
    let timestampReference = "Native ARFrame.timestamp seconds; plot elapsed from first recorded frame."
    let validityDefinition = "Face is tracked and lookAtPoint is finite. Blinks are exported, not rejected; no eye-confidence score is available."
    let deviceModel: String
    let systemVersion: String
    let beginTime: Date
    var endTime: Date?
    let requestedDuration: TimeInterval = 10
    var stopReason: String?
    // UI lifecycle markers use system uptime; these are not measured display presentation times.
    let stimulusVisibleUptime: TimeInterval
    var stimulusHiddenUptime: TimeInterval?
    var recordingStartUptime: TimeInterval?
    var recordingEndUptime: TimeInterval?
    let stimulus = "Existing rightward bars: 90 SwiftUI points/s, width 0.02 of view, pitch 2.4 widths; background fades white to black over 30 s."
    var samples: [GazeSample] = []
}
