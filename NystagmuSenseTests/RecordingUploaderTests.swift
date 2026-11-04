//
//  RecordingUploaderTests.swift
//  NystagmuSenseTests
//
//  Mac-transfer settings, request building, and an unreachable server.
//  No real Mac is involved; recordings are synthetic fixtures.
//

import Foundation
import Testing
@testable import NystagmuSense

struct RecordingUploaderTests {
    @Test(arguments: ["http://192.168.1.20:8765", "192.168.1.20:8765", " http://10.0.0.5:8765/ ",
                      "http://172.20.1.2:8765", "http://my-mac.local:8765", "http://127.0.0.1:8765"])
    func localAddressesAccepted(_ text: String) {
        #expect(TransferSettings(serverURL: text, token: "t").baseURL != nil)
    }

    @Test(arguments: ["", "https://192.168.1.20:8765", "http://example.com:8765", "http://8.8.8.8",
                      "http://172.32.0.1", "http://192.168.1.20:8765/upload", "http://192.168.1.20?x=1",
                      "http://192.168.1:8765", "ftp://192.168.1.20"])
    func nonLocalOrMalformedAddressesRejected(_ text: String) {
        #expect(TransferSettings(serverURL: text, token: "t").baseURL == nil)
    }

    @Test func emptySettingsMeanLocalOnly() {
        #expect(!TransferSettings().isEnabled)
        #expect(TransferSettings(serverURL: "192.168.1.20:8765", token: "").isEnabled)
    }

    @Test func settingsRoundTrip() throws {
        let defaults = try #require(UserDefaults(suiteName: UUID().uuidString))
        TransferSettings(serverURL: "http://192.168.1.20:8765", token: "abc").save(to: defaults)
        #expect(TransferSettings.load(from: defaults) == TransferSettings(serverURL: "http://192.168.1.20:8765", token: "abc"))
    }

    @Test func uploadRequestCarriesBothFilesUnchanged() throws {
        let files = try writeRecording()
        let uploader = RecordingUploader(settings: TransferSettings(serverURL: "192.168.1.20:8765", token: "secret"))
        let request = try uploader.uploadRequest(for: files)
        #expect(request.url?.absoluteString == "http://192.168.1.20:8765/upload")
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: RecordingUploader.tokenHeader) == "secret")
        #expect(request.timeoutInterval == RecordingUploader.timeout)
        let body = try JSONDecoder().decode([String: String].self, from: try #require(request.httpBody))
        #expect(body["stem"] == "NS_20261103-101500_ABCD1234_okn")
        #expect(body["csv"] == (try String(contentsOf: files.csv, encoding: .utf8)))
        #expect(body["json"] == (try String(contentsOf: files.metadata, encoding: .utf8)))
    }

    @Test func missingTokenOrBadAddressFailsBeforeNetwork() async throws {
        let files = try writeRecording()
        await #expect(throws: UploadError.missingToken) {
            try await RecordingUploader(settings: TransferSettings(serverURL: "192.168.1.20:8765", token: "")).upload(files)
        }
        await #expect(throws: UploadError.invalidAddress) {
            try await RecordingUploader(settings: TransferSettings(serverURL: "example.com", token: "t")).upload(files)
        }
    }

    @Test func serverUnavailableIsReportedAsUnreachable() async throws {
        let files = try writeRecording()
        // Nothing listens on port 1.
        let uploader = RecordingUploader(settings: TransferSettings(serverURL: "127.0.0.1:1", token: "t"))
        do {
            try await uploader.upload(files)
            Issue.record("expected an error")
        } catch let error as UploadError {
            guard case .unreachable = error else { Issue.record("got \(error)"); return }
        }
        #expect(FileManager.default.fileExists(atPath: files.csv.path))
        #expect(FileManager.default.fileExists(atPath: files.metadata.path))
    }

    private func writeRecording() throws -> RecordingFiles {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let stem = "NS_20261103-101500_ABCD1234_okn"
        let files = RecordingFiles(directory: dir,
                                   csv: dir.appendingPathComponent("\(stem).csv"),
                                   metadata: dir.appendingPathComponent("\(stem).json"))
        try Data("t_s,tracked\n0.000000,1\n".utf8).write(to: files.csv)
        try Data(#"{"schemaVersion":3,"note":"a/b \"quoted\""}"#.utf8).write(to: files.metadata)
        return files
    }
}
