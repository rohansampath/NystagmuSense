//
//  StimulusEngineTests.swift
//  NystagmuSenseTests
//

import CoreGraphics
import Foundation
import Testing
@testable import NystagmuSense

struct StimulusEngineTests {
    let engine = StimulusEngine()

    @Test func backgroundFadesWhiteToBlackAndBack() {
        var config = StimulusConfig()
        config.fixedBackgroundGray = nil
        config.fadeHalfCycleSeconds = 30
        let engine = StimulusEngine(config: config)
        #expect(engine.backgroundGray(at: 0)  == 1)
        #expect(engine.backgroundGray(at: 15) == 0.5)
        #expect(engine.backgroundGray(at: 30) == 0)
        #expect(engine.backgroundGray(at: 45) == 0.5)
        #expect(engine.backgroundGray(at: 60) == 1)
        #expect(engine.snapshot(at: 15).shadePercent == 50)
    }

    @Test func defaultBlackBarsFadeIntoBackgroundWithinTenSeconds() {
        #expect(engine.config.stripeGray == 0)
        #expect(engine.config.fixedBackgroundGray == nil)
        #expect(engine.backgroundGray(at: -1) == 1)
        for t in stride(from: 0.0, through: 10.0, by: 0.5) {
            #expect(abs(engine.snapshot(at: t).backgroundGray - (1 - t / 10)) < 1e-9)
        }
        #expect(engine.backgroundGray(at: 10) == engine.config.stripeGray)
    }

    @Test func fixedBackgroundControlDoesNotFade() {
        var config = StimulusConfig()
        config.fixedBackgroundGray = 0
        config.stripeGray = 1
        let engine = StimulusEngine(config: config)
        for t in [0.0, 5.0, 10.0, 30.0] {
            #expect(engine.backgroundGray(at: t) == 0)
        }
    }

    @Test func stimulusSettingsRoundTripForFadingAndFixedSessions() throws {
        let backgrounds: [Double?] = [nil, 0]
        for fixedGray in backgrounds {
            var config = StimulusConfig()
            config.fixedBackgroundGray = fixedGray
            let encoded = try JSONEncoder().encode(config)
            #expect(try JSONDecoder().decode(StimulusConfig.self, from: encoded) == config)
        }
    }

    @Test func legacySidecarsRetainOriginalAppearance() throws {
        let json = """
        {"stripeWidthRatio":0.02,"pitchToWidthRatio":2.4,"speedPointsPerSecond":90,
         "direction":"rightward","fadeHalfCycleSeconds":30}
        """
        let config = try JSONDecoder().decode(StimulusConfig.self, from: Data(json.utf8))
        #expect(config.stripeGray == 0)
        #expect(config.fixedBackgroundGray == nil)
        #expect(StimulusEngine(config: config).backgroundGray(at: 15) == 0.5)
    }

    @Test func stripesMoveByScheduledDisplacementEachFrame() {
        for direction in [StimulusConfig.Direction.leftward, .rightward] {
            var config = StimulusConfig()
            config.direction = direction
            let engine = StimulusEngine(config: config)
            for hz in [60.0, 120.0] {
                let t = 0.1
                let delta = 1 / hz
                let before = engine.stripePositions(at: t, viewWidth: 844)
                let after = engine.stripePositions(at: t + delta, viewWidth: 844)
                let expected = engine.displacement(at: t + delta) - engine.displacement(at: t)
                #expect(abs(Double(after[0] - before[0]) - expected) < 1e-9)
            }
        }
    }

    @Test func wraparoundPreservesVisibleGrating() {
        let width: CGFloat = 844
        let period = Double(engine.pitch(viewWidth: width)) / engine.config.speedPointsPerSecond
        let before = engine.stripePositions(at: 0, viewWidth: width)
        let after = engine.stripePositions(at: period, viewWidth: width)
        for (a, b) in zip(before, after) { #expect(abs(a - b) < 1e-9) }
    }

    @Test func displacementFollowsSpeedAndDirection() {
        #expect(abs(engine.config.speedPointsPerSecond - 90 * 1.4) < 1e-9)
        #expect(engine.displacement(at: 2) == 252)
        var cfg = StimulusConfig()
        cfg.direction = .leftward
        #expect(StimulusEngine(config: cfg).displacement(at: 2) == -252)
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

    @Test func instructionFollowsConfiguredStimulus() {
        #expect(StimulusConfig().participantInstruction
                == "Keep your head still and watch the black bars move to the right.")
        var cfg = StimulusConfig()
        cfg.direction = .leftward
        cfg.stripeGray = 0
        #expect(cfg.participantInstruction
                == "Keep your head still and watch the black bars move to the left.")
    }
}
