//
//  StimulusConfig.swift
//  NystagmuSense
//
//  Parameters of the moving-stripe stimulus. Defaults reproduce the
//  original FadingStripeView exactly.
//

import Foundation

struct StimulusConfig: Codable, Equatable {
    enum Direction: String, Codable { case rightward, leftward }

    /// Stripe width as a fraction of the view width (min 1 pt).
    var stripeWidthRatio: Double = 0.02
    /// Stripe pitch (period) as a multiple of the stripe width.
    var pitchToWidthRatio: Double = 2.4
    /// Stripe drift speed in SwiftUI points per second (not physical pixels).
    var speedPointsPerSecond: Double = 90
    var direction: Direction = .rightward
    /// Seconds for the background to fade white → black (then back).
    var fadeHalfCycleSeconds: Double = 30
}
