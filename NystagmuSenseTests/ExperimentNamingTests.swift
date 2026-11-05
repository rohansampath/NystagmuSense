//
//  ExperimentNamingTests.swift
//  NystagmuSenseTests
//
//  Descriptive file names, the persistent trial counter, named exports and
//  backward-compatible sidecar decoding.
//

import Foundation
import Testing
@testable import NystagmuSense

struct ExperimentNamingTests {
    let device = DeviceInfo(model: "TestDevice1,1", systemName: "iOS", systemVersion: "18.5", appVersion: "1.0")
    /// 2026-11-04 14:30:22 UTC
    let start = Date(timeIntervalSince1970: 1_793_802_622)

    func freshDefaults() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "naming-" + UUID().uuidString))
    }

    func decode(_ url: URL) throws -> SessionMetadata {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return try d.decode(SessionMetadata.self, from: Data(contentsOf: url))
    }

    // MARK: - Names

    @Test(arguments: [
        (StimulusConfig.TrialMode.okn, StimulusConfig.Direction.rightward, "P02_T001_OKN_RIGHT_20261104_143022"),
        (.okn, .leftward, "P02_T001_OKN_LEFT_20261104_143022"),
        (.fixationMovingStripes, .rightward, "P02_T001_FIXMOVE_RIGHT_20261104_143022"),
        (.fixationMovingStripes, .leftward, "P02_T001_FIXMOVE_LEFT_20261104_143022"),
        (.fixationStillStripes, .rightward, "P02_T001_FIXSTILL_NONE_20261104_143022"),
        (.fixationStillStripes, .leftward, "P02_T001_FIXSTILL_NONE_20261104_143022"),
    ])
    func nameForEachModeAndDirection(_ mode: StimulusConfig.TrialMode, _ dir: StimulusConfig.Direction,
                                     _ expected: String) {
        let name = RecordingName(experimentID: "P02", trialNumber: 1,
                                 stimulus: StimulusConfig(mode: mode, direction: dir), startedAt: start)
        #expect(name.stem == expected)
    }

    @Test func timestampIsUTCRegardlessOfTimeZone() {
        // Same instant, any device time zone → same name (formatter pinned to UTC).
        let name = RecordingName(experimentID: "X", trialNumber: 12, stimulus: StimulusConfig(), startedAt: start)
        #expect(name.stem.hasSuffix("_20261104_143022"))
        #expect(name.stem.contains("_T012_"))
        #expect(RecordingName.trialLabel(1234) == "T1234")
    }

    // MARK: - Shared contract with the receiver

    struct NameFixture: Decodable {
        struct Case: Decodable {
            let testType: String
            let participant: String?
            let trial: Int
            let mode: String
            let direction: String
            let startedAt: Date
            let name: String
        }
        let contract_version: Int
        let generated: [Case]
        let legacy_valid: [String]
        let invalid: [String]
    }

    /// scripts/tests/fixtures/recording_names.json, also validated by the Python receiver tests.
    func sharedFixture() throws -> NameFixture {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("scripts/tests/fixtures/recording_names.json")
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return try d.decode(NameFixture.self, from: Data(contentsOf: url))
    }

    @Test func appGeneratesExactlyTheSharedFixtureNames() throws {
        let fixture = try sharedFixture()
        #expect(fixture.contract_version == RecordingName.contractVersion)
        for c in fixture.generated {
            let mode = try #require(StimulusConfig.TrialMode(rawValue: c.mode))
            let direction = try #require(StimulusConfig.Direction(rawValue: c.direction))
            let type = try #require(TestType(rawValue: c.testType), "unknown test type \(c.testType)")
            let participant = try c.participant.map { try #require(Participant(rawValue: $0)) }
            let selection = TrialSelection(testType: type, participant: participant)
            #expect(selection.isComplete)
            let name = RecordingName(experimentID: type.code, participantID: selection.participant?.rawValue,
                                     trialNumber: c.trial,
                                     stimulus: StimulusConfig(mode: mode, direction: direction), startedAt: c.startedAt)
            #expect(name.stem == c.name)
        }
        // Every selectable test type is covered, so the receiver is tested with it.
        #expect(Set(fixture.generated.map(\.testType)) == Set(TestType.allCases.map(\.code)))
    }

    @Test func noGeneratedNameLooksLikeAnInvalidFixtureName() throws {
        let fixture = try sharedFixture()
        let generated = Set(fixture.generated.map(\.name))
        #expect(generated.isDisjoint(with: fixture.invalid))
        #expect(generated.allSatisfy { !$0.contains("/") && !$0.contains(".") && $0.allSatisfy(\.isASCII) })
    }

    // MARK: - Test types

    @Test func testTypeCodesAndNames() {
        let expected: [(TestType, String, String)] = [
            (.general, "DEV", "General Test"), (.gazeValidation, "GAZE", "Gaze Validation"),
            (.blink, "BLINK", "Blink Test"), (.oknDetection, "OKNTEST", "OKN Detection"),
            (.direction, "DIR", "Direction Test"), (.fixationControl, "FIX", "Fixation Control"),
            (.distance, "DIST", "Distance Test"), (.pilot02, "P02", "Pilot 02"), (.pilot03, "P03", "Pilot 03"),
        ]
        #expect(TestType.allCases.count == expected.count)
        for (type, code, name) in expected {
            #expect(type.code == code && type.displayName == name)
        }
    }

    @Test func testTypeDefaultsToGeneralAndPersists() throws {
        let defaults = try freshDefaults()
        #expect(ExperimentLog(defaults: defaults).testType == .general)
        defaults.set(TestType.direction.code, forKey: ExperimentLog.testTypeKey)
        #expect(ExperimentLog(defaults: defaults).testType == .direction)   // after relaunch
        defaults.set("NOPE", forKey: ExperimentLog.testTypeKey)
        #expect(ExperimentLog(defaults: defaults).testType == .general)
    }

    // MARK: - Counter

    @Test func oneSequenceAcrossTestTypesAdvancedOnlyBySaves() throws {
        let log = ExperimentLog(defaults: try freshDefaults())
        #expect(log.nextTrialNumber == 1)
        #expect(log.nextTrialNumber == 1)           // reading doesn't consume
        log.commitTrialNumber(1)
        log.commitTrialNumber(2)
        #expect(log.nextTrialNumber == 3)
        log.commitTrialNumber(2)                     // a repeated commit (Retry Export) never moves it back
        #expect(log.nextTrialNumber == 3)
    }

    @Test func numberingPersistsAcrossRestart() throws {
        let defaults = try freshDefaults()
        ExperimentLog(defaults: defaults).commitTrialNumber(1)
        ExperimentLog(defaults: defaults).commitTrialNumber(2)
        // A new instance on the same store = the app after relaunch.
        #expect(ExperimentLog(defaults: defaults).nextTrialNumber == 3)
    }

    @Test func earlierPerExperimentCountersAreNeverUndercut() throws {
        let defaults = try freshDefaults()
        defaults.set(5, forKey: "experiment.nextTrial.EXP")    // written by the free-text version
        #expect(ExperimentLog(defaults: defaults).nextTrialNumber == 5)
    }

    // MARK: - Export

    @Test func namedExportSharesOneStemAndRecordsTrialFields() throws {
        var r = SessionRecorder(startUptime: 100, startedAt: start, duration: 10,
                                stimulus: StimulusEngine(config: StimulusConfig(mode: .okn, direction: .leftward)))
        r.record(Fixture.tracked(at: 100.0, distance: 0.35))
        r.record(Fixture.tracked(at: 100.1, distance: 0.36))
        r.name = RecordingName(experimentID: TestType.pilot02.code, trialNumber: 7,
                               stimulus: r.stimulus.config, startedAt: start)
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: dir) }

        let files = try r.export(to: dir, device: device)
        let stem = "P02_T007_OKN_LEFT_20261104_143022"
        #expect(files.directory.lastPathComponent == stem)
        #expect(files.csv.lastPathComponent == stem + ".csv")
        #expect(files.metadata.lastPathComponent == stem + ".json")

        let meta = try decode(files.metadata)
        #expect(meta.schemaVersion == 6)
        #expect(meta.experimentID == "P02")
        #expect(meta.testTypeName == "Pilot 02")
        #expect(meta.trialNumber == 7)
        #expect(meta.recordingName == stem)
        #expect(meta.stimulus.direction == .leftward)
        #expect(meta.stimulus.trialMode == .okn)
        #expect(meta.sessionID == r.sessionID)
        #expect(meta.startedAt == start)
        // The CSV schema is unchanged by naming or distance.
        #expect(try String(contentsOf: files.csv, encoding: .utf8).hasPrefix(SessionRecorder.csvColumns.joined(separator: ",")))
    }

    @Test func pilot03ExportRecordsParticipantAndDirectionCode() throws {
        for (mode, direction, stem, code) in [
            (StimulusConfig.TrialMode.okn, StimulusConfig.Direction.leftward, "P03-P02_T041_OKN_LEFT_20261104_143022", "LEFT"),
            (.fixationStillStripes, .leftward, "P03-P01_T041_FIXSTILL_NONE_20261104_143022", "NONE"),
        ] {
            let participant: Participant = code == "NONE" ? .p01 : .p02
            var r = SessionRecorder(startUptime: 100, startedAt: start, duration: 10,
                                    stimulus: StimulusEngine(config: StimulusConfig(mode: mode, direction: direction)))
            r.record(Fixture.tracked(at: 100.0))
            r.name = RecordingName(experimentID: TestType.pilot03.code, participantID: participant.rawValue,
                                   trialNumber: 41, stimulus: r.stimulus.config, startedAt: start)
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: dir) }
            let files = try r.export(to: dir, device: device)
            #expect(files.csv.lastPathComponent == stem + ".csv" && files.metadata.lastPathComponent == stem + ".json")
            let meta = try decode(files.metadata)
            #expect(meta.schemaVersion == 6)
            #expect(meta.experimentID == "P03" && meta.testTypeName == "Pilot 03")
            #expect(meta.participantID == participant.rawValue)
            #expect(meta.directionCode == code)
            #expect(meta.recordingName == stem)
        }
    }

    @Test func onlyPilot03NeedsAParticipantAndAFixedBackground() {
        for type in TestType.allCases {
            #expect(type.requiresParticipant == (type == .pilot03))
            #expect(type.fixedBackgroundGray == (type == .pilot03 ? 1 : nil))
        }
        #expect(!TrialSelection(testType: .pilot03, participant: nil).isComplete)
        #expect(TrialSelection(testType: .pilot03, participant: .p02).isComplete)
        // A remembered participant never leaks into other test types' names.
        #expect(TrialSelection(testType: .direction, participant: .p01).participant == nil)
    }

    @Test func participantPersistsUntilChanged() throws {
        let defaults = try freshDefaults()
        #expect(ExperimentLog(defaults: defaults).participant == nil)
        defaults.set(Participant.p02.rawValue, forKey: ExperimentLog.participantKey)
        defaults.set(TestType.pilot03.code, forKey: ExperimentLog.testTypeKey)
        let log = ExperimentLog(defaults: defaults)                       // after relaunch
        #expect(log.selection == TrialSelection(testType: .pilot03, participant: .p02))
        defaults.set("Ashwin", forKey: ExperimentLog.participantKey)      // never a valid code
        #expect(ExperimentLog(defaults: defaults).participant == nil)
    }

    @Test func schema5SidecarStillDecodes() throws {
        let json = """
        {"schemaVersion":5,"sessionID":"1A2F66B1-8A5C-4890-BBB5-7FBE6E263000","startedAt":"2026-11-04T07:45:41Z",
         "device":{"model":"iPhone17,1","systemName":"iOS","systemVersion":"26.6.2","appVersion":"1.0"},
         "plannedDurationSeconds":10,"recordedSpanSeconds":9.96,"sampleCount":599,"trackedSampleCount":599,
         "droppedOutsideWindowCount":2,"droppedOutOfOrderCount":0,"observedSampleRateHz":60.01,
         "stimulus":{"direction":"rightward","fadeHalfCycleSeconds":10,"pitchToWidthRatio":2.4,
                     "speedPointsPerSecond":126,"stripeGray":0,"stripeWidthRatio":0.02,"trialMode":"okn"},
         "issues":[],"experimentID":"DIR","testTypeName":"Direction Test","trialNumber":5,
         "recordingName":"DIR_T005_OKN_RIGHT_20261104_074541","gazeSource":"ARKit","columns":{},"timingNotes":""}
        """
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        let meta = try d.decode(SessionMetadata.self, from: Data(json.utf8))
        #expect(meta.schemaVersion == 5 && meta.experimentID == "DIR" && meta.trialNumber == 5)
        #expect(meta.participantID == nil && meta.directionCode == nil)
    }

    @Test func schema3SidecarStillDecodes() throws {
        // Shape of a Pilot 01 sidecar (schema 3), trimmed to required fields.
        let json = """
        {"schemaVersion":3,"sessionID":"1A2F66B1-8A5C-4890-BBB5-7FBE6E263000","startedAt":"2026-11-04T05:21:49Z",
         "device":{"model":"iPhone17,1","systemName":"iOS","systemVersion":"26.6.2","appVersion":"1.0"},
         "plannedDurationSeconds":10,"recordedSpanSeconds":9.96,"sampleCount":599,"trackedSampleCount":599,
         "droppedOutsideWindowCount":3,"droppedOutOfOrderCount":0,"observedSampleRateHz":60.01,
         "stimulus":{"direction":"rightward","fadeHalfCycleSeconds":10,"pitchToWidthRatio":2.4,
                     "speedPointsPerSecond":0,"stripeGray":0,"stripeWidthRatio":0.02,"trialMode":"fixationStillStripes"},
         "issues":[],"gazeSource":"ARKit","columns":{},"timingNotes":""}
        """
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        let meta = try d.decode(SessionMetadata.self, from: Data(json.utf8))
        #expect(meta.schemaVersion == 3)
        #expect(meta.stimulus.trialMode == .fixationStillStripes)
        #expect(meta.experimentID == nil && meta.trialNumber == nil && meta.recordingName == nil)
        #expect(meta.faceDistance == nil)
        #expect(meta.testTypeName == nil)
    }

    @Test func schema4SidecarWithFreeTextExperimentStillDecodes() throws {
        let json = """
        {"schemaVersion":4,"sessionID":"1A2F66B1-8A5C-4890-BBB5-7FBE6E263000","startedAt":"2026-11-04T14:30:22Z",
         "device":{"model":"iPhone17,1","systemName":"iOS","systemVersion":"26.6.2","appVersion":"1.0"},
         "plannedDurationSeconds":10,"recordedSpanSeconds":9.96,"sampleCount":599,"trackedSampleCount":599,
         "droppedOutsideWindowCount":3,"droppedOutOfOrderCount":0,"observedSampleRateHz":60.01,
         "stimulus":{"direction":"leftward","fadeHalfCycleSeconds":10,"pitchToWidthRatio":2.4,
                     "speedPointsPerSecond":126,"stripeGray":0,"stripeWidthRatio":0.02,"trialMode":"okn"},
         "issues":[],"gazeSource":"ARKit","columns":{},"timingNotes":"",
         "experimentID":"EXP","trialNumber":1,"recordingName":"EXP_T001_OKN_LEFT_20261104_143022",
         "faceDistance":{"check":"passed","recommendedRangeCm":[30,40],"atStartCm":35,"medianCm":35,
                         "minCm":34,"maxCm":36,"samplesWithDistance":599,"sampleCount":599,
                         "fractionOutsideRange":0,"definition":"x"}}
        """
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        let meta = try d.decode(SessionMetadata.self, from: Data(json.utf8))
        #expect(meta.experimentID == "EXP" && meta.testTypeName == nil)
        #expect(meta.stimulus.direction == .leftward)
        #expect(meta.faceDistance?.check == .passed)
    }
}
