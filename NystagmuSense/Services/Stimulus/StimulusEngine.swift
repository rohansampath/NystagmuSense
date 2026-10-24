//
//  StimulusEngine.swift
//  NystagmuSense
//
//  Pure, deterministic stimulus maths. Given the time elapsed since stimulus
//  onset it returns what *should* be on screen; FadingStripeView only draws it.
//

import CoreGraphics
import Foundation

/// Size-independent stimulus state, suitable for logging alongside gaze samples.
struct StimulusSnapshot: Equatable {
    /// Background grey level, 0 (black) … 1 (white), as an sRGB-encoded
    /// `Color(white:)` value — NOT photometric luminance.
    let backgroundGray: Double
    /// Cumulative stripe displacement since onset, points (+ = rightward).
    let displacementPoints: Double

    /// Legacy "shade" scale used by the old score: 0 (white) … 100 (black).
    var shadePercent: Double { (1 - backgroundGray) * 100 }
}

struct StimulusEngine {
    let config: StimulusConfig

    init(config: StimulusConfig = StimulusConfig()) { self.config = config }

    func snapshot(at elapsed: TimeInterval) -> StimulusSnapshot {
        StimulusSnapshot(backgroundGray: backgroundGray(at: elapsed),
                         displacementPoints: displacement(at: elapsed))
    }

    /// Triangle wave: white → black over one half-cycle, then back.
    func backgroundGray(at elapsed: TimeInterval) -> Double {
        let phase = (max(0, elapsed) / config.fadeHalfCycleSeconds)
            .truncatingRemainder(dividingBy: 2)
        return phase <= 1 ? 1 - phase : phase - 1
    }

    func displacement(at elapsed: TimeInterval) -> Double {
        let sign: Double = config.direction == .rightward ? 1 : -1
        return sign * config.speedPointsPerSecond * max(0, elapsed)
    }

    // MARK: - Geometry for rendering

    func stripeWidth(viewWidth: CGFloat) -> CGFloat {
        max(1, viewWidth * CGFloat(config.stripeWidthRatio))
    }

    func pitch(viewWidth: CGFloat) -> CGFloat {
        stripeWidth(viewWidth: viewWidth) * CGFloat(config.pitchToWidthRatio)
    }

    /// Left edges of every stripe to draw. Starts a few pitches off-screen so
    /// the wrap-around is invisible.
    func stripePositions(at elapsed: TimeInterval, viewWidth: CGFloat) -> [CGFloat] {
        let p = pitch(viewWidth: viewWidth)
        var offset = CGFloat(displacement(at: elapsed)).truncatingRemainder(dividingBy: p)
        if offset < 0 { offset += p }

        var xs: [CGFloat] = []
        var x = -3 * p + offset
        while x < viewWidth + p {
            xs.append(x)
            x += p
        }
        return xs
    }
}
