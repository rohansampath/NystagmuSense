//
//  MenuViewModel.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import Foundation
@MainActor
final class MenuViewModel: ObservableObject {
    @Published var showHistory   = false
    @Published var showCountdown = false
    @Published var showTransfer  = false
    /// Condition for the next recording, chosen on the menu before it starts.
    @Published var trialMode: StimulusConfig.TrialMode = .okn
    /// Stripe direction for moving-stripe trials; Right keeps the original stimulus.
    @Published var direction: StimulusConfig.Direction = .rightward

    func startRecording() {
        showCountdown = true
    }
}
 
