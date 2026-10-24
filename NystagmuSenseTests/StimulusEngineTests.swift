//
//  StimulusEngineTests.swift
//  NystagmuSenseTests
//

import CoreGraphics
import Testing
@testable import NystagmuSense

struct StimulusEngineTests {
    let engine = StimulusEngine()

    @Test func backgroundFadesWhiteToBlackAndBack() {
        #expect(engine.backgroundGray(at: 0)  == 1)
        #expect(engine.backgroundGray(at: 15) == 0.5)
        #expect(engine.backgroundGray(at: 30) == 0)
        #expect(engine.backgroundGray(at: 45) == 0.5)
        #expect(engine.backgroundGray(at: 60) == 1)
        #expect(engine.snapshot(at: 15).shadePercent == 50)
    }

    @Test func displacementFollowsSpeedAndDirection() {
        #expect(engine.displacement(at: 2) == 180)
        var cfg = StimulusConfig()
        cfg.direction = .leftward
        #expect(StimulusEngine(config: cfg).displacement(at: 2) == -180)
        #expect(engine.displacement(at: -1) == 0)
    }

    @Test func defaultsMatchOriginalGeometry() {
        // Original FadingStripeView: width = 2 % of view, pitch = 2.4 × width.
        #expect(abs(engine.stripeWidth(viewWidth: 400) - 8) < 1e-9)
        #expect(abs(engine.pitch(viewWidth: 400) - 19.2) < 1e-9)
        #expect(engine.stripeWidth(viewWidth: 10) == 1)
    }

    @Test func stripePositionsAreDeterministicAndEvenlySpaced() {
        let a = engine.stripePositions(at: 3.7, viewWidth: 400)
        #expect(a == engine.stripePositions(at: 3.7, viewWidth: 400))

        let p = engine.pitch(viewWidth: 400)
        for (x0, x1) in zip(a, a.dropFirst()) { #expect(abs((x1 - x0) - p) < 1e-9) }
        #expect(a.first! >= -3 * p && a.first! < -2 * p)
        #expect(a.last! >= 400 && a.last! < 400 + p)
    }

    @Test func leftwardOffsetStaysInRange() {
        var cfg = StimulusConfig()
        cfg.direction = .leftward
        let e = StimulusEngine(config: cfg)
        let p = e.pitch(viewWidth: 400)
        let first = e.stripePositions(at: 1.234, viewWidth: 400).first!
        #expect(first >= -3 * p && first < -2 * p)
    }
}
