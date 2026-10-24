//
//  HistoryView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import SwiftUI

struct HistoryView: View {
    @StateObject private var vm = HistoryViewModel()
    var body: some View {
        List {
            Section {
                ForEach(vm.results) { r in
                    HStack {
                        VStack(alignment: .leading) {
                            Text(r.date, style: .date)
                            Text(r.date, style: .time).font(.caption2)
                        }
                        Spacer()
                        Text(String(format: "%.2f", r.score)).monospacedDigit()
                    }
                }
            } footer: {
                Text("Legacy scores from the earlier prototype. Not clinically validated. New recordings are saved as files in Files › NystagmuSense › Recordings.")
            }
        }
        .navigationTitle("Past Tests")
        .onAppear { vm.refresh() }
        .onReceive(NotificationCenter.default.publisher(
                   for: .NSManagedObjectContextDidSave)) { _ in vm.refresh() }
    }
}
