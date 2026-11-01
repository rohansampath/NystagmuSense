//
//  TestView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct TestView: View {
    @StateObject private var vm = TestViewModel()
    @EnvironmentObject private var menu: MenuViewModel
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        GeometryReader { geometry in
            let surface = CGSize(
                width: geometry.size.width + geometry.safeAreaInsets.leading + geometry.safeAreaInsets.trailing,
                height: geometry.size.height + geometry.safeAreaInsets.top + geometry.safeAreaInsets.bottom)
            stimulus
            .overlay(alignment: .top) {
                RecordingStatusCard(phase: vm.phase,
                                    isLandscape: vm.isLandscape,
                                    faceTracked: vm.faceTracked,
                                    trackedCount: vm.trackedCount,
                                    duration: vm.duration,
                                    stimulus: vm.stimulus.config,
                                    canRetryExport: vm.canRetryExport,
                                    canTryAgain: vm.canTryAgain,
                                    onStart: vm.start,
                                    onRetryExport: vm.retryExport,
                                    onTryAgain: vm.tryAgain,
                                    onClose: close)
                    .padding()
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
            case .starting, .recording: OrientationLock.holdCurrentLandscape()
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
        case .idle, .starting:
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
