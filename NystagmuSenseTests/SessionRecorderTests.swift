//
//  SessionRecorderTests.swift
//  NystagmuSenseTests
//

import Foundation
import Testing
@testable import NystagmuSense

struct SessionRecorderTests {
    let device = DeviceInfo(model: "TestDevice1,1", systemName: "iOS",
                            systemVersion: "18.5", appVersion: "1.0")

    func makeRecorder(start: Double = 100, duration: Double = 10) -> SessionRecorder {
        SessionRecorder(startUptime: start, duration: duration, stimulus: StimulusEngine())
    }

    func tempDir() -> URL {
        FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    }

    @Test func timestampsAreRelativeToSessionStart() {
        var r = makeRecorder()
        let kept = r.record(Fixture.tracked(at: 100.5))
        #expect(kept)
        #expect(r.samples.first?.t == 0.5)
        #expect(r.samples.first?.stimulus == StimulusEngine().snapshot(at: 0.5))
    }

    @Test func samplesOutsideWindowAreDropped() {
        var r = makeRecorder()
        let kept = [r.record(Fixture.tracked(at: 99.9)),    // before start
                    r.record(Fixture.tracked(at: 110.0)),   // exactly at end
                    r.record(Fixture.tracked(at: 110.1))]   // after end
        #expect(kept == [false, true, false])
        #expect(r.samples.count == 1)
        #expect(r.droppedOutsideWindow == 2)
    }

    @Test func statsAndUntrackedSamples() {
        var r = makeRecorder()
        r.record(Fixture.tracked(at: 100))
        r.record(.untracked(at: 100.5))
        r.record(Fixture.tracked(at: 101))
        #expect(r.trackedCount == 2)
        #expect(r.recordedSpan == 1)
        #expect(r.observedSampleRate == 2)
    }

    @Test func emptyRecorderHasNoRate() {
        #expect(makeRecorder().observedSampleRate == nil)
    }

    @Test func csvHasHeaderAndEmptyFieldsForMissingData() {
        var r = makeRecorder()
        r.record(Fixture.tracked(at: 101, x: 0.25))
        r.record(.untracked(at: 102))
        let lines = r.csv().split(separator: "\n").map(String.init)

        #expect(lines[0] == SessionRecorder.csvColumns.joined(separator: ","))
        let tracked = lines[1].split(separator: ",", omittingEmptySubsequences: false)
        let missing = lines[2].split(separator: ",", omittingEmptySubsequences: false)
        #expect(tracked.count == SessionRecorder.csvColumns.count)
        #expect(missing.count == SessionRecorder.csvColumns.count)
        #expect(tracked[0] == "1.000000" && tracked[2] == "1" && tracked[3] == "0.25")
        #expect(tracked[12] == "0.1" && tracked[13] == "0.2")   // blink left/right
        #expect(missing[2] == "0" && missing[3...13].allSatisfy(\.isEmpty))
    }

    @Test func exportRejectsEmptyRecording() {
        #expect(throws: RecordingError.noSamples) {
            try makeRecorder().export(to: tempDir(), device: device)
        }
    }

    @Test func exportWritesCSVAndMetadata() throws {
        var r = makeRecorder()
        r.record(Fixture.tracked(at: 100.0))
        r.record(Fixture.tracked(at: 100.1))
        r.note("test issue")

        let dir = tempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let files = try r.export(to: dir, device: device)

        #expect(try String(contentsOf: files.csv, encoding: .utf8) == r.csv())
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let meta = try decoder.decode(SessionMetadata.self, from: Data(contentsOf: files.metadata))
        #expect(meta.sessionID == r.sessionID)
        #expect(meta.sampleCount == 2)
        #expect(meta.device == device)
        #expect(meta.issues == ["test issue"])
        #expect(Set(meta.columns.keys) == Set(SessionRecorder.csvColumns))
    }
}
