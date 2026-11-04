//
//  FaceDistanceTests.swift
//  NystagmuSenseTests
//
//  Distance maths on synthetic ARKit-style transforms, the positioning gate,
//  and the per-recording summary. No camera involved.
//

import Foundation
import simd
import Testing
@testable import NystagmuSense

struct FaceDistanceTests {
    func translation(_ x: Float, _ y: Float, _ z: Float) -> simd_float4x4 {
        var m = matrix_identity_float4x4
        m.columns.3 = SIMD4(x, y, z, 1)
        return m
    }

    /// Face 35 cm in front of a camera at the origin; eyes ±3.2 cm, 2 cm forward of the face origin.
    @Test func distanceIsCameraToEyeMidpoint() throws {
        let d = try #require(FaceDistance.meters(camera: matrix_identity_float4x4,
                                                 face: translation(0, 0, -0.37),
                                                 leftEye: translation(0.032, 0.03, 0.02),
                                                 rightEye: translation(-0.032, 0.03, 0.02)))
        // midpoint = (0, 0.03, -0.35) → √(0.03² + 0.35²)
        let expected: Float = (0.03 * 0.03 + 0.35 * 0.35 as Float).squareRoot()
        #expect(abs(d - expected) < 1e-5)
    }

    @Test func distanceUsesTheSameWorldFrameForCameraAndFace() throws {
        // Moving camera and face together by the same offset changes nothing.
        let shift: Float = 0.5
        let d = try #require(FaceDistance.meters(camera: translation(shift, 0, 0),
                                                 face: translation(shift, 0, -0.35),
                                                 leftEye: translation(0.03, 0, 0),
                                                 rightEye: translation(-0.03, 0, 0)))
        #expect(abs(d - 0.35) < 1e-5)
        // A rotated face still places its eyes in world coordinates via face * eye.
        let rotated = simd_float4x4(simd_quatf(angle: .pi / 2, axis: [0, 1, 0]))
        var face = rotated
        face.columns.3 = SIMD4(0, 0, -0.35, 1)
        let r = try #require(FaceDistance.meters(camera: matrix_identity_float4x4, face: face,
                                                 leftEye: translation(0.03, 0, 0), rightEye: translation(-0.03, 0, 0)))
        #expect(abs(r - 0.35) < 1e-5)
    }

    @Test func unusablePosesGiveNoDistance() {
        let nan = translation(.nan, 0, 0)
        #expect(FaceDistance.meters(camera: matrix_identity_float4x4, face: nan,
                                    leftEye: translation(0, 0, 0), rightEye: translation(0, 0, 0)) == nil)
        #expect(FaceDistance.meters(camera: matrix_identity_float4x4, face: matrix_identity_float4x4,
                                    leftEye: matrix_identity_float4x4, rightEye: matrix_identity_float4x4) == nil)
    }

    // MARK: - Gate

    /// Feeds `cm` at 60 Hz for `seconds`, starting at `t0`; returns the end time.
    @discardableResult
    func feed(_ gate: inout DistanceGate, cm: Double?, seconds: Double, from t0: Double = 0) -> Double {
        var t = t0
        for _ in 0..<Int(seconds * 60) {
            gate.update(distanceCm: cm, at: t)
            t += 1.0 / 60
        }
        return t
    }

    @Test func gateMessagesForEachRange() {
        var g = DistanceGate()
        #expect(g.status == .noFace)
        #expect(g.status.message == "No face detected")
        feed(&g, cm: 25, seconds: 1)
        #expect(g.status == .tooClose(25))
        #expect(g.status.message == "Move farther away (25 cm)")
        var far = DistanceGate()
        feed(&far, cm: 45, seconds: 1)
        #expect(far.status == .tooFar(45))
        #expect(far.status.message == "Move closer (45 cm)")
    }

    @Test func readyOnlyAfterOneSecondInRange() {
        var g = DistanceGate()
        let t = feed(&g, cm: 35, seconds: 0.9)
        #expect(g.status == .holding(35))
        #expect(g.status.message == "Good positioning — 35 cm")
        #expect(!g.status.isReady)
        feed(&g, cm: 35, seconds: 0.2, from: t)
        #expect(g.status == .ready(35))
        #expect(g.status.message == "Ready to record — 35 cm")
    }

    @Test func leavingRangeOrLosingTrackingRestartsTheHold() {
        var g = DistanceGate()
        var t = feed(&g, cm: 35, seconds: 1.5)
        #expect(g.status.isReady)
        t = feed(&g, cm: nil, seconds: 0.05, from: t)       // tracking lost
        #expect(g.status == .noFace)
        t = feed(&g, cm: 35, seconds: 0.5, from: t)
        #expect(!g.status.isReady)
        t = feed(&g, cm: 50, seconds: 0.5, from: t)         // walks out of range
        #expect(g.status == .tooFar(50))
        feed(&g, cm: 35, seconds: 0.8, from: t)
        #expect(!g.status.isReady)
    }

    @Test func smoothingDampsSingleFrameJitter() {
        var g = DistanceGate()
        let t = feed(&g, cm: 35, seconds: 1.5)
        g.update(distanceCm: 45, at: t)                     // one 10 cm outlier frame
        #expect(g.status.isReady)
        #expect(abs(g.smoothedCm! - 37) < 1e-9)            // moves 20 % of the way, stays in range
    }

    // MARK: - Summary

    @Test func summaryStatistics() throws {
        let s = FaceDistanceSummary(distancesCm: [nil, 34, 36, 45, 30, nil], check: .passed)
        #expect(s.check == .passed)
        #expect(s.recommendedRangeCm == [30, 40])
        #expect(s.atStartCm == 34)
        #expect(s.medianCm == 35)
        #expect(s.minCm == 30 && s.maxCm == 45)
        #expect(s.samplesWithDistance == 4 && s.sampleCount == 6)
        #expect(s.fractionOutsideRange == 0.25)
    }

    @Test func summaryWithoutDistancesHasNoStatistics() {
        let s = FaceDistanceSummary(distancesCm: [nil, nil], check: .bypassed)
        #expect(s.medianCm == nil && s.atStartCm == nil && s.fractionOutsideRange == nil)
        #expect(s.samplesWithDistance == 0)
    }
}
