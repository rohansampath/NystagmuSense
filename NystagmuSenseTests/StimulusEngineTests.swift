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

    // MARK: - Trial modes

    @Test func stillStripeModeNeverMoves() {
        let still = StimulusEngine(config: StimulusConfig(mode: .fixationStillStripes))
        #expect(still.config.speedPointsPerSecond == 0)
        for t in [0, 0.016, 0.5, 5, 10, 1_000.0] {
            #expect(still.displacement(at: t) == 0)
            #expect(still.snapshot(at: t).displacementPoints == 0)
            #expect(still.stripePositions(at: t, viewWidth: 874) == still.stripePositions(at: 0, viewWidth: 874))
        }
    }

    @Test func movingFixationModeMatchesOKNMotion() {
        let okn = StimulusEngine(config: StimulusConfig(mode: .okn))
        let fix = StimulusEngine(config: StimulusConfig(mode: .fixationMovingStripes))
        #expect(okn.config == StimulusConfig())          // default OKN trial is unchanged
        for t in [0, 0.016, 0.5, 3.7, 10.0] {
            #expect(fix.displacement(at: t) == okn.displacement(at: t))
            #expect(fix.backgroundGray(at: t) == okn.backgroundGray(at: t))
            #expect(fix.stripePositions(at: t, viewWidth: 874) == okn.stripePositions(at: t, viewWidth: 874))
        }
    }

    @Test(arguments: [StimulusConfig.Direction.rightward, .leftward])
    func directionReversesMotionForMovingModesOnly(_ direction: StimulusConfig.Direction) throws {
        let sign: Double = direction == .rightward ? 1 : -1
        for mode in [StimulusConfig.TrialMode.okn, .fixationMovingStripes] {
            let config = StimulusConfig(mode: mode, direction: direction)
            #expect(config.isMoving)
            #expect(StimulusEngine(config: config).displacement(at: 2) == sign * 252)   // same speed magnitude
        }
        let still = StimulusConfig(mode: .fixationStillStripes, direction: direction)
        #expect(!still.isMoving)
        #expect(StimulusEngine(config: still).displacement(at: 2) == 0)
        let decoded = try JSONDecoder().decode(StimulusConfig.self,
                                               from: JSONEncoder().encode(StimulusConfig(mode: .okn, direction: direction)))
        #expect(decoded.direction == direction)
        #expect(StimulusConfig(mode: .okn, direction: direction).participantInstruction
                    .hasSuffix(direction == .rightward ? "move to the right." : "move to the left."))
    }

    @Test func trialModeRoundTripsThroughJSON() throws {
        for mode in StimulusConfig.TrialMode.allCases {
            let config = StimulusConfig(mode: mode)
            let decoded = try JSONDecoder().decode(StimulusConfig.self, from: JSONEncoder().encode(config))
            #expect(decoded == config)
            #expect(decoded.trialMode == mode)
        }
    }

    @Test func sidecarWithoutModeDecodesAsOKN() throws {
        // A schema-2 sidecar's stimulus block, written before trialMode existed.
        let json = """
        {"stripeWidthRatio":0.02,"pitchToWidthRatio":2.4,"speedPointsPerSecond":90,"direction":"rightward",
         "fadeHalfCycleSeconds":30,"fixedBackgroundGray":0,"stripeGray":1}
        """
        let config = try JSONDecoder().decode(StimulusConfig.self, from: Data(json.utf8))
        #expect(config.trialMode == .okn)
        // Recorded settings are kept as written (independent of current defaults).
        #expect(config.speedPointsPerSecond == 90 && config.fixedBackgroundGray == 0 && config.stripeGray == 1)
    }

    @Test func fixationDotIsCentredAndOnlyInControlModes() throws {
        let size = CGSize(width: 874, height: 402)
        #expect(StimulusEngine(config: StimulusConfig(mode: .okn)).fixationDotRect(in: size) == nil)
        for mode in [StimulusConfig.TrialMode.fixationMovingStripes, .fixationStillStripes] {
            let dot = try #require(StimulusEngine(config: StimulusConfig(mode: mode)).fixationDotRect(in: size))
            #expect(dot.midX == 437 && dot.midY == 201)
            #expect(dot.width == 12 && dot.height == 12)
        }
    }
}
