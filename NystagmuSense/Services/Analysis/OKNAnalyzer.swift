//
//  OKNAnalyzer.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//  LEGACY / UNVALIDATED heuristic, kept for later review. It is NOT called
//  by the recording MVP and its output must not be shown as a clinical result.
//
//  TODO(Milestone 2): replace with a pure pipeline over `[RecordedSample]`
//  (preprocess → velocity → slow/fast phase → OKN events → onset/offset).
//  See docs/ARCHITECTURE.md › "Future OKN detection".
//

import Foundation
struct OKNAnalyzer {
    private let window = 60, flipLimit = 2, speedLimit: Float = 5
    func isOptokineticLost(velocities v: [Float]) -> Bool {
        guard v.count >= window else { return false }
        let w = Array(v.suffix(window))
        let mean = w.reduce(0, +) / Float(w.count) |> abs
        let flips = zip(w, w.dropFirst()).filter { $0.0.sign != $0.1.sign }.count
        return flips < flipLimit || mean < speedLimit
    }
}
