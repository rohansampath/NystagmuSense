//
//  StimulusConfig.swift
//  NystagmuSense
//
//  Parameters of the moving-stripe stimulus.
//

import Foundation

struct StimulusConfig: Codable, Equatable {
    enum Direction: String, Codable { case rightward, leftward }

    /// Which trial is recorded. The fixation modes are controls for OKN trials:
    /// the subject holds gaze on a centred red dot drawn over the stripes.
    enum TrialMode: String, Codable, CaseIterable {
        case okn                    // moving stripes, no dot (default)
        case fixationMovingStripes  // same moving stripes + dot: how much OKN breaks through
        case fixationStillStripes   // same stripes, never moving + dot: still-eye baseline

        var showsFixationDot: Bool { self != .okn }

        /// Suffix for exported file names.
        var fileSuffix: String {
            switch self {
            case .okn:                   return "okn"
            case .fixationMovingStripes: return "fixmove"
            case .fixationStillStripes:  return "fixstill"
            }
        }

        var displayName: String {
            switch self {
            case .okn:                   return "OKN: moving stripes"
            case .fixationMovingStripes: return "Control: dot + moving stripes"
            case .fixationStillStripes:  return "Control: dot + still stripes"
            }
        }
    }

    /// Fixation dot geometry, SwiftUI points. Fixed for all fixation trials.
    static let fixationDotDiameterPoints: Double = 12
    static let fixationDotOutlinePoints: Double = 1.5

    /// Stripe width as a fraction of the view width (min 1 pt).
    var stripeWidthRatio: Double = 0.02
    /// Stripe pitch (period) as a multiple of the stripe width.
    var pitchToWidthRatio: Double = 2.4
    /// Stripe drift speed in SwiftUI points per second (not physical pixels).
    var speedPointsPerSecond: Double = 90
    var direction: Direction = .rightward
    /// Seconds for the background to fade white → black (then back).
    var fadeHalfCycleSeconds: Double = 30
    /// A fixed background keeps contrast visible throughout capture. Nil enables
    /// the legacy white → black fade for explicitly configured experiments.
    var fixedBackgroundGray: Double? = 0
    var stripeGray: Double = 1
    var trialMode: TrialMode = .okn

    init() {}

    /// Default stimulus for `mode`. Still-stripe trials record speed 0.
    init(mode: TrialMode) {
        trialMode = mode
        if mode == .fixationStillStripes { speedPointsPerSecond = 0 }
    }

    private enum CodingKeys: String, CodingKey {
        case stripeWidthRatio, pitchToWidthRatio, speedPointsPerSecond, direction
        case fadeHalfCycleSeconds, fixedBackgroundGray, stripeGray, trialMode
    }

    /// Old sidecars describe black stripes over a fading background.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        stripeWidthRatio = try c.decode(Double.self, forKey: .stripeWidthRatio)
        pitchToWidthRatio = try c.decode(Double.self, forKey: .pitchToWidthRatio)
        speedPointsPerSecond = try c.decode(Double.self, forKey: .speedPointsPerSecond)
        direction = try c.decode(Direction.self, forKey: .direction)
        fadeHalfCycleSeconds = try c.decode(Double.self, forKey: .fadeHalfCycleSeconds)
        fixedBackgroundGray = try c.decodeIfPresent(Double.self, forKey: .fixedBackgroundGray)
        stripeGray = try c.decodeIfPresent(Double.self, forKey: .stripeGray) ?? 0
        // Sidecars before schema 3 were all OKN trials.
        trialMode = try c.decodeIfPresent(TrialMode.self, forKey: .trialMode) ?? .okn
    }
}

extension StimulusConfig {
    /// What the participant is told to watch, derived from the configured stimulus.
    var participantInstruction: String {
        if trialMode.showsFixationDot {
            return "Keep your head still and keep looking at the red dot."
        }
        let bars: String
        switch stripeGray {
        case 0.9...:  bars = "white"
        case ..<0.1:  bars = "black"
        default:      bars = "grey"
        }
        let way = direction == .rightward ? "right" : "left"
        return "Keep your head still and watch the \(bars) bars move to the \(way)."
    }
}

/// Full stimulus surface in SwiftUI points, saved to reproduce stripe geometry.
struct StimulusViewport: Codable, Equatable {
    let widthPoints: Double
    let heightPoints: Double

    var isLandscape: Bool { widthPoints > heightPoints && heightPoints > 0 }
}
