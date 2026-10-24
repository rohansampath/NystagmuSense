//
//  TestResults.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import CoreData

// MARK: - Core-Data entity
@objc(TestResult)
public final class TestResult: NSManagedObject {
    @NSManaged public var id:         UUID
    @NSManaged public var date:       Date
    @NSManaged public var score:      Double
    @NSManaged public var shadeLevel: Double
    @NSManaged public var duration:   Double
}
extension TestResult: Identifiable {}

// MARK: - Strongly typed fetch request
extension TestResult {
    /// `context.fetch(TestResult.request)` → `[TestResult]`
    @nonobjc
    public class func fetchRequest() -> NSFetchRequest<TestResult> {
        NSFetchRequest<TestResult>(entityName: "TestResult")
    }
}
