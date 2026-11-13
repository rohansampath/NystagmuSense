//
//  TestView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct TestView: View {
    @StateObject private var vm: TestViewModel
    @EnvironmentObject private var menu: MenuViewModel
    @Environment(\.scenePhase) private var scenePhase

    init(mode: StimulusConfig.TrialMode = .okn, direction: StimulusConfig.Direction = .rightward,
         selection: TrialSelection = ExperimentLog().selection) {
        _vm = StateObject(wrappedValue:
            TestViewModel(stimulus: StimulusEngine(config: Self.stimulusConfig(mode: mode, direction: direction,
                                                                               selection: selection)),
                          selection: selection))
    }

    /// The stimulus a trial with this menu selection shows. Pilot 05 is always
    /// regular OKN at the chosen nominal contrast; the other pilots keep their
    /// fixed background.
    static func stimulusConfig(mode: StimulusConfig.TrialMode, direction: StimulusConfig.Direction,
                               selection: TrialSelection) -> StimulusConfig {
        if selection.testType.usesContrast {
            var config = StimulusConfig(mode: .okn, direction: direction)
            if let contrast = selection.contrast { config.applyNominalContrast(contrast) }
            return config
        }
        var config = StimulusConfig(mode: mode, direction: direction)
        config.fixedBackgroundGray = selection.testType.fixedBackgroundGray
        return config
    }

    /// Contrast trials hide the status card while recording, so nothing but the
    /// grating is on screen (at 0 % nothing visible moves). It returns when the
    /// trial ends.
    private var showsStatusCard: Bool {
        if case .recording = vm.phase, vm.stimulus.config.michelsonContrast != nil { return false }
        return true
    }

    var body: some View {
        GeometryReader { geometry in
            let surface = CGSize(
                width: geometry.size.width + geometry.safeAreaInsets.leading + geometry.safeAreaInsets.trailing,
                height: geometry.size.height + geometry.safeAreaInsets.top + geometry.safeAreaInsets.bottom)
            stimulus
            .overlay(alignment: .top) {
                if showsStatusCard {
                RecordingStatusCard(phase: vm.phase,
                                    isLandscape: vm.isLandscape,
                                    faceTracked: vm.faceTracked,
                                    trackedCount: vm.trackedCount,
                                    duration: vm.duration,
                                    stimulus: vm.stimulus.config,
                                    canRetryExport: vm.canRetryExport,
                                    canTryAgain: vm.canTryAgain,
                                    upload: vm.upload,
                                    positioning: vm.positioning,
                                    onCheckPosition: vm.startPositioning,
                                    onStart: { vm.start() },
                                    onStartWithoutCheck: { vm.start(bypassDistanceCheck: true) },
                                    onRetryExport: vm.retryExport,
                                    onRetryUpload: vm.retryUpload,
                                    onTryAgain: vm.tryAgain,
                                    onClose: close)
                    .padding()
                }
            }
            .onChange(of: surface, initial: true) { _, size in
                vm.updateViewport(width: Double(size.width), height: Double(size.height))
            }
        }
        .onAppear {
            UIApplication.shared.isIdleTimerDisabled = true
        }
        .onDisappear {
            vm.cancel()
            OrientationLock.release()
            UIApplication.shared.isIdleTimerDisabled = false
        }
        .onChange(of: scenePhase) { _, phase in
            vm.scenePhaseChanged(phase)
        }
        .onChange(of: vm.phase) { _, phase in
            // Pin the landscape side for the whole capture; free it afterwards.
            switch phase {
            case .positioning, .starting, .recording: OrientationLock.holdCurrentLandscape()
            default:                    OrientationLock.release()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
    }

    /// Before onset, the static t = 0 frame (same luminance as the moving
    /// stimulus, so motion onset isn't also a brightness step); moving stripes
    /// while recording; a plain background once the session has ended.
    @ViewBuilder private var stimulus: some View {
        switch vm.phase {
        case .idle, .positioning, .starting:
            FadingStripeView(engine: vm.stimulus, startTime: nil)
        case .recording:
            FadingStripeView(engine: vm.stimulus, startTime: vm.stimulusStartTime)
        case .finished, .failed, .cancelled:
            Color(.systemBackground).ignoresSafeArea()
        }
    }

    /// Pops back to the menu.
    private func close() {
        vm.cancel()
        menu.showCountdown = false
    }
}
