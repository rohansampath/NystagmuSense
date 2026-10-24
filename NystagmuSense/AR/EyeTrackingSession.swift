import ARKit

final class EyeTrackingSession: NSObject, ARSessionDelegate {
    private let session = ARSession()
    var onSample: ((GazeSample) -> Void)?
    var onFailure: ((String) -> Void)?

    func start() {
        session.delegateQueue = .main
        session.delegate = self
        let configuration = ARFaceTrackingConfiguration()
        configuration.isWorldTrackingEnabled = false
        configuration.maximumNumberOfTrackedFaces = 1
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
    }

    func stop() {
        session.pause()
        session.delegate = nil
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        let face = frame.anchors.compactMap { $0 as? ARFaceAnchor }.first
        let point = face?.lookAtPoint
        let tracked = face?.isTracked == true
        let valid = tracked && point.map { $0.x.isFinite && $0.y.isFinite && $0.z.isFinite } == true
        onSample?(GazeSample(
            timestamp: frame.timestamp,
            x: valid ? point?.x : nil, y: valid ? point?.y : nil, z: valid ? point?.z : nil,
            faceTracked: tracked, valid: valid,
            blinkLeft: face?.blendShapes[.eyeBlinkLeft]?.floatValue,
            blinkRight: face?.blendShapes[.eyeBlinkRight]?.floatValue
        ))
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        onFailure?("ARKit failed: \(error.localizedDescription)")
    }

    func sessionWasInterrupted(_ session: ARSession) {
        onFailure?("ARKit was interrupted. Recording stopped; any saved data is partial.")
    }
}
