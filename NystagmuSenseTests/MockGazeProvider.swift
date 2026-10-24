//
//  MockGazeProvider.swift
//  NystagmuSenseTests
//
//  Test-only provider. Samples it emits are synthetic fixtures, never
//  experimental data.
//

@testable import NystagmuSense

final class MockGazeProvider: GazeProvider {
    var isSupported = true
    var errorOnStart: GazeTrackingError?
    var onSample: ((EyeMovementSample) -> Void)?
    var onError: ((GazeTrackingError) -> Void)?
    private(set) var startCount = 0
    private(set) var stopCount = 0

    func start() {
        startCount += 1
        if let errorOnStart { onError?(errorOnStart) }
    }

    func stop() { stopCount += 1 }

    func emit(_ s: EyeMovementSample) { onSample?(s) }
    func fail(_ e: GazeTrackingError) { onError?(e) }
}

enum Fixture {
    static func tracked(at t: Double, x: Float = 0.1) -> EyeMovementSample {
        EyeMovementSample(timestamp: t, isTracked: true,
                          lookAtPoint: [x, 0.02, 0.5],
                          leftEyeDirection: [x, 0, 1],
                          rightEyeDirection: [x, 0, 1])
    }
}
