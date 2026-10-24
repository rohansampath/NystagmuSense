//
//  EyeMovementDetector.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//  LEGACY / UNVALIDATED — not used by the recording path.
//  Pure functions only: no SwiftUI, ARKit or Core Data.
//
//  Previously this differentiated the eye *position* (eye transform column 3),
//  which does not measure rotation. It now uses the eye direction vector,
//  but the resulting angle is uncalibrated eye-in-head yaw from ARKit's model.
//
import simd
struct EyeMovementDetector {
    /// Horizontal yaw of the left-eye direction vector, degrees (uncalibrated).
    static func leftEyeYawDegrees(_ s: EyeMovementSample) -> Float? {
        guard let d = s.leftEyeDirection else { return nil }
        return atan2f(d.x, d.z) * 180 / .pi
    }

    /// Finite-difference yaw velocity between two samples, °/s (uncalibrated).
    static func velocityDegPerSec(from a: EyeMovementSample,
                                  to b: EyeMovementSample) -> Float? {
        let dt = Float(b.timestamp - a.timestamp)
        guard dt > 0, let yawA = leftEyeYawDegrees(a), let yawB = leftEyeYawDegrees(b)
        else { return nil }
        return remainderf(yawB - yawA, 360) / dt
    }
}
