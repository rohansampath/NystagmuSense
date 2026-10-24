//
//  CountdownOverlay.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct CountdownOverlay: View {
    @StateObject private var vm = CountdownViewModel()
    @State private var go = false
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            Text("\(vm.seconds)")
                .font(.system(size: 100, weight: .bold))
                .foregroundColor(.white)
        }
        .onAppear { vm.start() }
        .onChange(of: vm.seconds) { _, s in if s <= 0 { go = true } }
        .navigationDestination(isPresented: $go) { TestView() }
    }
}
