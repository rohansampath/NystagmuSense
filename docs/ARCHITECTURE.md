# NystagmuSense architecture

Status: recording MVP. The app shows the moving-stripe stimulus, records ~10 s of
raw ARKit eye-tracking data, and exports it as CSV + JSON. **It does not detect
OKN or compute any clinical score.**

## Layout

```text
NystagmuSense/
├── App/                      NystagmuSenseApp (entry), ContentView (unused root wrapper)
├── Views/                    SwiftUI only: Menu, Countdown, Test, History
│   └── Components/           FadingStripeView (renders stimulus), RecordingStatusCard, ScoreCard (legacy)
├── ViewModels/               Menu, Countdown, History, TestViewModel (session coordinator)
├── Models/                   EyeMovementSample (raw gaze), StimulusConfig
├── Services/
│   ├── EyeTracking/          GazeProvider protocol, ARKitGazeProvider (sole ARSession owner)
│   ├── Stimulus/             StimulusEngine (pure stimulus maths)
│   ├── Recording/            SessionRecorder (CSV export), SessionMetadata (JSON sidecar, DeviceInfo)
│   └── Analysis/             LEGACY, unvalidated: OKNAnalyzer, EyeMovementDetector, ScoreCalculator
├── Persistence/              Core Data stack + TestResult entity (legacy score history)
├── Networking/APIClient.swift  unused placeholder (api.example.com); not called anywhere
└── Utils/PipeForward.swift
scripts/plot_gaze.py          offline plotting of exported recordings
NystagmuSenseTests/           Swift Testing unit tests + MockGazeProvider
```

## Data flow

```text
MenuView ("Record 10 Seconds") → TestView        (CountdownOverlay currently unused)
                                        │ owns
                                        ▼
                                 TestViewModel  (coordinator, @MainActor)
                    ┌──────────────┼───────────────────┐
                    ▼              ▼                   ▼
            GazeProvider     StimulusEngine      SessionRecorder
          (ARKitGazeProvider)  (pure maths)    (samples → CSV/JSON)
                    │              ▲                   │
   EyeMovementSample┘              │ snapshot(at: t)   ▼
                                   └──────────── Documents/Recordings/<stem>/
                                                       │ ShareLink / Files app
                                                       ▼
                                              scripts/plot_gaze.py
```

Rules:

- Views never touch ARKit or do maths. `FadingStripeView` asks `StimulusEngine`
  what to draw at the current time; `TestView` renders `TestViewModel.phase`.
- Only `ARKitGazeProvider` imports ARKit. The old `EyeTrackingView` (an
  `ARSCNView` whose session was never run) was removed, so there is exactly one
  `ARSession`.
- `SessionRecorder` and `StimulusEngine` are value types with no UI, ARKit or
  Core Data dependency, so they're unit-tested without a device.
- Recording doesn't depend on any analysis code.

## Session lifecycle (`TestViewModel.phase`)

```text
idle ──start()──▶ starting ──first frame──▶ recording ──10 s timer / finish()──▶ finished(summary)
                     │                          │                                └▶ failed (0 samples / write error)
                     ├─ unsupported / permission / startup timeout (5 s) ──▶ failed
                     ├─ app leaves foreground ─▶ failed  (during recording: finish() with partial data)
                     └─ cancel() (view disappears) ──────────────────────────▶ cancelled (nothing saved)
```

- `start()` and `finish()` are guarded by phase, so repeated `onAppear`
  calls and timer/error races can't start two sessions or export twice.
- `sessionWasInterrupted` during recording is noted in the sidecar's `issues`
  and recording continues (the gap shows up in the data). `didFailWithError`
  ends the session early and saves what was captured, with the error in `issues`.
- Leaving the screen (`onDisappear`) or tapping Cancel stops the camera and
  discards the partial session.

## Timestamps and synchronisation

- One reference: `t0 = CACurrentMediaTime()` when the **first ARKit frame is
  delivered**. Both the stimulus animation and the sample timeline use it.
  Before that, the stimulus shows its static t = 0 frame.
- `ARFrame.timestamp` and `CACurrentMediaTime()` share the system-uptime
  (monotonic) clock, so `t_s = ARFrame.timestamp − t0`. Wall-clock `Date` is
  only stored in metadata for humans.
- Samples with `t_s < 0` (the first frame, captured just before `t0`) or
  `t_s > duration` are dropped and counted in `droppedOutsideWindowCount`.
- `stim_*` columns are the state **scheduled** for `t_s`
  (`StimulusEngine.snapshot(at:)`), not a confirmed displayed frame. Not
  compensated: display latency (≈1–2 refreshes), camera exposure and ARKit
  processing latency, and the gap between TimelineView's target date and actual
  draw time. Treat cross-stream alignment as ±~50 ms until it's measured.

## Raw data model

`EyeMovementSample` holds only what ARKit reports, in face-anchor coordinates
(+x = subject's left, +y up, +z out of the face):

| field | source | units |
|---|---|---|
| `timestamp` | `ARFrame.timestamp` | s, uptime clock |
| `isTracked` | `ARFaceAnchor.isTracked` (false if no anchor) | bool |
| `lookAtPoint` | `ARFaceAnchor.lookAtPoint` | m |
| `left/rightEyeDirection` | normalised z-axis of `left/rightEyeTransform` | unitless |
| `blinkLeft/Right` | `blendShapes[.eyeBlinkLeft/Right]` | 0 open … 1 closed |

There are no confidence scores (ARKit doesn't provide any) and no angles in degrees
(no calibration yet). Untracked frames, and frames with non-finite estimates, keep
their timestamp but have nil measurements, so stale or NaN values never get exported.
Blink coefficients are exported but don't affect validity. The CSV schema is documented
in each sidecar's `columns` key and in the README.

> The previous implementation recorded `eyeTransform.columns.3`, which is the
> eye's *position* in the face and barely changes with gaze. Velocities and
> OKN decisions derived from it weren't meaningful.

## Future OKN detection (integration point)

Input: `[RecordedSample]` (from `SessionRecorder.samples`) or the exported CSV.
Each sample has `t`, the raw `EyeMovementSample`, and the scheduled
`StimulusSnapshot`. Planned pipeline, as pure Swift functions or structs in
`Services/Analysis/` (no SwiftUI, ARKit or Core Data):

```text
[RecordedSample] → preprocess (dropouts, blinks, resample?) → velocity (e.g. Savitzky–Golay)
  → slow/fast phase classification → OKN events → tracking onset/offset → threshold estimation
```

Prototype offline in Python on exported CSVs first, then port the validated
algorithm. Wire it in by having `TestViewModel.finish()` pass
`recorder.samples` to the analyser *after* export, so a failed or absent
analysis never blocks data capture.

`OKNAnalyzer`, `EyeMovementDetector` and `ScoreCalculator` are kept for
reference only. They aren't called anywhere, and `ScoreCalculator`'s output
(log of background shade) isn't a contrast-sensitivity measurement.

## Adding devices / gaze sources

Implement `GazeProvider` (e.g. a Vision-framework or external-tracker provider,
or a VR-headset configuration) and inject it with
`TestViewModel(provider:)`. If a source reports different quantities, add
optional fields to `EyeMovementSample` and columns to `SessionRecorder.csvColumns`
and `SessionMetadata.columnDescriptions`, then bump `schemaVersion`.
Per-device calibration profiles would sit between the provider and the
analysis, never inside the recorder (the CSV stays raw).

## Persistence

Core Data (`TestResult`) holds legacy score history only and is untouched apart
from switching entity code generation to *Manual/None*. The hand-written
`TestResult` class was clashing with Xcode's auto-generated one. Raw recordings are
plain files, not Core Data.
