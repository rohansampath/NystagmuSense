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
                                    canRetryExport: vm.canRetryExport,
                                    onStart: vm.start,
                                    onRetryExport: vm.retryExport,
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
            UIApplication.shared.isIdleTimerDisabled = false
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { vm.appBecameInactive() }
        }
        .toolbar(.hidden, for: .navigationBar)
    }

    /// Stripes while capturing; a plain background once the session has ended.
    @ViewBuilder private var stimulus: some View {
        switch vm.phase {
        case .idle, .starting, .finished, .failed, .cancelled:
            Color(.systemBackground).ignoresSafeArea()
        case .recording:
            FadingStripeView(engine: vm.stimulus, startTime: vm.stimulusStartTime)
        }
    }

    /// Pops back to the menu.
    private func close() {
        vm.cancel()
        menu.showCountdown = false
    }
}
