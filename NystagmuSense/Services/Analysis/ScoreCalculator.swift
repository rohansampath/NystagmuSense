//
//  ScoreCalculator.swift
//  NystagmuSense
//
//  Created by Rohan Sampath on 6/30/25.
//
//
//  LEGACY / UNVALIDATED — log-scaled background shade, not a measured
//  contrast-sensitivity score. Not used by the recording MVP; kept only so
//  historical Core Data results remain interpretable.
//
import Foundation
struct ScoreCalculator {
    func score(fromShade s: Double) -> Double {
        guard s > 0 else { return 0 }
        return log10(s) / log10(100) * 2
    }
}

