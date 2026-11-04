//
//  ExperimentNaming.swift
//  NystagmuSense
//
//  Descriptive recording names and the persistent per-experiment trial counter.
//

import Foundation

/// `{experiment}_{trial}_{MODE}_{DIRECTION}_{UTC yyyyMMdd_HHmmss}`,
/// e.g. `P02_T001_OKN_RIGHT_20261104_143022`. Built only from the trial's own
/// settings (never inferred from gaze); CSV and JSON share it as their stem.
struct RecordingName: Equatable {
    let experimentID: String
    let trialNumber: Int
    let mode: StimulusConfig.TrialMode
    /// Nil when the stripes never move (written as NONE).
    let direction: StimulusConfig.Direction?
    let startedAt: Date

    init(experimentID: String, trialNumber: Int, stimulus: StimulusConfig, startedAt: Date) {
        self.experimentID = experimentID
        self.trialNumber  = trialNumber
        self.mode         = stimulus.trialMode
        self.direction    = stimulus.isMoving ? stimulus.direction : nil
        self.startedAt    = startedAt
    }

    var stem: String {
        let dir: String
        switch direction {
        case .rightward: dir = "RIGHT"
        case .leftward:  dir = "LEFT"
        case nil:        dir = "NONE"
        }
        return "\(experimentID)_\(Self.trialLabel(trialNumber))_\(mode.nameCode)_\(dir)_\(Self.utc.string(from: startedAt))"
    }

    static func trialLabel(_ n: Int) -> String { "T" + String(format: "%03d", n) }

    private static let utc: DateFormatter = {
        let f = DateFormatter()
        f.locale     = Locale(identifier: "en_US_POSIX")
        f.timeZone   = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyyMMdd_HHmmss"
        return f
    }()
}

/// Experiment ID (entered once on the menu) and a trial counter per experiment,
/// in UserDefaults on the phone so they survive app restarts.
struct ExperimentLog {
    static let idKey = "experiment.id"
    static let defaultID = "EXP"

    let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    /// Upper-case letters, digits and "-" (underscores separate name fields),
    /// at most 16 characters; blank becomes `EXP`.
    static func sanitized(_ raw: String) -> String {
        let kept = raw.uppercased().filter { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }
        return kept.isEmpty ? defaultID : String(kept.prefix(16))
    }

    var experimentID: String { Self.sanitized(defaults.string(forKey: Self.idKey) ?? "") }

    func nextTrialNumber(for experimentID: String) -> Int {
        max(1, defaults.integer(forKey: counterKey(experimentID)))
    }

    /// Hands out the next number and persists the increment at once, so a
    /// number is never reused, whatever happens to that recording afterwards.
    func reserveTrialNumber(for experimentID: String) -> Int {
        let n = nextTrialNumber(for: experimentID)
        defaults.set(n + 1, forKey: counterKey(experimentID))
        return n
    }

    private func counterKey(_ id: String) -> String { "experiment.nextTrial.\(id)" }
}
