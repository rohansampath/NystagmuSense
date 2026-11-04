//
//  RecordingUploader.swift
//  NystagmuSense
//
//  Sends an exported recording (CSV + JSON) to scripts/receive_recordings.py
//  on a Mac over local Wi-Fi. Runs only after the local export has succeeded
//  and never touches the local copy. Independent of ARKit and the stimulus.
//

import Foundation

/// Mac receiver address and shared token, entered on the Mac Transfer screen.
/// Kept in UserDefaults on the phone, never in the repository.
struct TransferSettings: Equatable {
    var serverURL = ""
    var token = ""

    private static let urlKey   = "transfer.serverURL"
    private static let tokenKey = "transfer.token"

    static func load(from defaults: UserDefaults = .standard) -> TransferSettings {
        TransferSettings(serverURL: defaults.string(forKey: urlKey) ?? "",
                         token: defaults.string(forKey: tokenKey) ?? "")
    }

    func save(to defaults: UserDefaults = .standard) {
        defaults.set(serverURL, forKey: Self.urlKey)
        defaults.set(token, forKey: Self.tokenKey)
    }

    /// True when the user has filled anything in; empty means "local only".
    var isEnabled: Bool {
        !serverURL.trimmingCharacters(in: .whitespaces).isEmpty || !token.isEmpty
    }

    /// The receiver's base URL, accepted only for a plain `http://host:port`
    /// on the local network (the only hosts App Transport Security allows here).
    var baseURL: URL? {
        var text = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.contains("://") { text = "http://" + text }
        guard let components = URLComponents(string: text),
              components.scheme == "http",
              let host = components.host, Self.isLocalHost(host),
              components.path.isEmpty || components.path == "/",
              components.query == nil, components.user == nil
        else { return nil }
        return components.url
    }

    /// Private IPv4 ranges, link-local, loopback and Bonjour `.local` names.
    static func isLocalHost(_ host: String) -> Bool {
        let h = host.lowercased()
        if h == "localhost" || h.hasSuffix(".local") { return true }
        let parts = h.split(separator: ".", omittingEmptySubsequences: false)
        let octets = parts.compactMap { UInt8($0) }
        guard parts.count == 4, octets.count == 4 else { return false }
        switch (octets[0], octets[1]) {
        case (10, _), (127, _), (192, 168), (169, 254), (172, 16...31): return true
        default:                                                      return false
        }
    }
}

enum UploadError: Error, Equatable, LocalizedError {
    case invalidAddress
    case missingToken
    case unauthorized
    case conflict
    case unreachable(String)
    case server(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidAddress:
            return "Enter the Mac's local address, e.g. http://192.168.1.20:8765."
        case .missingToken:
            return "Enter the upload token shown on the Mac."
        case .unauthorized:
            return "The Mac rejected the upload token."
        case .conflict:
            return "The Mac already has a different recording with this name."
        case .unreachable(let reason):
            return "Couldn't reach the Mac (\(reason)). Check the server is running with --lan and both devices are on the same Wi-Fi."
        case .server(let code, let message):
            return "The Mac returned HTTP \(code)\(message.isEmpty ? "" : ": \(message)")."
        }
    }
}

protocol RecordingUploading {
    func upload(_ files: RecordingFiles) async throws
}

struct RecordingUploader: RecordingUploading {
    let settings: TransferSettings
    var session: URLSession = .shared

    static let timeout: TimeInterval = 15
    static let tokenHeader = "X-Upload-Token"

    /// The uploader for the saved settings, or nil when transfer isn't set up.
    static func fromSavedSettings() -> RecordingUploading? {
        let settings = TransferSettings.load()
        return settings.isEnabled ? RecordingUploader(settings: settings) : nil
    }

    /// Succeeds only if the server is reachable *and* accepts the token.
    func checkHealth() async throws {
        try await send(request(path: "health"))
    }

    /// Succeeds only after the Mac confirms both files are written.
    func upload(_ files: RecordingFiles) async throws {
        try await send(uploadRequest(for: files))
    }

    func uploadRequest(for files: RecordingFiles) throws -> URLRequest {
        let payload = Payload(stem: files.csv.deletingPathExtension().lastPathComponent,
                              csv: try String(contentsOf: files.csv, encoding: .utf8),
                              json: try String(contentsOf: files.metadata, encoding: .utf8))
        var request = try request(path: "upload")
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(payload)
        return request
    }

    // MARK: - Private

    private struct Payload: Encodable {
        let stem: String
        let csv: String
        let json: String
    }

    private func request(path: String) throws -> URLRequest {
        guard let base = settings.baseURL else { throw UploadError.invalidAddress }
        guard !settings.token.isEmpty else { throw UploadError.missingToken }
        var request = URLRequest(url: base.appendingPathComponent(path), timeoutInterval: Self.timeout)
        request.setValue(settings.token, forHTTPHeaderField: Self.tokenHeader)
        return request
    }

    private func send(_ request: URLRequest) async throws {
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw UploadError.unreachable(error.localizedDescription)
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        switch status {
        case 200..<300: return
        case 401:       throw UploadError.unauthorized
        case 409:       throw UploadError.conflict
        default:
            let message = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? ""
            throw UploadError.server(status, message)
        }
    }
}
