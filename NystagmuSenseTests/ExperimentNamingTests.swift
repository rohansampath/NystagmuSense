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

    @Test(arguments: [("p02", "P02"), ("  P_02 ", "P02"), ("", "EXP"), ("___", "EXP"),
                      ("pilot-3", "PILOT-3"), ("ABCDEFGHIJKLMNOPQRS", "ABCDEFGHIJKLMNOP")])
    func experimentIDIsSanitised(_ raw: String, _ expected: String) {
        #expect(ExperimentLog.sanitized(raw) == expected)
    }

    // MARK: - Counter

    @Test func trialNumbersAreSequentialPerExperiment() throws {
        let log = ExperimentLog(defaults: try freshDefaults())
        #expect(log.nextTrialNumber(for: "P02") == 1)
        let reserved: [Int] = (0..<3).map { _ in log.reserveTrialNumber(for: "P02") }
        #expect(reserved == [1, 2, 3])
        #expect(log.reserveTrialNumber(for: "P03") == 1)
        #expect(log.nextTrialNumber(for: "P02") == 4)
    }

    @Test func numberingPersistsAcrossRestart() throws {
        let defaults = try freshDefaults()
        defaults.set("p02", forKey: ExperimentLog.idKey)
        _ = ExperimentLog(defaults: defaults).reserveTrialNumber(for: "P02")
        _ = ExperimentLog(defaults: defaults).reserveTrialNumber(for: "P02")
        // A new instance on the same store = the app after relaunch.
        let relaunched = ExperimentLog(defaults: defaults)
        #expect(relaunched.experimentID == "P02")
        #expect(relaunched.reserveTrialNumber(for: "P02") == 3)
    }

    // MARK: - Export

    @Test func namedExportSharesOneStemAndRecordsTrialFields() throws {
        var r = SessionRecorder(startUptime: 100, startedAt: start, duration: 10,
                                stimulus: StimulusEngine(config: StimulusConfig(mode: .okn, direction: .leftward)))
        r.record(Fixture.tracked(at: 100.0, distance: 0.35))
        r.record(Fixture.tracked(at: 100.1, distance: 0.36))
        r.name = RecordingName(experimentID: "P02", trialNumber: 7, stimulus: r.stimulus.config, startedAt: start)
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: dir) }

        let files = try r.export(to: dir, device: device)
        let stem = "P02_T007_OKN_LEFT_20261104_143022"
        #expect(files.directory.lastPathComponent == stem)
        #expect(files.csv.lastPathComponent == stem + ".csv")
        #expect(files.metadata.lastPathComponent == stem + ".json")

        let meta = try decode(files.metadata)
        #expect(meta.schemaVersion == 4)
        #expect(meta.experimentID == "P02")
        #expect(meta.trialNumber == 7)
        #expect(meta.recordingName == stem)
        #expect(meta.stimulus.direction == .leftward)
        #expect(meta.stimulus.trialMode == .okn)
        #expect(meta.sessionID == r.sessionID)
        #expect(meta.startedAt == start)
        // The CSV schema is unchanged by naming or distance.
        #expect(try String(contentsOf: files.csv, encoding: .utf8).hasPrefix(SessionRecorder.csvColumns.joined(separator: ",")))
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
    }
}
