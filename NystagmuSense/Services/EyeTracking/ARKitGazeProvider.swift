//
//  ARKitGazeProvider.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//  Sole owner of the ARSession / TrueDepth camera in the app.
//

import ARKit
import AVFoundation

final class ARKitGazeProvider: NSObject, GazeProvider, ARSessionDelegate {
    var onSample: ((EyeMovementSample) -> Void)?
    var onError: ((GazeTrackingError) -> Void)?

    private let session = ARSession()

    var isSupported: Bool { ARFaceTrackingConfiguration.isSupported }

    func start() {
        guard isSupported else { onError?(.unsupportedDevice); return }

        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .denied, .restricted:
            onError?(.cameraPermissionDenied); return
        default:
            break   // .notDetermined: ARKit shows the system prompt on run
        }

        let cfg = ARFaceTrackingConfiguration()
        cfg.isWorldTrackingEnabled = false
        session.delegate = self          // delegateQueue nil → main thread
        session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
    }

    func stop() { session.pause() }

    // MARK: - ARSessionDelegate

    func session(_ s: ARSession, didUpdate frame: ARFrame) {
        guard let face = frame.anchors.compactMap({ $0 as? ARFaceAnchor }).first,
              face.isTracked else {
            onSample?(.untracked(at: frame.timestamp))
            return
        }
        onSample?(EyeMovementSample(
            timestamp:         frame.timestamp,
            isTracked:         true,
            lookAtPoint:       face.lookAtPoint,
            leftEyeDirection:  Self.direction(of: face.leftEyeTransform),
            rightEyeDirection: Self.direction(of: face.rightEyeTransform)
        ))
    }

    func session(_ s: ARSession, didFailWithError error: Error) {
        if let arError = error as? ARError, arError.code == .cameraUnauthorized {
            onError?(.cameraPermissionDenied)
        } else {
            onError?(.sessionFailed(error.localizedDescription))
        }
    }

    func sessionWasInterrupted(_ s: ARSession) { onError?(.interrupted) }

    /// z-axis basis vector of an eye transform (unit length, face coordinates).
    private static func direction(of t: simd_float4x4) -> SIMD3<Float> {
        simd_normalize(SIMD3(t.columns.2.x, t.columns.2.y, t.columns.2.z))
    }
}
