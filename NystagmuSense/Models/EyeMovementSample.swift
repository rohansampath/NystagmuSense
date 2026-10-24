//
//  EyeMovementSample.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import Foundation
import simd

/// One raw eye-tracking measurement, exactly as reported by the gaze provider.
///
/// Coordinate system (ARKit provider): all vectors are expressed in the
/// face-anchor coordinate space (origin between the eyes, +x toward the
/// subject's left, +y up, +z out of the face toward the camera).
/// No calibration or angle conversion is applied.
struct EyeMovementSample: Codable, Equatable {
    /// Capture time on the system-uptime clock (seconds), e.g. `ARFrame.timestamp`.
    /// Convert to session-relative time with `SessionRecorder`.
    let timestamp: TimeInterval

    /// Whether the provider reported the face/eyes as tracked for this frame.
    /// When false, all measurements below are nil (no stale values are kept).
    let isTracked: Bool

    /// `ARFaceAnchor.lookAtPoint` — estimated gaze fixation point, metres.
    let lookAtPoint: SIMD3<Float>?

    /// Unit z-axis of `ARFaceAnchor.left/rightEyeTransform` — eye orientation
    /// direction vector (unitless). Sign convention not yet verified on device.
    let leftEyeDirection: SIMD3<Float>?
    let rightEyeDirection: SIMD3<Float>?

    /// `eyeBlinkLeft` / `eyeBlinkRight` blend-shape coefficients, 0 (open) … 1 (closed).
    /// Exported as-is; not used to reject samples.
    var blinkLeft: Float? = nil
    var blinkRight: Float? = nil

    static func untracked(at timestamp: TimeInterval) -> EyeMovementSample {
        EyeMovementSample(timestamp: timestamp, isTracked: false,
                          lookAtPoint: nil, leftEyeDirection: nil, rightEyeDirection: nil)
    }
}
