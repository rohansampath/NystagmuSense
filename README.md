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
| Moving stripe stimulus | White bars on a fixed black background, gated on landscape and face tracking |
| 10 s raw ARKit eye-tracking recording | Implemented, **not yet verified on a physical iPhone** |
| CSV + JSON export (share sheet / Files app) | Implemented, **not yet verified on device** |
| Python plotting (`scripts/plot_gaze.py`) | Works on CSVs from the real exporter (tested with synthetic data) |
| OKN detection | **Candidate only, offline:** `scripts/detect_okn.py` (Savitzky–Golay baseline, tuned on synthetic data). Not in the app; legacy Swift heuristic in `Services/Analysis/` stays disabled |
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

1. Tap **Record 10 Seconds**, then rotate the phone into landscape. If the screen
   won't rotate, turn off Portrait Orientation Lock. **Start Recording** stays
   disabled until the app is displayed in landscape.
2. Keep your face fully visible to the front camera in good light, then tap
   **Start Recording**. The first time, iOS asks for camera access; this doesn't
   fail the session. From Start until the session ends, the screen is locked to the
   landscape side you're holding, so it can't rotate mid-trial. The static
   stimulus frame is already showing, and once a face is tracked the stimulus starts
   moving and the recording clock starts together.
3. Keep your head still and watch the white vertical bars move rightward over a
   fixed black background (90 SwiftUI points/s). The compact status card shows
   face-tracking status while leaving most of the stimulus visible.
4. After ~10 s, the stimulus disappears and **Recording saved** shows sample count
   and observed rate. Rotating or resizing the stimulus surface, or leaving the
   foreground, stops capture and saves partial data with a reason in `issues`.
   **Cancel** discards the recording. Failed exports offer **Retry Export**; other
   failures (no camera frames within 5 s, no face found within 5 s of the first
   frame, camera denied) offer **Try Again**. Backgrounding the app before a face
   is found returns to the Ready state.

The sidecar records the full stimulus surface size (`stimulusViewport`, in
points) and stripe/background grey levels, alongside speed, direction and spacing.
The default capture uses constant contrast; an explicitly configured experiment
can set `fixedBackgroundGray` to nil to enable the legacy background fade.
These changes support repeatable data collection; OKN detection remains disabled.

## Fixation-control trials

Two extra menu buttons run the same 10 s flow (landscape, start on the first
tracked frame, status card, export, cancel, retry) with a control stimulus. In
both, the subject keeps looking at a solid **red dot** (12 pt diameter, 1.5 pt dark
outline) fixed at the exact centre of the screen, drawn over the stripes for the
whole trial:

| Button | `stimulus.trialMode` | File suffix | Stripes | What it's for |
|---|---|---|---|---|
| **Record 10 Seconds** | `okn` | `_okn` | moving, no dot (unchanged) | the OKN trial |
| **Control: Dot + Moving Stripes** | `fixationMovingStripes` | `_fixmove` | same stripes and motion as `okn` | how much OKN breaks through while holding gaze on a fixed target |
| **Control: Dot + Still Stripes** | `fixationStillStripes` | `_fixstill` | same stripes, speed 0 (`stim_displacement_pt` stays 0) | baseline for what a still eye looks like to ARKit |

The status card shows the mode name while recording. `scripts/plot_gaze.py` and
`scripts/detect_okn.py` print the mode and add it to plot titles (`okn` if the
sidecar has none). Detection logic is the same for every mode.

## Export

- Tap **Export** on the result card to AirDrop, Save to Files, email, etc.
  (sends `NS_<date>_<id>_<mode>.csv` and `.json`, mode = `okn`, `fixmove` or
  `fixstill`; recordings before schema 3 have no mode suffix), **or**
- open *Files › On My iPhone › NystagmuSense › Recordings/*, **or**
- in Finder, select the iPhone › Files › NystagmuSense.

## Plot

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python3 scripts/plot_gaze.py path/to/NS_20261024-101500_ABCD1234.csv
# → prints stats, writes NS_..._ABCD1234.png next to the CSV
#   --output file.png to choose the path, --show to open an interactive window
```

The plot shows raw, uncalibrated signals against time: left/right eye direction x,
lookAtPoint x and lookAtPoint y. Untracked periods are shaded, and lines are broken
wherever frames are missing (gap > 2.5× the median frame interval), so unobserved
time is never drawn as data. Non-finite values count as missing. It doesn't classify
OKN. Interpret it by eye. It refuses empty, malformed, or time-decreasing files
rather than reordering or interpolating, and exits with an error (no PNG) if no sample
has a tracked face.

## Candidate OKN detection (offline)

```bash
python3 scripts/detect_okn.py path/to/NS_....csv [--plot okn.png]
```

A baseline, interpretable detector (no ML). It converts each eye's direction vector to a
horizontal angle, masks untracked samples and blinks (padded 50 ms), differentiates with a
local polynomial derivative (5 samples, polyorder 2; equivalent to Savitzky–Golay
on uniform samples) using the actual camera timestamps, then finds fast
phases (|v| > 40 deg/s), slow phases (line fits ≥ 0.15 s) and OKN beats (a slow phase followed
within 0.1 s by an opposite-direction fast phase). OKN is a candidate where a 2 s window
(0.5 s step) has ≥ 2 beats with ≥ 75 % in one direction. Every threshold is a CLI flag; run
with `--help`.

The entire pipeline splits on invalid samples and timestamp gaps greater than
2.5× the median frame interval. It does not join slow/fast phases, count beats
across missing data, or merge candidate windows across those boundaries. Each
available blink channel is checked independently; missing/non-finite values in
an available channel invalidate that sample. Opposite-direction candidate windows
stay separate, and reported bounds never extend beyond the observed segment.
Bounds are sliding-window support, **not measured physiological onset/offset**;
beat counts and median slow velocity refer to the interval's dominant direction.
Reversing stimulus displacement is reported as unknown rather than reduced to
one net direction. Parameter and malformed CSV errors return a clean error.

Caveats: thresholds were tuned on synthetic data only, the eye-angle sign (+ = subject's
right) is **unverified on device**, and output is a research candidate with no clinical or
contrast-sensitivity meaning.

**Known specificity limitation:** `trials/trackingtest2` was recorded with deliberate
left/right saccades, yet this baseline reports candidate OKN windows. A slow-phase
line-fit slope alone does not establish sustained pursuit or distinguish voluntary
motion from stimulus-driven OKN. Do not treat this negative-control intent as a
verified ground-truth annotation, or adjust thresholds just to make it pass. Before
enabling detection in the app, collect independently labelled positive recordings
and controls (fixation, voluntary saccades, pursuit, head motion and blinks), verify
direction on device, and assess false positives and sensitivity on recordings not
used to select thresholds.

## CSV format (schema v3)

`schemaVersion` in the sidecar tells recordings apart:

- **v1** (`trials/trackingtest1`–`2`): black bars on a white→black fading
  background, so `stim_bg_gray` changes over time.
- **v2**: the sidecar adds `stimulusViewport`, `stimulus.fixedBackgroundGray` and
  `stimulus.stripeGray`. The default stimulus is white bars on a constant black
  background, so `stim_bg_gray` is constant (0). CSV columns are unchanged.
- **v3**: the sidecar adds `stimulus.trialMode` (`okn`, `fixationMovingStripes`,
  `fixationStillStripes`; missing means `okn`) and, in fixation trials only,
  `fixationDot` (`centerXPoints`, `centerYPoints`, `diameterPoints`,
  `outlinePoints`, in SwiftUI points within `stimulusViewport`, origin top-left).
  A `fields` key describes these. Still-stripe trials record
  `speedPointsPerSecond` 0. CSV columns are unchanged.

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

# Python script tests (plot_gaze tests are stdlib only; detect_okn tests need numpy + scipy)
pip install -r scripts/requirements.txt
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
- The grating and recording start only after the first tracked face frame arrives.
  Startup time is not part of the session.
