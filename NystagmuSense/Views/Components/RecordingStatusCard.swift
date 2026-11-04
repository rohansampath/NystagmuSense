//
//  RecordingStatusCard.swift
//  NystagmuSense
//
//  Small overlay showing recording progress / outcome, Mac upload status and
//  the export button.
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
    let upload: TestViewModel.UploadStatus?
    let positioning: DistanceGate.Status
    let onCheckPosition: () -> Void
    let onStart: () -> Void
    let onStartWithoutCheck: () -> Void
    let onRetryExport: () -> Void
    let onRetryUpload: () -> Void
    let onTryAgain: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            switch phase {
            case .idle:
                Label(isLandscape ? "Ready to record" : "Rotate your phone sideways",
                      systemImage: "iphone.gen3.landscape")
                    .font(.headline)
                Text(stimulus.trialMode.displayName).foregroundStyle(.secondary)
                Text(isLandscape
                     ? stimulus.participantInstruction
                     : "Landscape mode is required. If the screen won't rotate, turn off Portrait Orientation Lock.")
                Button("Check Position", action: onCheckPosition)
                    .buttonStyle(.borderedProminent)
                    .disabled(!isLandscape)
                Button("Cancel", action: onClose)

            case .positioning:
                Label(positioning.message,
                      systemImage: positioning.isReady ? "checkmark.circle.fill" : "ruler")
                    .font(.headline)
                    .foregroundStyle(positioning.isReady ? .green : positioning == .noFace ? .red : .orange)
                Text("Hold the phone about \(Int(DistanceGate.recommendedCm.lowerBound))–\(Int(DistanceGate.recommendedCm.upperBound)) cm from your eyes (approximate ARKit camera-to-eye distance, uncalibrated).")
                    .font(.caption)
                HStack {
                    Button("Start Trial", action: onStart)
                        .buttonStyle(.borderedProminent)
                        .disabled(!positioning.isReady)
                    Button("Cancel", action: onClose)
                }
                Button("Start without distance check (development)", action: onStartWithoutCheck)
                    .font(.caption)

            case .starting:
                Text("Finding your face…")
                Text("Keep your face visible to the front camera.")
                Button("Cancel", action: onClose)

            case .recording:
                HStack(spacing: 16) {
                    Text("Recording \(Int(duration)) s").font(.headline)
                    Text(stimulus.trialMode.displayName)
                    Label(faceTracked ? "Face tracked" : "Face not detected",
                          systemImage: faceTracked ? "eye" : "eye.slash")
                        .foregroundStyle(faceTracked ? .green : .red)
                    Text("\(trackedCount) tracked").monospacedDigit()
                    Button("Cancel", action: onClose)
                }

            case .finished(let s):
                Text("Recording saved").font(.headline)
                Text(s.files.csv.deletingPathExtension().lastPathComponent)
                    .font(.caption.monospaced())
                Text("\(s.sampleCount) samples (\(s.trackedCount) with face tracked)")
                if let hz = s.sampleRateHz {
                    Text(String(format: "Observed rate %.1f Hz", hz))
                }
                if s.trackedCount == 0 {
                    Text("Warning: no face was detected.").foregroundStyle(.red)
                }
                ForEach(s.issues, id: \.self) { Text($0).foregroundStyle(.orange) }
                if let upload { uploadStatus(upload) }
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

    @ViewBuilder private func uploadStatus(_ status: TestViewModel.UploadStatus) -> some View {
        switch status {
        case .notConfigured:
            Label("Saved locally (Mac transfer not set up)", systemImage: "iphone")
        case .uploading:
            Label("Saved locally · Uploading to Mac…", systemImage: "arrow.up.circle")
        case .uploaded:
            Label("Uploaded to Mac", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
        case .failed(let message):
            Label("Upload failed: saved locally", systemImage: "exclamationmark.triangle")
                .foregroundStyle(.orange)
            Text(message).font(.caption)
            Button("Retry Upload", action: onRetryUpload).buttonStyle(.bordered)
        }
    }
}
