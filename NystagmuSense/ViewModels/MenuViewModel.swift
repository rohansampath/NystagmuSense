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
    /// Mode for the next recording; set by the menu button that starts it.
    @Published var trialMode: StimulusConfig.TrialMode = .okn

    func startRecording(_ mode: StimulusConfig.TrialMode) {
        trialMode     = mode
        showCountdown = true
    }
}
 
