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

    var body: some View {
        FadingStripeView(engine: vm.stimulus, startTime: vm.stimulusStartTime)
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
            .toolbar(.hidden, for: .navigationBar)
    }

    /// Pops back to the menu (skipping the countdown screen).
    private func close() {
        vm.cancel()
        menu.showCountdown = false
    }
}
