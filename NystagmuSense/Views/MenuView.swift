//
//  MenuView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct MenuView: View {
    @EnvironmentObject private var vm: MenuViewModel
    @AppStorage(ExperimentLog.idKey) private var experimentID = ""

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
                        Text("Experiment")
                        TextField("P02", text: $experimentID)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled()
                            .frame(width: 90)
                            .textFieldStyle(.roundedBorder)
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

    /// Re-read on every render, so it updates after each recording.
    private var nextTrialLabel: String {
        let log = ExperimentLog()
        let id = ExperimentLog.sanitized(experimentID)
        return "\(id)_\(RecordingName.trialLabel(log.nextTrialNumber(for: id)))"
    }
}
