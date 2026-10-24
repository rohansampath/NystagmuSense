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
        TimelineView(.animation(minimumInterval: 1.0 / 120.0)) { _ in
            Canvas { ctx, size in
                let elapsed = startTime.map { CACurrentMediaTime() - $0 } ?? 0

                // 1. Background
                ctx.fill(Path(CGRect(origin: .zero, size: size)),
                         with: .color(Color(white: engine.backgroundGray(at: elapsed))))

                // 2. Stripes
                let w = engine.stripeWidth(viewWidth: size.width)
                for x in engine.stripePositions(at: elapsed, viewWidth: size.width) {
                    ctx.fill(Path(CGRect(x: x, y: 0, width: w, height: size.height)),
                             with: .color(.black))
                }
            }
        }
        .ignoresSafeArea()
    }
}
