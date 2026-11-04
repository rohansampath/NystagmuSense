//
//  TransferSettingsView.swift
//  NystagmuSense
//
//  Mac receiver address + upload token, and a connection check against
//  scripts/receive_recordings.py. Leaving both empty keeps recordings local only.
//

import SwiftUI

struct TransferSettingsView: View {
    @State private var settings = TransferSettings.load()
    @State private var testing = false
    @State private var result: (ok: Bool, message: String)?

    var body: some View {
        Form {
            Section {
                TextField("http://192.168.1.20:8765", text: $settings.serverURL)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Upload token", text: $settings.token)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            } header: {
                Text("Mac receiver")
            } footer: {
                Text("On the Mac, run scripts/receive_recordings.py --lan. Both devices must be on the same Wi-Fi. Leave empty to keep recordings on this iPhone only.")
            }

            Section {
                Button(testing ? "Testing…" : "Test Connection", action: testConnection)
                    .disabled(testing)
                if let result {
                    Label(result.message, systemImage: result.ok ? "checkmark.circle.fill" : "xmark.octagon")
                        .foregroundStyle(result.ok ? .green : .red)
                }
            } footer: {
                Text("The first time, iOS asks to find devices on your local network. Allow it, then test again.")
            }
        }
        .navigationTitle("Mac Transfer")
        .onChange(of: settings) { _, new in
            new.save()
            result = nil
        }
    }

    private func testConnection() {
        testing = true
        result = nil
        let uploader = RecordingUploader(settings: settings)
        Task {
            do {
                try await uploader.checkHealth()
                result = (true, "Connected. The Mac accepted the token.")
            } catch {
                result = (false, error.localizedDescription)
            }
            testing = false
        }
    }
}
