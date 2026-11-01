//
//  OrientationLock.swift
//  NystagmuSense
//
//  Runtime interface-orientation restriction. The app delegate reports `mask`
//  to UIKit; changing it asks the active window scene to re-evaluate.
//

import UIKit

@MainActor
enum OrientationLock {
    /// Matches the orientations declared in the target's Info settings.
    static var appDefault: UIInterfaceOrientationMask {
        UIDevice.current.userInterfaceIdiom == .pad ? .all : [.portrait, .landscapeLeft, .landscapeRight]
    }

    private(set) static var mask: UIInterfaceOrientationMask = appDefault

    /// Pins the current landscape side so neither a 180° flip nor a turn to
    /// portrait can rotate the stimulus mid-trial. No-op when not in landscape.
    static func holdCurrentLandscape() {
        switch windowScene?.interfaceOrientation {
        case .landscapeLeft:  restrict(to: .landscapeLeft)
        case .landscapeRight: restrict(to: .landscapeRight)
        default:              break
        }
    }

    static func release() { restrict(to: appDefault) }

    private static func restrict(to newMask: UIInterfaceOrientationMask) {
        guard newMask != mask else { return }
        mask = newMask
        guard let scene = windowScene else { return }
        scene.windows.first?.rootViewController?.setNeedsUpdateOfSupportedInterfaceOrientations()
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: newMask)) { error in
            // Not fatal: TestViewModel.updateViewport still ends a trial whose
            // stimulus surface changes (e.g. iPad multitasking ignores locks).
            print("OrientationLock: could not apply \(newMask.rawValue): \(error.localizedDescription)")
        }
    }

    private static var windowScene: UIWindowScene? {
        UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     supportedInterfaceOrientationsFor window: UIWindow?) -> UIInterfaceOrientationMask {
        OrientationLock.mask
    }
}
