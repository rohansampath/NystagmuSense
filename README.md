# NystagmuSense

---

Swift Application that can test Contrast Sensitivity Function.

Optokinetic nystagmus is a reflex of the nervous system when a person is tracking an object
across their visual field. This tracking leads to abnormal movement of the eyes, a smooth tracking
followed by a series of twitches in the contralateral direction. This phenomenon can be induced by
physical stimuli, opening doors for potential uses in an optometry clinic. One potential use can be seen in
measuring someone’s contrast sensitivity function, a robust, but often overlooked, marker of visual
function. The machine used to measure this function is a visual field machine, which is extremely costly
to maintain from a money and space perspective. Using a dynamic stimulus on a smartphone, we can
induce an optokinetic reflex in the user, and using eye tracking, measure the exact point they are no longer
induced. Advances in camera technology, specifically on mobile phones, have allowed for eye tracking to
become a viable method to do this. The app then takes the moment when the user stops tracking the
phone and compares it with the luminance value of the screen before. This value is from 1 to 100, and
after taking the common log of that value, it directly correlates to the user’s expected contrast sensitivity
function.

---
##### Reach out to rrs248@cornell.edu for access - Heuristic Signalling Algorithm under development
---

## Current status

> **Research prototype. Not clinically validated. It produces no diagnostic or
> contrast-sensitivity score.**

| Component | Status |
|---|---|
| Menu → **Record 10 Seconds** → test screen | Works. The 30 s countdown screen is skipped for Deliverable 1 (`CountdownOverlay` kept, unused) |
| Moving, fading stripe stimulus | Works. Logic moved to `StimulusEngine`, same appearance |
| 10 s raw ARKit eye-tracking recording | Implemented, **not yet verified on a physical iPhone** |
| CSV + JSON export (share sheet / Files app) | Implemented, **not yet verified on device** |
| Python plotting (`scripts/plot_gaze.py`) | Works on CSVs from the real exporter (tested with synthetic data) |
| OKN detection | **Not implemented.** Legacy heuristic kept in `Services/Analysis/`, disabled |
| Contrast-sensitivity score | **Removed from the test flow.** "Past Tests" shows only legacy prototype scores |

Architecture, timing and data-model details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
The full research roadmap is in [NYSTAGMUSENSE_PROJECT_SPEC.md](NYSTAGMUSENSE_PROJECT_SPEC.md);
only Deliverable 1 (10 s recording + export + plot) is implemented.

## Requirements

- Xcode 16.4+ with the iOS 18.5 platform installed (deployment target is iOS 18.5)
- An iPhone/iPad with a TrueDepth (Face ID) front camera. ARKit face tracking
  doesn't run in the Simulator, which can only show the "unsupported device" path.
- No third-party dependencies. Apple frameworks only: SwiftUI, ARKit, Core Data.
- Plotting: Python 3.9+ and `matplotlib` (`pip install -r scripts/requirements.txt`)

## Build and run on an iPhone

1. Open `NystagmuSense.xcodeproj`.
2. Under *Signing & Capabilities* for the `NystagmuSense` target, pick your team
   (the project currently points at team `L5VAJVH6AP`). If signing complains about
   the iCloud/Push entitlements, remove those capabilities locally; the app
   doesn't use them.
3. Connect the iPhone, select it as the run destination, and press ⌘R.
4. Accept the camera permission prompt on first use.

## Record 10 seconds

1. Put the phone on a stand at a comfortable viewing distance, in portrait, with
   your face fully visible in good light. Tap **Record 10 Seconds**.
2. The stripe stimulus appears with a status card at the top. "Starting camera…"
   switches to **Recording 10 s** once the first camera frame arrives. That's
   when the stimulus starts moving and t = 0.
3. Watch the stripes. The card shows *Face tracked* or *Face not detected* live.
4. After ~10 s the stimulus disappears and the card shows **Recording saved** with
   sample count and observed rate. **Cancel** (or leaving the screen) discards the
   recording. If the app leaves the foreground mid-recording, it stops and saves the
   partial data, with the reason in the sidecar's `issues`. Zero tracked samples counts as a
   failed capture even though the file is saved.

## Export

- Tap **Export** on the result card to AirDrop, Save to Files, email, etc.
  (sends `NS_<date>_<id>.csv` and `.json`), **or**
- open *Files › On My iPhone › NystagmuSense › Recordings/*, **or**
- in Finder, select the iPhone › Files › NystagmuSense.

## Plot

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python3 scripts/plot_gaze.py path/to/NS_20261024-101500_ABCD1234.csv
# → prints stats, writes NS_..._ABCD1234.png next to the CSV (or --out file.png)
```

The plot shows raw, uncalibrated horizontal signals (left/right eye direction x,
lookAtPoint x) against time, with untracked periods shaded. It doesn't classify
OKN. Interpret it by eye. It refuses empty, malformed, or time-decreasing files
rather than reordering or interpolating.

## CSV format (schema v1)

| column | meaning | units |
|---|---|---|
| `t_s` | time since session start (monotonic) | s |
| `host_time_s` | `ARFrame.timestamp` (system uptime clock) | s |
| `tracked` | 1 if `ARFaceAnchor.isTracked`, else 0 (gaze fields then empty) | – |
| `lookat_{x,y,z}_m` | `ARFaceAnchor.lookAtPoint`, face-anchor coords | m |
| `left_dir_{x,y,z}`, `right_dir_{x,y,z}` | unit z-axis of each eye transform, face-anchor coords | unitless |
| `blink_left`, `blink_right` | `eyeBlinkLeft/Right` blend-shape coefficient, 0 open … 1 closed (not used to reject samples) | – |
| `stim_bg_gray` | scheduled background grey, sRGB code value 0–1 (not luminance) | – |
| `stim_displacement_pt` | scheduled cumulative stripe displacement (+ = rightward) | SwiftUI points |

Face-anchor coordinates: +x toward the subject's left, +y up, +z out of the face.
The `.json` sidecar has session ID, device model, iOS version, sample counts,
observed rate, stimulus settings, column definitions, and any capture issues.

## Tests

```bash
# Swift unit tests (needs an installed iOS Simulator runtime)
xcodebuild test -project NystagmuSense.xcodeproj -scheme NystagmuSense \
  -destination 'platform=iOS Simulator,name=iPhone 16'

# Python script tests (stdlib only)
python3 -m unittest discover scripts/tests
```

## Known limitations

- Nothing in the recording path has run on a physical device yet. The eye-direction
  sign convention, real sample rate (ARKit face tracking is nominally 60 Hz), and
  `lookAtPoint` behaviour still need to be checked.
- Signals are raw ARKit model outputs in face coordinates. There's no calibration,
  no conversion to degrees of visual angle, and head movement isn't removed
  (head pose isn't recorded yet).
- Stimulus/gaze alignment uses the *scheduled* stimulus state. Display and camera
  latency aren't measured or compensated.
- Stimulus speed and stripe size are in screen points, so not physically
  standardised across devices. Screen brightness isn't controlled.
- The grating isn't shown until the first camera frame arrives (static before
  that), so the first ~0.5–1 s after tapping is not part of the session.
