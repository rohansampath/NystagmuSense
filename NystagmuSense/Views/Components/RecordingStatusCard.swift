//
//  RecordingStatusCard.swift
//  NystagmuSense
//
//  Small overlay showing recording progress / outcome and the export button.
//

import SwiftUI

struct RecordingStatusCard: View {
    let phase: TestViewModel.Phase
    let isLandscape: Bool
    let faceTracked: Bool
    let trackedCount: Int
    let duration: TimeInterval
    let stimulus: StimulusConfig
    let canRetryExport: Bool
    let canTryAgain: Bool
    let onStart: () -> Void
    let onRetryExport: () -> Void
    let onTryAgain: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            switch phase {
            case .idle:
                Label(isLandscape ? "Ready to record" : "Rotate your phone sideways",
                      systemImage: "iphone.gen3.landscape")
                    .font(.headline)
                Text(isLandscape
                     ? stimulus.participantInstruction
                     : "Landscape mode is required. If the screen won't rotate, turn off Portrait Orientation Lock.")
                Button("Start Recording", action: onStart)
                    .buttonStyle(.borderedProminent)
                    .disabled(!isLandscape)
                Button("Cancel", action: onClose)

            case .starting:
                Text("Finding your face…")
                Text("Keep your face visible to the front camera.")
                Button("Cancel", action: onClose)

            case .recording:
                HStack(spacing: 16) {
                    Text("Recording \(Int(duration)) s").font(.headline)
                    Label(faceTracked ? "Face tracked" : "Face not detected",
                          systemImage: faceTracked ? "eye" : "eye.slash")
                        .foregroundStyle(faceTracked ? .green : .red)
                    Text("\(trackedCount) tracked").monospacedDigit()
                    Button("Cancel", action: onClose)
                }

            case .finished(let s):
                Text("Recording saved").font(.headline)
                Text("\(s.sampleCount) samples (\(s.trackedCount) with face tracked)")
                if let hz = s.sampleRateHz {
                    Text(String(format: "Observed rate %.1f Hz", hz))
                }
                if s.trackedCount == 0 {
                    Text("Warning: no face was detected.").foregroundStyle(.red)
                }
                ForEach(s.issues, id: \.self) { Text($0).foregroundStyle(.orange) }
                HStack {
                    ShareLink(items: [s.files.csv, s.files.metadata]) {
                        Label("Export", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.borderedProminent)
                    Button("Done", action: onClose).buttonStyle(.bordered)
                }

            case .failed(let message):
                Text("Recording failed").font(.headline)
                Text(message).foregroundStyle(.red)
                HStack {
                    if canRetryExport {
                        Button("Retry Export", action: onRetryExport).buttonStyle(.borderedProminent)
                    }
                    if canTryAgain {
                        Button("Try Again", action: onTryAgain).buttonStyle(.borderedProminent)
                    }
                    Button("Done", action: onClose).buttonStyle(.bordered)
                }

            case .cancelled:
                EmptyView()
            }
        }
        .font(.callout)
        .padding(12)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
