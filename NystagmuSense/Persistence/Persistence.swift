//
//  Persistence.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
import CoreData

//
//  PersistenceController.swift
//  NystagmuSense
//
//  Central Core-Data stack + in-memory preview instance.
//

import CoreData

// MARK: - Main Core-Data stack
final class PersistenceController: ObservableObject {

    /// Singleton for on-device use.
    static let shared = PersistenceController()

    /// NSPersistentContainer exposed to SwiftUI via `.environment(\.managedObjectContext, …)`.
    let container: NSPersistentContainer

    /// Designated initialiser.
    /// - Parameter inMemory: `true` → store lives only in RAM (for previews/tests).
    init(inMemory: Bool = false) {
        container = NSPersistentContainer(name: "NystagmuSense")

        if inMemory {
            // Write to /dev/null so nothing hits disk.
            container.persistentStoreDescriptions.first?.url = .init(fileURLWithPath: "/dev/null")
        }

        container.loadPersistentStores { _, error in
            if let error {
                fatalError("Core Data failed to load: \(error)")
            }
        }

        // Merge-by-property wins on conflict (good default for local apps).
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
    }
}

// MARK: - SwiftUI / XCTest Preview helper
extension PersistenceController {

    /// Throw-away, in-memory Core-Data stack seeded with one dummy `TestResult`
    /// so SwiftUI Canvas & previews render instantly.
    static let preview: PersistenceController = {
        let pc  = PersistenceController(inMemory: true)
        let ctx = pc.container.viewContext

        // Seed a sample test result
        let r          = TestResult(context: ctx)
        r.id           = UUID()
        r.date         = .now
        r.score        = 1.25
        r.shadeLevel   = 42.0
        r.duration     = 60.0

        try? ctx.save()
        return pc
    }()
}
