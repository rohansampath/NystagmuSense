//
//  MenuView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct MenuView: View {
    @EnvironmentObject private var vm: MenuViewModel
    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()
                Text("NystagmuSense").font(.largeTitle.bold())
                Spacer()
                Button("Past Tests")  { vm.showHistory   = true }
                    .buttonStyle(.borderedProminent)
                Button("Record 10 Seconds")  { vm.startRecording(.okn) }
                    .buttonStyle(.bordered)
                VStack(spacing: 12) {
                    Button("Control: Dot + Moving Stripes") { vm.startRecording(.fixationMovingStripes) }
                    Button("Control: Dot + Still Stripes")  { vm.startRecording(.fixationStillStripes) }
                }
                .buttonStyle(.bordered)
                Spacer()
            }
            .navigationDestination(isPresented: $vm.showHistory)   { HistoryView() }
            .navigationDestination(isPresented: $vm.showCountdown) { TestView(mode: vm.trialMode) }
        }
    }
}
