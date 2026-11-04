//
//  NystagmuSenseUITests.swift
//  NystagmuSenseUITests
//
//  Created by Rohan Sampath on 6/30/25.
//

import XCTest

final class NystagmuSenseUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testRecordingRequiresLandscape() throws {
        XCUIDevice.shared.orientation = .portrait
        defer { XCUIDevice.shared.orientation = .portrait }
        let app = XCUIApplication()
        app.launch()
        app.buttons["Record 10 Seconds"].tap()
        let start = app.buttons["Check Position"]
        XCTAssertTrue(start.waitForExistence(timeout: 5))
        XCTAssertFalse(start.isEnabled)
        XCTAssertTrue(app.staticTexts["Rotate your phone sideways"].exists)

        XCUIDevice.shared.orientation = .landscapeLeft
        let enabled = NSPredicate(format: "enabled == true")
        expectation(for: enabled, evaluatedWith: start)
        waitForExpectations(timeout: 5)

        XCUIDevice.shared.orientation = .portrait
        let disabled = NSPredicate(format: "enabled == false")
        expectation(for: disabled, evaluatedWith: start)
        waitForExpectations(timeout: 5)
        XCTAssertTrue(app.staticTexts["Rotate your phone sideways"].exists)
    }

    @MainActor
    func testExample() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
