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
    @AppStorage(ExperimentLog.contrastKey) private var contrastCode = -1

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
                    if selection.testType.usesContrast {
                        // Pilot 05: regular OKN only; the experimenter picks the nominal contrast.
                        Picker("Contrast", selection: contrast) {
                            ForEach(NominalContrast.allCases) { Text($0.label).tag(Optional($0)) }
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 360)
                    } else {
                        Picker("Condition", selection: $vm.trialMode) {
                            Text("OKN").tag(StimulusConfig.TrialMode.okn)
                            Text("Dot + moving").tag(StimulusConfig.TrialMode.fixationMovingStripes)
                            Text("Dot + still").tag(StimulusConfig.TrialMode.fixationStillStripes)
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 330)
                    }
                    if trialMode == .fixationStillStripes {
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
                    Text(selection.missingChoice ?? "Next: \(nextTrialLabel)")
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
                TestView(mode: trialMode, direction: vm.direction, selection: selection)
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

    private var contrast: Binding<NominalContrast?> {
        Binding(get: { NominalContrast(rawValue: contrastCode) },
                set: { contrastCode = $0?.rawValue ?? -1 })
    }

    private var selection: TrialSelection {
        TrialSelection(testType: TestType(rawValue: testTypeCode) ?? .general,
                       participant: Participant(rawValue: participantCode),
                       contrast: NominalContrast(rawValue: contrastCode))
    }

    /// Pilot 05 trials are always regular OKN, whatever the condition picker last held.
    private var trialMode: StimulusConfig.TrialMode {
        selection.testType.usesContrast ? .okn : vm.trialMode
    }

    /// The saved name without its timestamp. Re-read on every render, so it
    /// updates after each recording.
    private var nextTrialLabel: String {
        let name = RecordingName(experimentID: selection.testType.code,
                                 participantID: selection.participant?.rawValue,
                                 trialNumber: ExperimentLog().nextTrialNumber,
                                 stimulus: TestView.stimulusConfig(mode: trialMode, direction: vm.direction,
                                                                   selection: selection),
                                 startedAt: Date())
        return name.label
    }
}
