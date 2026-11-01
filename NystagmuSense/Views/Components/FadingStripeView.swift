//
//  FadingStripeView.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//

import QuartzCore
import SwiftUI

/// Renders the moving-stripe stimulus. All maths lives in `StimulusEngine`;
/// this view only draws the state at the current time.
struct FadingStripeView: View {
    let engine: StimulusEngine
    /// Stimulus onset on the system-uptime clock (`CACurrentMediaTime()`).
    /// `nil` → render the static t = 0 frame.
    let startTime: TimeInterval?

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 120.0, paused: startTime == nil)) { timeline in
            // Read the timeline outside Canvas so its drawing closure receives a
            // new value every frame. Map the scheduled date to the uptime clock
            // shared by the recorder (rather than accumulating frame deltas).
            let uptime = CACurrentMediaTime() + timeline.date.timeIntervalSinceNow
            let elapsed = startTime.map { max(0, uptime - $0) } ?? 0
            let background = engine.backgroundGray(at: elapsed)
            Canvas { ctx, size in
                // 1. Background
                ctx.fill(Path(CGRect(origin: .zero, size: size)),
                         with: .color(Color(white: background)))

                // 2. Stripes
                let w = engine.stripeWidth(viewWidth: size.width)
                for x in engine.stripePositions(at: elapsed, viewWidth: size.width) {
                    ctx.fill(Path(CGRect(x: x, y: 0, width: w, height: size.height)),
                             with: .color(Color(white: engine.config.stripeGray)))
                }

                // 3. Fixation dot (control trials): on top, centred, never moves.
                //    The dark outline keeps it visible over white stripes too.
                if let dot = engine.fixationDotRect(in: size) {
                    let circle = Path(ellipseIn: dot)
                    ctx.fill(circle, with: .color(.red))
                    ctx.stroke(circle, with: .color(Color(white: 0.1)),
                               lineWidth: CGFloat(StimulusConfig.fixationDotOutlinePoints))
                }
            }
        }
        .ignoresSafeArea()
    }
}
