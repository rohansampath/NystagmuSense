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

/// Serialized: the HTTP stub below is shared state.
@Suite(.serialized)
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

    @Test func serverNotRunningIsReportedAsReceiverUnavailable() async throws {
        let files = try writeRecording()
        // Nothing listens on port 1.
        let uploader = RecordingUploader(settings: TransferSettings(serverURL: "127.0.0.1:1", token: "t"))
        do {
            try await uploader.upload(files)
            Issue.record("expected an error")
        } catch let error as UploadError {
            #expect(error == .receiverUnavailable)
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

    // MARK: - Receiver responses → errors (stubbed HTTP, no network)

    func stubbedUploader(status: Int, body: String) -> RecordingUploader {
        StubProtocol.response = (status, Data(body.utf8))
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubProtocol.self]
        return RecordingUploader(settings: TransferSettings(serverURL: "192.168.1.20:8765", token: "t"),
                                 session: URLSession(configuration: config))
    }

    @Test(arguments: [
        (400, #"{"error":"invalid recording name","code":"invalid_name"}"#,
         UploadError.rejectedName("NS_20261103-101500_ABCD1234_okn")),
        // PR #9-era receivers send no code; their name rejection is still recognised.
        (400, #"{"error":"invalid recording name"}"#, UploadError.rejectedName("NS_20261103-101500_ABCD1234_okn")),
        (401, #"{"error":"invalid upload token","code":"unauthorized"}"#, UploadError.unauthorized),
        (409, #"{"error":"a different recording with this name already exists","code":"conflict"}"#, UploadError.conflict),
        (400, #"{"error":"metadata is not valid JSON","code":"malformed"}"#, UploadError.server(400, "metadata is not valid JSON")),
        (500, #"{"error":"could not write files on the Mac","code":"write_failed"}"#,
         UploadError.server(500, "could not write files on the Mac")),
        (502, "not json", UploadError.server(502, "")),
    ])
    func receiverResponsesMapToDistinctErrors(_ status: Int, _ body: String, _ expected: UploadError) async throws {
        let files = try writeRecording()
        await #expect(throws: expected) {
            try await stubbedUploader(status: status, body: body).upload(files)
        }
        #expect(FileManager.default.fileExists(atPath: files.csv.path))     // local copy untouched
    }

    @Test func healthReportsWhetherTheReceiverKnowsTheNameContract() async throws {
        let current = try await stubbedUploader(status: 200, body: #"{"status":"ok","name_contract":1}"#).checkHealth()
        #expect(current.acceptsThisAppsNames)
        let old = try await stubbedUploader(status: 200, body: #"{"status":"ok"}"#).checkHealth()
        #expect(old.nameContract == nil && !old.acceptsThisAppsNames)
    }

    @Test func networkFailuresAreNotReportedAsMissingReceiver() {
        #expect(UploadError.from(URLError(.cannotConnectToHost)) == .receiverUnavailable)
        if case .network = UploadError.from(URLError(.timedOut)) {} else { Issue.record("timeout should be network") }
        if case .network = UploadError.from(URLError(.notConnectedToInternet)) {} else { Issue.record("offline should be network") }
    }
}

/// Answers every request with a fixed status and body.
final class StubProtocol: URLProtocol {
    nonisolated(unsafe) static var response: (Int, Data) = (200, Data())
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let (status, body) = Self.response
        let http = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: http, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
