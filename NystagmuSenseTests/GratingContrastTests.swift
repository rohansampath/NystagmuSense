//
//  GratingContrastTests.swift
//  NystagmuSenseTests
//
//  Pilot 05 nominal-contrast gratings. These check code values and the
//  luminance model; they cannot show that the display produces the contrast.
//

import Foundation
import Testing
@testable import NystagmuSense

struct GratingContrastTests {
    let device = DeviceInfo(model: "TestDevice1,1", systemName: "iOS", systemVersion: "18.5", appVersion: "1.0")
    /// 2026-11-04 14:30:22 UTC
    let start = Date(timeIntervalSince1970: 1_793_802_622)

    struct CodeFixture: Decodable {
        struct Level: Decodable {
            let percent: Int
            let code: String
            let luminance_background: Double
            let luminance_bar: Double
            let code_background: Double
            let code_bar: Double
        }
        let mean_relative_luminance: Double
        let pitch_to_width_ratio: Double
        let levels: [Level]
    }

    /// scripts/tests/fixtures/contrast_codes.json, written by analysis/pilot_05/contrast_model.py.
    func sharedCodes() throws -> CodeFixture {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("scripts/tests/fixtures/contrast_codes.json")
        return try JSONDecoder().decode(CodeFixture.self, from: Data(contentsOf: url))
    }

    @Test func levelsAndNameCodes() {
        #expect(NominalContrast.allCases.map(\.rawValue) == [0, 5, 10, 20, 40, 80])
        #expect(NominalContrast.allCases.map(\.nameCode) == ["C000", "C005", "C010", "C020", "C040", "C080"])
        #expect(NominalContrast.c20.fraction == 0.2)
    }

    @Test func appMatchesThePythonContrastModelExactly() throws {
        let fixture = try sharedCodes()
        #expect(fixture.mean_relative_luminance == GratingLuminance.meanRelativeLuminance)
        #expect(fixture.pitch_to_width_ratio == StimulusConfig().pitchToWidthRatio)
        #expect(fixture.levels.map(\.percent) == NominalContrast.allCases.map(\.rawValue))
        for level in fixture.levels {
            let contrast = try #require(NominalContrast(rawValue: level.percent))
            var config = StimulusConfig(mode: .okn, direction: .leftward)
            config.applyNominalContrast(contrast)
            #expect(contrast.nameCode == level.code)
            #expect(abs(try #require(config.fixedBackgroundGray) - level.code_background) < 1e-12)
            #expect(abs(config.stripeGray - level.code_bar) < 1e-12)
        }
    }

    @Test(arguments: NominalContrast.allCases)
    func michelsonContrastAndMeanLuminanceHold(_ contrast: NominalContrast) {
        let d = StimulusConfig().barFraction
        let l = GratingLuminance.luminances(contrast: contrast.fraction, barFraction: d)
        #expect(abs((l.background - l.bar) / (l.background + l.bar) - contrast.fraction) < 1e-12)
        #expect(abs(d * l.bar + (1 - d) * l.background - GratingLuminance.meanRelativeLuminance) < 1e-12)
        // Encoded values are not linear in luminance; decoding them restores it.
        let codes = GratingLuminance.codeValues(contrast: contrast.fraction, barFraction: d)
        #expect(abs(GratingLuminance.srgbDecode(codes.background) - l.background) < 1e-12)
        #expect((0...1).contains(codes.background) && (0...1).contains(codes.bar))
        if contrast != .c0 {
            #expect(abs((codes.background - codes.bar) / (codes.background + codes.bar) - contrast.fraction) > 1e-3)
        }
    }

    @Test func zeroContrastIsAUniformFieldThatStillMoves() {
        var config = StimulusConfig(mode: .okn, direction: .rightward)
        config.applyNominalContrast(.c0)
        #expect(config.fixedBackgroundGray == config.stripeGray)
        let engine = StimulusEngine(config: config)
        #expect(engine.snapshot(at: 2).displacementPoints == 252)          // direction and speed still recorded
        #expect(engine.snapshot(at: 2).backgroundGray == config.fixedBackgroundGray)
    }

    @Test func contrastChangesOnlyTheGreyLevels() {
        let base = StimulusConfig(mode: .okn, direction: .leftward)
        for contrast in NominalContrast.allCases {
            var c = base
            c.applyNominalContrast(contrast)
            #expect(c.speedPointsPerSecond == base.speedPointsPerSecond && c.direction == base.direction)
            #expect(c.stripeWidthRatio == base.stripeWidthRatio && c.pitchToWidthRatio == base.pitchToWidthRatio)
            #expect(c.trialMode == .okn && c.fadeHalfCycleSeconds == base.fadeHalfCycleSeconds)
            #expect(StimulusEngine(config: c).fixationDotRect(in: CGSize(width: 874, height: 402)) == nil)
        }
    }

    @Test func instructionIsIdenticalAtEveryLevelAndNamesNoDirection() {
        var texts = Set<String>()
        for contrast in NominalContrast.allCases {
            for direction in [StimulusConfig.Direction.leftward, .rightward] {
                var c = StimulusConfig(mode: .okn, direction: direction)
                c.applyNominalContrast(contrast)
                texts.insert(c.participantInstruction)
            }
        }
        #expect(texts.count == 1)
        let text = texts.first!.lowercased()
        #expect(!text.contains("left") && !text.contains("right") && !text.contains("bar"))
    }

    @Test func selectionNeedsAContrastOnlyForPilot05() {
        #expect(!TrialSelection(testType: .pilot05, participant: .p01).isComplete)
        #expect(TrialSelection(testType: .pilot05, participant: .p01).missingChoice == "Choose the contrast")
        #expect(TrialSelection(testType: .pilot05, participant: nil, contrast: .c5).missingChoice == "Choose the participant")
        #expect(TrialSelection(testType: .pilot05, participant: .p03, contrast: .c0).isComplete)
        #expect(TrialSelection(testType: .pilot04, participant: .p01, contrast: .c20).contrast == nil)
    }

    @Test func pilot05IsAlwaysRegularOknAtTheChosenContrast() {
        let selection = TrialSelection(testType: .pilot05, participant: .p02, contrast: .c40)
        let config = TestView.stimulusConfig(mode: .fixationStillStripes, direction: .rightward, selection: selection)
        #expect(config.trialMode == .okn && config.isMoving)
        #expect(config.michelsonContrast == 0.4)
        let p04 = TestView.stimulusConfig(mode: .okn, direction: .rightward,
                                          selection: TrialSelection(testType: .pilot04, participant: .p01))
        #expect(p04.michelsonContrast == nil && p04.fixedBackgroundGray == 1 && p04.stripeGray == 0)
    }

    @Test func contrastPersistsUntilChanged() throws {
        let defaults = try #require(UserDefaults(suiteName: "contrast-" + UUID().uuidString))
        defaults.set(TestType.pilot05.code, forKey: ExperimentLog.testTypeKey)
        defaults.set(Participant.p01.rawValue, forKey: ExperimentLog.participantKey)
        #expect(ExperimentLog(defaults: defaults).contrast == nil)
        defaults.set(20, forKey: ExperimentLog.contrastKey)
        #expect(ExperimentLog(defaults: defaults).selection
                == TrialSelection(testType: .pilot05, participant: .p01, contrast: .c20))
        defaults.set(-1, forKey: ExperimentLog.contrastKey)
        #expect(ExperimentLog(defaults: defaults).contrast == nil)
    }

    @Test func exportNamesAndRecordsTheContrast() throws {
        for (contrast, direction, stem) in [
            (NominalContrast.c20, StimulusConfig.Direction.leftward, "P05-P01_T120_OKN_LEFT_C020_20261104_143022"),
            (.c0, .rightward, "P05-P01_T120_OKN_RIGHT_C000_20261104_143022"),
        ] {
            let selection = TrialSelection(testType: .pilot05, participant: .p01, contrast: contrast)
            let config = TestView.stimulusConfig(mode: .okn, direction: direction, selection: selection)
            var r = SessionRecorder(startUptime: 100, startedAt: start, duration: 10, stimulus: StimulusEngine(config: config))
            r.record(Fixture.tracked(at: 100.0))
            r.name = RecordingName(experimentID: selection.testType.code, participantID: selection.participant?.rawValue,
                                   trialNumber: 120, stimulus: config, startedAt: start)
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: dir) }
            let files = try r.export(to: dir, device: device)
            #expect(files.directory.lastPathComponent == stem)
            #expect(files.csv.lastPathComponent == stem + ".csv" && files.metadata.lastPathComponent == stem + ".json")
            let d = JSONDecoder()
            d.dateDecodingStrategy = .iso8601
            let meta = try d.decode(SessionMetadata.self, from: Data(contentsOf: files.metadata))
            #expect(meta.schemaVersion == 7)
            #expect(meta.experimentID == "P05" && meta.participantID == "P01" && meta.recordingName == stem)
            #expect(meta.stimulus.michelsonContrast == contrast.fraction)
            #expect(meta.stimulus.meanRelativeLuminance == 0.5)
            #expect(meta.stimulus.direction == direction && meta.stimulus.speedPointsPerSecond == 126)
            #expect(meta.directionCode == (direction == .leftward ? "LEFT" : "RIGHT"))
        }
    }

    @Test func olderStimulusSidecarsDecodeWithoutContrast() throws {
        let json = #"{"stripeWidthRatio":0.02,"pitchToWidthRatio":2.4,"speedPointsPerSecond":126,"direction":"rightward","fadeHalfCycleSeconds":10,"fixedBackgroundGray":1,"stripeGray":0,"trialMode":"okn"}"#
        let config = try JSONDecoder().decode(StimulusConfig.self, from: Data(json.utf8))
        #expect(config.michelsonContrast == nil && config.meanRelativeLuminance == nil)
        #expect(RecordingName(experimentID: "P04", participantID: "P01", trialNumber: 61, stimulus: config,
                              startedAt: start).stem == "P04-P01_T061_OKN_RIGHT_20261104_143022")
    }
}
