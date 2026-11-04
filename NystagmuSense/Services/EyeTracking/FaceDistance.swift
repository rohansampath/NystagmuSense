//
//  FaceDistance.swift
//  NystagmuSense
//
//  Approximate camera-to-eyes distance from ARKit poses, the pre-trial
//  positioning gate, and the per-recording summary. Pure maths, no ARKit, so
//  it is testable with synthetic transforms.
//
//  This is ARKit's estimate of the distance from the FRONT CAMERA to the
//  midpoint between the eyes. It is uncalibrated and is not the
//  eye-to-screen-centre distance (the camera sits at the screen edge).
//

import Foundation
import simd

enum FaceDistance {
    /// Metres, or nil if the poses are unusable. All four transforms come from
    /// one ARFrame: camera and face in world coordinates, eyes relative to the face.
    static func meters(camera: simd_float4x4, face: simd_float4x4,
                       leftEye: simd_float4x4, rightEye: simd_float4x4) -> Float? {
        let l = face * leftEye.columns.3
        let r = face * rightEye.columns.3
        let mid = (SIMD3(l.x, l.y, l.z) + SIMD3(r.x, r.y, r.z)) / 2
        let cam = SIMD3(camera.columns.3.x, camera.columns.3.y, camera.columns.3.z)
        let d = simd_distance(mid, cam)
        return d.isFinite && d > 0 ? d : nil
    }
}

/// Pre-trial check: the smoothed distance must stay in range for `holdSeconds`.
/// Preliminary experimental range, not a clinically validated requirement.
struct DistanceGate {
    static let recommendedCm: ClosedRange<Double> = 30...40
    static let holdSeconds: TimeInterval = 1
    /// Weight of each new frame in the moving average (~80 ms at 60 Hz), so
    /// the readout doesn't flicker.
    static let smoothing = 0.2

    enum Status: Equatable {
        case noFace
        case tooClose(Int)
        case tooFar(Int)
        case holding(Int)       // in range, not yet for holdSeconds
        case ready(Int)

        var isReady: Bool { if case .ready = self { return true } else { return false } }

        var message: String {
            switch self {
            case .noFace:            return "No face detected"
            case .tooClose(let cm):  return "Move farther away (\(cm) cm)"
            case .tooFar(let cm):    return "Move closer (\(cm) cm)"
            case .holding(let cm):   return "Good positioning — \(cm) cm"
            case .ready(let cm):     return "Ready to record — \(cm) cm"
            }
        }
    }

    private(set) var smoothedCm: Double?
    private var inRangeSince: TimeInterval?
    private var lastTime: TimeInterval = 0

    /// Tracking loss (nil) clears the average and restarts the hold.
    mutating func update(distanceCm: Double?, at t: TimeInterval) {
        lastTime = t
        guard let d = distanceCm, d.isFinite, d > 0 else {
            smoothedCm = nil
            inRangeSince = nil
            return
        }
        let s = smoothedCm.map { $0 + Self.smoothing * (d - $0) } ?? d
        smoothedCm = s
        if Self.recommendedCm.contains(s) {
            if inRangeSince == nil { inRangeSince = t }
        } else {
            inRangeSince = nil
        }
    }

    var status: Status {
        guard let s = smoothedCm else { return .noFace }
        let cm = Int(s.rounded())
        if s < Self.recommendedCm.lowerBound { return .tooClose(cm) }
        if s > Self.recommendedCm.upperBound { return .tooFar(cm) }
        if let since = inRangeSince, lastTime - since >= Self.holdSeconds { return .ready(cm) }
        return .holding(cm)
    }
}

/// Face-distance record for one recording (sidecar `faceDistance`, schema 4).
/// Recording is never stopped for being out of range; the deviation is recorded.
struct FaceDistanceSummary: Codable, Equatable {
    enum Check: String, Codable {
        case passed         // Start was enabled by DistanceGate
        case bypassed       // "Start without distance check"
        case notPerformed   // started without the positioning step
    }

    let check: Check
    let recommendedRangeCm: [Double]
    /// First recorded sample that has a distance.
    let atStartCm: Double?
    let medianCm: Double?
    let minCm: Double?
    let maxCm: Double?
    let samplesWithDistance: Int
    let sampleCount: Int
    /// Fraction of samples with a distance that fall outside the range.
    let fractionOutsideRange: Double?
    var definition = "ARKit estimate of the distance from the front camera to the midpoint between "
        + "the eyes, raw per frame (not smoothed), cm. Uncalibrated; not the eye-to-screen-centre distance."

    init(distancesCm: [Double?], check: Check) {
        let valid = distancesCm.compactMap { $0 }.filter(\.isFinite)
        let sorted = valid.sorted()
        let range = DistanceGate.recommendedCm
        self.check = check
        recommendedRangeCm = [range.lowerBound, range.upperBound]
        atStartCm = valid.first
        minCm = sorted.first
        maxCm = sorted.last
        if sorted.isEmpty {
            medianCm = nil
        } else {
            let m = sorted.count / 2
            medianCm = sorted.count % 2 == 1 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2
        }
        samplesWithDistance = valid.count
        sampleCount = distancesCm.count
        fractionOutsideRange = valid.isEmpty ? nil
            : Double(valid.filter { !range.contains($0) }.count) / Double(valid.count)
    }
}
