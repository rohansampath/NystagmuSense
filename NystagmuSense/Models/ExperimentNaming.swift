//
//  ExperimentNaming.swift
//  NystagmuSense
//
//  Test types, descriptive recording names and the persistent trial counter.
//

import Foundation

/// Predefined development/pilot test types. The code is the first field of
/// every recording name. It labels *why* a trial was recorded; it does not
/// change the stimulus (mode and direction are chosen separately).
enum TestType: String, CaseIterable, Identifiable {
    case general         = "DEV"
    case gazeValidation  = "GAZE"
    case blink           = "BLINK"
    case oknDetection    = "OKNTEST"
    case direction       = "DIR"
    case fixationControl = "FIX"
    case distance        = "DIST"
    case pilot02         = "P02"
    case pilot03         = "P03"

    var id: String { rawValue }
    var code: String { rawValue }

    var displayName: String {
        switch self {
        case .general:         return "General Test"
        case .gazeValidation:  return "Gaze Validation"
        case .blink:           return "Blink Test"
        case .oknDetection:    return "OKN Detection"
        case .direction:       return "Direction Test"
        case .fixationControl: return "Fixation Control"
        case .distance:        return "Distance Test"
        case .pilot02:         return "Pilot 02"
        case .pilot03:         return "Pilot 03"
        }
    }

    /// Pilot 03 recordings must say who was recorded; no recording starts without it.
    var requiresParticipant: Bool { self == .pilot03 }

    /// Pilot 03 keeps a constant white background (black bars, full contrast)
    /// instead of the default white → black fade. Nil keeps the fade.
    var fixedBackgroundGray: Double? { self == .pilot03 ? 1 : nil }
}

/// Pseudonymous participant codes. Names are never stored on the phone.
enum Participant: String, CaseIterable, Identifiable {
    case p01 = "P01"
    case p02 = "P02"

    var id: String { rawValue }
}

/// Everything about a trial chosen on the menu before it starts. Captured
/// once when the trial screen opens, so a later menu change can't relabel it.
struct TrialSelection: Equatable {
    let testType: TestType
    /// Only kept for test types that need one.
    let participant: Participant?

    init(testType: TestType, participant: Participant?) {
        self.testType = testType
        self.participant = testType.requiresParticipant ? participant : nil
    }

    var isComplete: Bool { !testType.requiresParticipant || participant != nil }
}

/// File-name contract, version 1, shared with scripts/receive_recordings.py
/// (STEM_RE) and checked on both sides against
/// scripts/tests/fixtures/recording_names.json:
///
///     {TEST}_T{trial ≥3 digits}_{OKN|FIXMOVE|FIXSTILL}_{RIGHT|LEFT|NONE}_{UTC yyyyMMdd_HHmmss}
///
/// e.g. `DIR_T001_OKN_RIGHT_20261104_143022`. TEST is upper-case letters,
/// digits or "-", 1–16 characters: the test-type code, followed by
/// `-{participant}` when the trial has one (`P03-P01_T041_OKN_LEFT_…`).
/// Built only from the trial's own settings (never inferred from gaze); the
/// folder, CSV and JSON share it.
struct RecordingName: Equatable {
    /// Bump together with the receiver's NAME_CONTRACT when the format changes.
    static let contractVersion = 1

    let experimentID: String
    /// Pseudonymous code such as P01; nil for test types without participants.
    let participantID: String?
    let trialNumber: Int
    let mode: StimulusConfig.TrialMode
    /// Nil when the stripes never move (written as NONE).
    let direction: StimulusConfig.Direction?
    let startedAt: Date

    init(experimentID: String, participantID: String? = nil, trialNumber: Int, stimulus: StimulusConfig,
         startedAt: Date) {
        self.experimentID  = experimentID
        self.participantID = participantID
        self.trialNumber   = trialNumber
        self.mode         = stimulus.trialMode
        self.direction    = stimulus.isMoving ? stimulus.direction : nil
        self.startedAt    = startedAt
    }

    /// First field of the stem: `P03-P01`, or just the code without a participant.
    var testField: String { participantID.map { "\(experimentID)-\($0)" } ?? experimentID }

    /// Direction field of the stem; NONE when the stripes never move.
    var directionCode: String {
        switch direction {
        case .rightward: return "RIGHT"
        case .leftward:  return "LEFT"
        case nil:        return "NONE"
        }
    }

    var stem: String {
        "\(testField)_\(Self.trialLabel(trialNumber))_\(mode.nameCode)_\(directionCode)_\(Self.utc.string(from: startedAt))"
    }

    static func trialLabel(_ n: Int) -> String {
        let digits = String(n)
        return "T" + String(repeating: "0", count: max(0, 3 - digits.count)) + digits
    }

    private static let utc: DateFormatter = {
        let f = DateFormatter()
        f.locale     = Locale(identifier: "en_US_POSIX")
        f.timeZone   = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyyMMdd_HHmmss"
        return f
    }()
}

/// Selected test type, participant and one trial counter shared by all test
/// types (so numbers follow recording order on this phone), in UserDefaults
/// so they survive app restarts.
struct ExperimentLog {
    static let testTypeKey = "experiment.testType"
    static let participantKey = "experiment.participant"
    private static let nextTrialKey = "recording.nextTrial"
    /// Per-experiment counters written by the earlier free-text ID version.
    private static let legacyCounterPrefix = "experiment.nextTrial."

    let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    var testType: TestType { TestType(rawValue: defaults.string(forKey: Self.testTypeKey) ?? "") ?? .general }

    /// Last participant chosen on the menu; nil until one is picked.
    var participant: Participant? { Participant(rawValue: defaults.string(forKey: Self.participantKey) ?? "") }

    var selection: TrialSelection { TrialSelection(testType: testType, participant: participant) }

    /// The number the next saved recording gets. Never below any number already
    /// used on this phone, including by the earlier per-experiment counters.
    var nextTrialNumber: Int {
        let legacy = defaults.dictionaryRepresentation()
            .filter { $0.key.hasPrefix(Self.legacyCounterPrefix) }
            .compactMap { $0.value as? Int }
        return max(1, defaults.integer(forKey: Self.nextTrialKey), legacy.max() ?? 0)
    }

    /// Called once `trial` has been saved locally (upload success not
    /// required). The counter only moves forward, so a saved number is never
    /// handed out again.
    func commitTrialNumber(_ trial: Int) {
        defaults.set(max(nextTrialNumber, trial + 1), forKey: Self.nextTrialKey)
    }
}
