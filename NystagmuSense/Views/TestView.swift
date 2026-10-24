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
        stimulus
            .overlay(alignment: .top) {
                RecordingStatusCard(phase: vm.phase,
                                    faceTracked: vm.faceTracked,
                                    duration: vm.duration,
                                    onClose: close)
                    .padding()
            }
            .onAppear {
                UIApplication.shared.isIdleTimerDisabled = true
                vm.start()
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
        case .finished, .failed, .cancelled:
            Color(.systemBackground).ignoresSafeArea()
        default:
            FadingStripeView(engine: vm.stimulus, startTime: vm.stimulusStartTime)
        }
    }

    /// Pops back to the menu.
    private func close() {
        vm.cancel()
        menu.showCountdown = false
    }
}
