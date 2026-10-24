//
//  GazeProvider.swift
//  NystagmuSense
//
//  Hardware-agnostic interface for eye-tracking sources. Views and
//  view models depend on this, never on ARKit directly.
//

import Foundation

enum GazeTrackingError: Error, Equatable, LocalizedError {
    case unsupportedDevice
    case cameraPermissionDenied
    case sessionFailed(String)
    case interrupted
    case noFramesReceived

    var errorDescription: String? {
        switch self {
        case .unsupportedDevice:
            return "This device does not support face tracking (TrueDepth camera required)."
        case .cameraPermissionDenied:
            return "Camera access is denied. Enable it in Settings › NystagmuSense."
        case .sessionFailed(let reason):
            return "Face tracking failed: \(reason)"
        case .interrupted:
            return "Face tracking was interrupted (app backgrounded or camera in use)."
        case .noFramesReceived:
            return "Face tracking did not start: no camera frames were received."
        }
    }
}

/// A source of timestamped gaze samples.
///
/// Callbacks are delivered on the main thread. A provider never fabricates
/// samples: frames without a tracked face are reported with `isTracked == false`.
protocol GazeProvider: AnyObject {
    var isSupported: Bool { get }
    var onSample: ((EyeMovementSample) -> Void)? { get set }
    var onError: ((GazeTrackingError) -> Void)? { get set }

    /// Reports `.cameraPermissionDenied` / `.unsupportedDevice` via `onError` if it cannot start.
    func start()
    func stop()
}
