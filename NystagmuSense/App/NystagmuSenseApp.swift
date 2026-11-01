import SwiftUI

@main
struct NystagmuSenseApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
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
