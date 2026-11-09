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
    @AppStorage(ExperimentLog.participantKey) private var participantCode = ""

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
                    if selection.testType.requiresParticipant {
                        Picker("Participant", selection: participant) {
                            ForEach(selection.testType.participants) { Text($0.rawValue).tag(Optional($0)) }
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 70 * CGFloat(selection.testType.participants.count) + 80)
                    }
                    Picker("Condition", selection: $vm.trialMode) {
                        Text("OKN").tag(StimulusConfig.TrialMode.okn)
                        Text("Dot + moving").tag(StimulusConfig.TrialMode.fixationMovingStripes)
                        Text("Dot + still").tag(StimulusConfig.TrialMode.fixationStillStripes)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 330)
                    if vm.trialMode == .fixationStillStripes {
                        Text("Direction: none (still stripes)").font(.subheadline).foregroundStyle(.secondary)
                            .frame(height: 32)
                    } else {
                        Picker("Stripe direction", selection: $vm.direction) {
                            Text("← Left").tag(StimulusConfig.Direction.leftward)
                            Text("Right →").tag(StimulusConfig.Direction.rightward)
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 220)
                    }
                    Text(selection.isComplete ? "Next: \(nextTrialLabel)" : "Choose the participant")
                        .font(.caption.monospaced())
                        .foregroundStyle(selection.isComplete ? Color.secondary : Color.red)
                }
                Button("Record 10 Seconds")  { vm.startRecording() }
                    .buttonStyle(.borderedProminent)
                    .disabled(!selection.isComplete)
                Button("Mac Transfer")  { vm.showTransfer = true }
                Spacer()
            }
            .navigationDestination(isPresented: $vm.showHistory)   { HistoryView() }
            .navigationDestination(isPresented: $vm.showCountdown) {
                TestView(mode: vm.trialMode, direction: vm.direction, selection: selection)
            }
            .navigationDestination(isPresented: $vm.showTransfer)  { TransferSettingsView() }
        }
    }

    private var testType: Binding<TestType> {
        Binding(get: { TestType(rawValue: testTypeCode) ?? .general },
                set: { testTypeCode = $0.code })
    }

    private var participant: Binding<Participant?> {
        Binding(get: { Participant(rawValue: participantCode) },
                set: { participantCode = $0?.rawValue ?? "" })
    }

    private var selection: TrialSelection {
        TrialSelection(testType: TestType(rawValue: testTypeCode) ?? .general,
                       participant: Participant(rawValue: participantCode))
    }

    /// The saved name without its timestamp. Re-read on every render, so it
    /// updates after each recording.
    private var nextTrialLabel: String {
        let name = RecordingName(experimentID: selection.testType.code,
                                 participantID: selection.participant?.rawValue,
                                 trialNumber: ExperimentLog().nextTrialNumber,
                                 stimulus: StimulusConfig(mode: vm.trialMode, direction: vm.direction),
                                 startedAt: Date())
        return "\(name.testField)_\(RecordingName.trialLabel(name.trialNumber))_\(name.mode.nameCode)_\(name.directionCode)"
    }
}
