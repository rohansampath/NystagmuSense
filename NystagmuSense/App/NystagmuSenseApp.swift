import SwiftUI

@main
struct NystagmuSenseApp: App {
    @StateObject private var persistence = PersistenceController.shared
    @StateObject private var menuVM      = MenuViewModel()

    var body: some Scene {
        WindowGroup {
            MenuView()
                .environment(\.managedObjectContext, persistence.container.viewContext)
                .environmentObject(menuVM)
        }
    }
}
