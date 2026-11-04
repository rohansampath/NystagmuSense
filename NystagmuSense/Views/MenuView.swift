//
//  MenuView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct MenuView: View {
    @EnvironmentObject private var vm: MenuViewModel
    @AppStorage(ExperimentLog.testTypeKey) private var testTypeCode = TestType.general.code

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()
                Text("NystagmuSense").font(.largeTitle.bold())
                Spacer()
                Button("Past Tests")  { vm.showHistory   = true }
                    .buttonStyle(.borderedProminent)
                VStack(spacing: 8) {
                    HStack {
                        Text("Test Type")
                        Picker("Test Type", selection: testType) {
                            ForEach(TestType.allCases) { Text($0.displayName).tag($0) }
                        }
                        .pickerStyle(.menu)
                    }
                    Text("Next: \(nextTrialLabel)").font(.caption.monospaced()).foregroundStyle(.secondary)
                    Picker("Stripe direction", selection: $vm.direction) {
                        Text("← Left").tag(StimulusConfig.Direction.leftward)
                        Text("Right →").tag(StimulusConfig.Direction.rightward)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 220)
                    Text("Direction applies to moving stripes").font(.caption2).foregroundStyle(.secondary)
                }
                Button("Record 10 Seconds")  { vm.startRecording(.okn) }
                    .buttonStyle(.bordered)
                VStack(spacing: 12) {
                    Button("Control: Dot + Moving Stripes") { vm.startRecording(.fixationMovingStripes) }
                    Button("Control: Dot + Still Stripes")  { vm.startRecording(.fixationStillStripes) }
                }
                .buttonStyle(.bordered)
                Button("Mac Transfer")  { vm.showTransfer = true }
                Spacer()
            }
            .navigationDestination(isPresented: $vm.showHistory)   { HistoryView() }
            .navigationDestination(isPresented: $vm.showCountdown) {
                TestView(mode: vm.trialMode, direction: vm.direction)
            }
            .navigationDestination(isPresented: $vm.showTransfer)  { TransferSettingsView() }
        }
    }

    private var testType: Binding<TestType> {
        Binding(get: { TestType(rawValue: testTypeCode) ?? .general },
                set: { testTypeCode = $0.code })
    }

    /// Re-read on every render, so it updates after each recording.
    private var nextTrialLabel: String {
        let log = ExperimentLog()
        return "\(log.testType.code)_\(RecordingName.trialLabel(log.nextTrialNumber))"
    }
}
