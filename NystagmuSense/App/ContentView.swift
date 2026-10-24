//
//  ContentView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//
//
//  ContentView.swift
//  NystagmuSense
//
//  Root view that simply hosts the MenuView.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        MenuView()                     // our actual entry screen
            .navigationBarHidden(true) // remove default nav chrome
    }
}

#Preview {
    ContentView()
        .environment(
            \.managedObjectContext,
             PersistenceController.preview.container.viewContext
        )
        .environmentObject(MenuViewModel())
}
