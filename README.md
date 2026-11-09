# NystagmuSense

---

A Swift research application exploring smartphone eye tracking and optokinetic
nystagmus (OKN), with the long-term goal of studying contrast sensitivity.

Optokinetic nystagmus is a reflex of the nervous system in response to patterns
moving across the visual field. This response consists of a smooth tracking
movement in the direction of the stimulus, followed by a rapid resetting movement
in the opposite direction. This is a normal visual reflex. The phenomenon can be
induced by moving visual stimuli, opening doors for potential uses in an optometry
clinic. One potential use is studying contrast sensitivity, an important marker of
visual function. Research has demonstrated OKN-based estimates of contrast
sensitivity under controlled, calibrated conditions; see
[Dakin and Turnbull (2016)](https://www.nature.com/articles/srep34514).

Using a dynamic stimulus on a smartphone, we aim to induce an optokinetic response
and record eye movements using the front camera. Advances in camera technology,
specifically on mobile phones, make this an approach worth investigating. The
current app presents moving bars and exports raw ARKit eye-tracking data; an
offline Savitzky–Golay-based detector identifies candidate tracking/reset patterns.
It does not yet measure the exact point at which OKN stops or calculate a
contrast-sensitivity function. That would require calibrated stimulus contrast,
threshold measurements across spatial frequencies, and validation against a
reference method. A screen shade from 1 to 100, or its common logarithm, is not
itself a calibrated contrast-sensitivity measurement.

---
##### Reach out to rrs248@cornell.edu for access - Research prototype; candidate OKN detection under development
---

## Current status

> **Research prototype. Not clinically validated. It produces no diagnostic or
> contrast-sensitivity score.**

| Component | Status |
|---|---|
| Menu → **Record 10 Seconds** → test screen | Works. The 30 s countdown screen is skipped for Deliverable 1 (`CountdownOverlay` kept, unused) |
| Moving stripe stimulus | Black bars at 126 pt/s over a white → black background fade; motion and the ten-second fade wait for landscape and face tracking |
| 10 s raw ARKit eye-tracking recording | Earlier app recordings are checked into `trials/`; the newly merged landscape/permission/retry flow passes simulator tests and needs a fresh phone run |
| CSV + JSON export (share sheet / Files app) | Real schema-v1 device exports are checked in; new recordings use schema v2 with surface size and stripe/background settings |
| Python plotting (`scripts/plot_gaze.py`) | Tested on synthetic data and checked-in real device recordings |
| OKN detection | **Candidate only, offline:** `scripts/detect_okn.py` (Savitzky–Golay baseline, tuned on synthetic data). Not in the app; legacy Swift heuristic in `Services/Analysis/` stays disabled |
| Contrast-sensitivity score | **Removed from the test flow.** "Past Tests" shows only legacy prototype scores |

Architecture, timing and data-model details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
The full research roadmap is in [NYSTAGMUSENSE_PROJECT_SPEC.md](NYSTAGMUSENSE_PROJECT_SPEC.md);
the recording/export/plot workflow and an offline candidate detector are implemented.
In-app OKN detection and contrast-sensitivity measurement remain future work.

## Requirements

- Xcode 16.4+ with an iOS SDK supporting the iOS 18.5 deployment target, and
  an installed iOS Simulator runtime for simulator tests
- An iPhone/iPad with a TrueDepth (Face ID) front camera. ARKit face tracking
  doesn't run in the Simulator, which can only show the "unsupported device" path.
- iOS app: no third-party dependencies. Apple frameworks include SwiftUI, ARKit
  and Core Data.
- Offline analysis on a computer: Python 3.9+ with `matplotlib`, `numpy` and
  `scipy` (`python3 -m pip install -r scripts/requirements.txt`)

## Build and run on an iPhone

1. Use the merged `main` branch and open `NystagmuSense.xcodeproj`.
2. Under *Signing & Capabilities* for the `NystagmuSense` target, pick your team
   (the project currently points at team `L5VAJVH6AP`). The unused iCloud/Push
   capabilities have already been removed.
3. Connect the iPhone, select it as the run destination, and press ⌘R.
4. Accept the camera permission prompt on first use.

## Experiment workflow

1. On the Mac, start the receiver (see [Automatic Wi-Fi Recording Transfer](#automatic-wi-fi-recording-transfer)).
2. On the menu, pick the **Test Type** (default *General Test*). The app
   remembers it across launches, and the line below it shows the next name,
   e.g. `DIR_T004`. Test type only labels the recording; it doesn't change the
   stimulus.
   For **Pilot 03** also pick the **participant** (`P01` / `P02`, remembered
   until changed); **Record** stays disabled until one is chosen.
3. Pick the **condition** (`OKN`, `Dot + moving`, `Dot + still`) and, for
   moving stripes, the **stripe direction** (`← Left` or `Right →`; Right is
   the default). Still stripes show "Direction: none" and are named `NONE`.
   The line below shows the next name without its timestamp, e.g.
   `P03-P01_T041_OKN_LEFT`.
4. Tap **Record 10 Seconds**, rotate to landscape, and tap **Check Position**.
   Test type, participant, condition and direction are fixed from here on. The
   card shows face detection and an approximate distance:
   - "No face detected", "Move closer (35 cm)" or "Move farther away (20 cm)";
   - "Good positioning — 28 cm" once the distance is in range;
   - **Start Trial** enables once the smoothed distance has stayed inside
     **25–30 cm** for 1 s ("Ready to record").
5. Tap **Start Trial**. The recording begins on the next tracked frame, using
   the same ARKit session. Moving out of range during the trial does **not**
   stop it; the deviation is saved in the sidecar.
6. Check that the result card shows the file name and **Uploaded to Mac**.

**Start without distance check (development)** skips the gate, for example when
the distance readout isn't working. The trial is recorded as
`faceDistance.check = "bypassed"`, never as passed.

**The distance is approximate.** It is ARKit's estimate of the distance from the
front camera to the midpoint between the eyes, and it is uncalibrated. The camera
sits at the screen edge, so this isn't the eye-to-screen-centre distance (about
3 % less at 28 cm). The 25–30 cm range is a preliminary choice for experiments,
not a validated requirement.

### File names

Every recording is named
`{TEST}_T{trial}_{MODE}_{DIRECTION}_{yyyyMMdd_HHmmss}` (**file-name contract
1**), and the folder, CSV and JSON all share that name. For example:

```
DEV_T001_OKN_RIGHT_20261104_143022.csv / .json
DIR_T002_OKN_LEFT_20261104_143105.csv / .json
FIX_T003_FIXSTILL_NONE_20261104_143145.csv / .json
P02_T004_FIXMOVE_RIGHT_20261104_143220.csv / .json
P03-P01_T005_OKN_LEFT_20261106_150030.csv / .json
```

A trial with a participant (Pilot 03) writes `{code}-{participant}` in the
`TEST` field, e.g. `P03-P01`. That already fits contract 1 (`TEST` allows
`A–Z 0–9 -`), so older receivers accept it and the contract number is unchanged.

| Test Type (menu) | Code | Purpose |
|---|---|---|
| General Test (default) | `DEV` | General debugging and quick experiments |
| Gaze Validation | `GAZE` | Verify eye-angle tracking |
| Blink Test | `BLINK` | Test blink masking and artifacts |
| OKN Detection | `OKNTEST` | Test OKN fast/slow phases |
| Direction Test | `DIR` | Compare leftward and rightward motion |
| Fixation Control | `FIX` | Test fixation without OKN |
| Distance Test | `DIST` | Validate pre-trial distance measurement |
| Pilot 02 | `P02` | Formal next pilot recordings |
| Pilot 03 | `P03` | High-contrast OKN validation, participants `P01`/`P02`; constant white background (see [docs/PILOT_03.md](docs/PILOT_03.md)) |

- **Timestamp:** the recording start in **UTC**, the same instant as
  `startedAt` in the JSON.
- **Trial counter:** one sequence shared by all test types on the phone, so the
  numbers follow recording order. It survives app restarts but not deleting
  the app. The counter moves forward only when a recording is **saved
  locally**; a successful upload isn't needed, and a failed upload never frees
  a number. Retry Export keeps the same name. Cancelled, empty and never-saved
  recordings don't use a number.
- **One contract on both sides.** `RecordingName` in Swift and `STEM_RE` in
  `scripts/receive_recordings.py` are both tested against
  `scripts/tests/fixtures/recording_names.json`. The receiver's `/health`
  reports `name_contract`, and **Test Connection** warns if the running
  receiver is older than the app. When changing the format, update all three
  places and bump the contract number.
- **Older recordings** keep their names (`NS_<date>_<id>_<mode>`, and schema 4
  `EXP_T…`). The receiver and every script still accept them.

The sidecar (schema 6) adds:
- `experimentID` (the test-type code), `testTypeName`, `trialNumber`,
  `recordingName`;
- schema 6: `participantID` (Pilot 03) and `directionCode` (`RIGHT` / `LEFT` /
  `NONE`, as in the name). The receiver refuses a sidecar whose
  `recordingName` or `participantID` disagrees with the file name
  (`mismatched_metadata`);
- `faceDistance`: `check`, `recommendedRangeCm`, `atStartCm`, `medianCm`,
  `minCm`, `maxCm`, `fractionOutsideRange`, and the definition above.

`stimulus.trialMode` and `stimulus.direction` stay separate fields.

`sessionID` stays the unique recording ID, and the CSV columns are unchanged.

### Checks to do on a physical iPhone

Neither distance nor direction can be tested in the Simulator.
1. **Distance:**
   - Hold a ruler from the eyes (bridge of the nose) to the front camera at
     about **20, 28 and 35 cm**.
   - Note the cm shown at each distance, and whether "Move farther away",
     "Good positioning / Ready" and "Move closer" appear as expected.
   - Expect a few cm of error. Treat the readout as **uncalibrated** until it
     has been checked like this.
2. **Direction:**
   - Run an OKN trial with `← Left` and check that the bars move toward the
     screen's left edge.
   - The JSON should have `"direction": "leftward"`, the name should contain
     `_OKN_LEFT_`, and `stim_displacement_pt` in the CSV should decrease.
   - Repeat with `Right →`.
   - With *Dot + Still Stripes*, the bars never move and the name says `NONE`.
3. **Names:**
   - Record two trials and check that the names go `T001`, `T002`.
   - Quit and relaunch the app (swipe it away), record again, and check that
     the next name is `T003`.

## Record 10 seconds

1. Tap **Record 10 Seconds**, then rotate the phone into landscape. If the screen
   won't rotate, turn off Portrait Orientation Lock. **Check Position** stays
   disabled until the app is displayed in landscape.
2. Keep your face fully visible to the front camera in good light, tap
   **Check Position**, then **Start Trial** once the distance is in range (see
   [Experiment workflow](#experiment-workflow)). The first time, iOS asks for camera access; this doesn't
   fail the session. From Start until the session ends, the screen is locked to the
   landscape side you're holding, so it can't rotate mid-trial. The static
   stimulus frame is already showing, and once a face is tracked the stimulus starts
   moving and the recording clock starts together.
3. Keep your head still and watch the black vertical bars move rightward at
   **126 SwiftUI points/s** (40% faster than 90 pt/s). Over the ten-second capture,
   the background fades steadily from white to black, where it matches the bars.
   The static white-background frame before capture avoids a brightness step at
   motion onset. The compact card shows face-tracking status.
4. After ~10 s, the stimulus disappears and **Recording saved** shows sample count
   and observed rate. If the surface changes despite the orientation lock (for
   example, iPad multitasking), or the app becomes inactive during recording,
   capture stops and saves partial data with a reason in `issues`.
   **Cancel** discards the recording. Failed exports offer **Retry Export**; other
   failures (no camera frames within 5 s, no face found within 5 s of the first
   frame, camera denied) offer **Try Again**. Backgrounding the app before a face
   is found returns to the Ready state.

The sidecar records the full stimulus surface size (`stimulusViewport`, in
points) and stripe/background grey levels, alongside speed, direction and spacing.
The default capture uses black bars (`stripeGray = 0`) with a ten-second
background fade (`fixedBackgroundGray = nil`, `fadeHalfCycleSeconds = 10`).
Longer explicitly configured sessions continue the triangle wave back to white.
A fixed-background control can set `fixedBackgroundGray` to a grey code value.
The recorded background is a scheduled sRGB display value, not measured luminance
or a calibrated contrast threshold.
These changes support repeatable data collection. OKN detection is available
offline in Python; it is not enabled in the iOS app.

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

## Annotation workflow (reset labels for detector development)

`scripts/annotate_okn.py` is a small matplotlib tool for marking reset (fast-phase)
events by hand. `scripts/evaluate_okn.py` scores `detect_okn.py` against
completely reviewed trials. There is no ML, no database and no new dependency.
Labels describe what is visible in the ARKit signal, not physiological ground truth.

```bash
# One window for a whole split of the Pilot 01 plan (analysis/annotations/plan.csv)
python3 scripts/annotate_okn.py --split evaluation --annotator AA             # suggestions never shown
python3 scripts/annotate_okn.py --split development --annotator AA --assisted # velocity-peak suggestions (≥ 20 deg/s, NOT validated)
# Or any recordings, in the order given
python3 scripts/annotate_okn.py trials/<name>/<name>.csv [...] --annotator AA
```

The window opens at the first trial you haven't marked reviewed (`--start A3`
picks one by Pilot ID, queue number or `trial_id`). `←` / `→` save and move to the
previous / next trial without wrapping; if a save fails you stay on the trial
with your edits. Closing the window also saves. Evaluation trials never compute
or show suggestions, even with `--assisted` or in a mixed queue.

| Control | Action |
|---|---|
| `←` `→` (or the buttons) | save, then previous / next trial |
| left-click / right-click | add an event at the nearest sample / remove the nearest event |
| `1` `2` `3` | label for the next clicks: `fast_phase` / `uncertain` / `artifact` (resets to fast phase on each trial) |
| `z` | undo |
| `x` | mark the trial **completely reviewed** (needed for scoring, including trials with 0 resets); never set automatically |
| `s` | save to `analysis/annotations/events.csv` and `reviews.csv` |
| `+` `-`, `shift+←` `shift+→`, `r` | zoom at the cursor, scroll in time, reset zoom |
| `h` | show / hide the help panel |
| `t`, `y` | show/hide suggestions, accept the ones in view (assisted, non-evaluation trials only) |

The toolbar's zoom and pan tools also work. Events within 50 ms of an existing
event are refused as duplicates. Then:

```bash
python3 scripts/evaluate_okn.py                     # ±100 ms one-to-one matching
python3 scripts/evaluate_okn.py --tolerance-ms 150 --annotator AA
```

The scoring rules (uncertain labels excluded, artifacts count as false
positives, independent and assisted labels reported separately, unreviewed
trials never scored) are in `scripts/evaluate_okn.py`. The Pilot 01 labelling
plan is in [analysis/annotations/README.md](analysis/annotations/README.md).

## Export

- Tap **Export** on the result card to AirDrop, Save to Files, email, etc.
  (sends `{experiment}_T{trial}_{MODE}_{DIRECTION}_{UTC}.csv` and `.json`; see
  [File names](#file-names). Recordings before schema 4 are named
  `NS_<date>_<id>[_<mode>]`), **or**
- open *Files › On My iPhone › NystagmuSense › Recordings/*, **or**
- in Finder, select the iPhone › Files › NystagmuSense.

## Automatic Wi-Fi Recording Transfer

With a small receiver running on your Mac, each recording is uploaded
automatically after it is saved on the phone, into
`trials/<recording name>/` (the same CSV + JSON, byte-for-byte). The phone
always keeps its own copy. No paid Apple Developer account, cloud service or
extra dependencies; the receiver is Python standard library only.

1. **Start the Mac server** (from the repository folder). Create a token once,
   then start the receiver; `--lan` lets the iPhone reach it:

   ```bash
   openssl rand -hex 6 > ~/.nystagmusense_token     # once; stays outside the repo
   NS_UPLOAD_TOKEN=$(cat ~/.nystagmusense_token) python3 scripts/receive_recordings.py --lan
   ```

   If macOS asks whether Python may accept incoming connections, choose **Allow**.
   Without `--lan` it only listens on `127.0.0.1` (this Mac). `--port` changes the
   default port 8765.

2. **Find the Mac's IP address** (Wi-Fi is usually `en0`):

   ```bash
   ipconfig getifaddr en0
   ```

3. **Configure the iPhone.** Both devices must be on the same Wi-Fi. In the app,
   tap **Mac Transfer** and enter:
   - *Server*: `http://<that IP>:8765`, e.g. `http://192.168.1.20:8765`
   - *Upload token*: the output of `cat ~/.nystagmusense_token`

   Settings are stored only on the phone. Only local-network addresses
   (`192.168.x.x`, `10.x.x.x`, `172.16–31.x.x`, `*.local`) are accepted.

4. **Test the connection.** Tap **Test Connection**. The first time, iOS asks to
   find devices on your local network; tap **Allow**, then test again.
   "Connected" means the server is reachable *and* the token matches. From the Mac
   you can check the server too:

   ```bash
   curl -H "X-Upload-Token: $(cat ~/.nystagmusense_token)" http://localhost:8765/health
   ```

5. **Record and verify.** Record a trial as usual. The result card shows
   *Saved locally · Uploading to Mac…*, then **Uploaded to Mac** once the Mac has
   written both files. The server prints `saved trials/P02_T001_…`. Then:

   ```bash
   ls trials/
   python3 scripts/plot_gaze.py trials/P02_T001_<…>/P02_T001_<…>.csv
   ```

   If no server is set up, the card says *Saved locally (Mac transfer not set up)*.

   New folders in `trials/` are git-ignored because this repository is public;
   share a trial on purpose with `git add -f trials/<name>`.

6. **Retry a failed upload.** If the card says **Upload failed: saved locally**,
   fix the cause it shows (server not running, wrong IP or token, different Wi-Fi)
   and tap **Retry Upload**. Re-sending a recording the Mac already has is
   harmless; a *different* recording with the same name is refused, never
   overwritten. Recordings stay in *Files › On My iPhone › NystagmuSense ›
   Recordings*, and **Export** still works.

7. **Stop the server.** Press **Ctrl+C** in its Terminal window.

## Plot

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r scripts/requirements.txt
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
python3 scripts/detect_okn.py path/to/NS_20261024-101500_ABCD1234.csv --plot okn.png
# Omit --plot okn.png for the text report only.
```

To test a new phone recording:

1. Record the moving stimulus as described above, then export **both** CSV and
   JSON to the computer where the Python environment is set up.
2. Keep the original files together. Inspect `issues`, tracked sample count and
   observed rate in the JSON. Partial sessions or poor face tracking need review.
3. Run `plot_gaze.py` on the CSV to inspect the raw traces, then run
   `detect_okn.py` with `--plot` to compare candidate slow/fast phases with them.
   The detector reads the CSV; retain the JSON for stimulus/device context.
4. Record what the participant was doing, the phone model, viewing distance and
   lighting. Collect separate watch-the-bars, fixation and deliberate-saccade
   recordings; do not treat a deliberate movement as a confirmed OKN response.

New phone recordings can now be tested with this SG-based workflow. The analysis
runs on an exported recording on a computer, not live on the phone. The method estimates
eye velocity and flags candidate patterns; it is not a trained prediction model.
A positive window does not establish true OKN, and no windows does not prove that
OKN was absent, especially when little usable data remains.

A baseline, interpretable detector (no ML). It converts each eye's direction vector to a
horizontal angle, masks untracked samples and blinks (padded 50 ms), and estimates
velocity with a local polynomial derivative (5 samples, polyorder 2; equivalent to Savitzky–Golay
on uniform samples) using the actual camera timestamps, then finds fast
phases (|v| > 40 deg/s), slow phases (line fits ≥ 0.15 s) and OKN beats (a slow phase followed
within 0.1 s by an opposite-direction fast phase). Proposed slow phases must also
pass provisional quality gates: line-fit R² ≥ 0.8 and ≥ 80% of time-weighted SG
velocity samples agreeing with the fitted direction. A large net slope across
several reversals is therefore insufficient. OKN is a candidate where a 2 s window
(0.5 s step) has ≥ 2 beats with ≥ 75 % in one direction. Every threshold is a CLI flag; run
with `--help`.

The report gives fit rejection reasons and per-beat timestamps/quality metrics.
The plot shows rejected fits as dashed grey lines, qualified fits in blue and
numbered green markers for accepted slow/reset pairs. The green strip remains
**window support**, not continuous proof of OKN. When `stim_bg_gray` is present, a
third panel shows the scheduled display value; it is not measured contrast.

These new gates are conservative heuristics, **not calibrated accuracy or
confidence estimates**. Curved or noisy true slow phases may fail them. The flags
`--min-slow-r2` and `--min-slow-direction-agreement` expose the criteria; setting
both to 0 provides a comparison with the earlier slope-only pairing behavior.
Do not tune these thresholds merely to make a particular screenshot look right.

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

**Known specificity limitation:** the earlier slope-only baseline labelled the
deliberate left/right saccade recording `trials/trackingtest2` as candidate OKN.
The new quality gates reject its proposed beats under current defaults. This
recording was examined during development, so that result is a regression check,
not an independent specificity estimate. Voluntary movements with sufficiently
linear drift can still pass. Collect independently labelled positive recordings
and controls, verify the eye-angle sign with known left/right gaze movements, and
measure sensitivity and false positives on held-out recordings before enabling
detection in the app. Do not flip eye-angle sign solely to match the stimulus.

Relevant validation precedent: [Sangi et al. (2015)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4848063/)
compared detections with masked human annotations. Our provisional fit gates are
an implementation choice and have not been validated by that study.

### Experimental hybrid: raw-angle change points + SG

The existing SG pipeline remains the default. A second, opt-in implementation
is in `scripts/hybrid_okn.py`; it uses change-point segmentation to locate
short, steep resets in the **raw angle**, then computes SG velocity only within
the slow intervals between resets. Identified reset samples never enter those
SG windows. Both detectors reuse the same blink/gap masks, eye-angle sign,
slow-fit quality gates, beat pairing and candidate-window logic. Neither runs
in the iOS app, and existing Pilot 01 outputs are untouched.

```bash
# Original method (also the default when --method is omitted)
python3 scripts/detect_okn.py path/to/recording.csv --method sg --plot sg.png
# Alternative method
python3 scripts/detect_okn.py path/to/recording.csv --method hybrid --plot hybrid.png
# Run BOTH on identical inputs: side-by-side PNGs + reproducible summary.json
python3 scripts/compare_okn.py path/to/recording.csv --output-dir analysis/hybrid_comparison
# Batch comparison (use explicit paths if only some trials should be included)
python3 scripts/compare_okn.py trials/*/*.csv --output-dir analysis/hybrid_comparison
# Once human labels exist: evaluate both against the SAME complete reviews
python3 scripts/evaluate_okn.py --detector both
```

The comparison JSON includes source CSV checksums, parameter sets, reset times
and durations, accepted slow-phase and beat counts, candidate windows, and median
beat SPV. These generated comparisons stay git-ignored. `--no-plots` writes only
JSON. Evaluation uses each method's defaults and keeps manual and assisted
labels separate; annotation suggestions themselves remain unchanged.

**Segmentation model.** Within each contiguous valid run, dynamic programming
minimises raw-angle squared error plus a penalty per additional line segment.
Line segments join at observed samples, allowing even a one-camera-interval
reset. The penalty is `6 × noise_sigma² × log(sample_count)` by default. Noise
is estimated robustly from three-sample interpolation residuals at the actual
timestamps, with a 0.05° floor. This is a constrained polyline model, inspired
by penalised piecewise-linear segmentation, rather than an implementation of
[CPOP](https://www.jstatsoft.org/article/view/v109i07) (which optimises knot heights).
It uses O(n²) time and O(n) working memory per valid run, suitable for the current
short offline recordings; long continuous recordings will cost more.

Adjacent same-direction steep segments are combined. A hybrid reset must exceed
the **same 40°/s speed gate** as the SG baseline, have amplitude ≥ 0.5°, and last
≤ 150 ms. The extra gates suppress tiny/noisy excursions and long fast ramps;
they are provisional. Its report's `peak_velocity` is the steepest segment slope,
not an estimated physiological peak. Hybrid plots show SG velocity in slow
intervals and unsmoothed frame differences inside accepted resets, with the
piecewise-linear fit in orange on comparison plots.

Hybrid-specific flags are `--cp-penalty-scale`, `--cp-noise-floor-deg`,
`--cp-min-reset-amplitude-deg`, and `--cp-max-reset-s`. The existing
`--fast-threshold` applies to both methods in a comparison. All defaults are
experimental, not fitted to the available trial recordings. A larger penalty
can miss resets; a smaller one can oversegment noise. Resets with sampled slopes
below the speed gate, low amplitudes, or insufficient camera samples can still
be missed. More reset candidates do **not** establish better accuracy: compare
precision/recall and fixation false detections on held-out human-labelled trials.

## Relationship to the original paper's score

The original project paper's Methods (pp. 7–8, *Contrast Sensitivity Function Test
App Using Optokinetic Nystagmus*, Rohan Sampath) describes black moving bars over
a white → black background, two cycles, a 100–150 pixel eye-movement rule, gaps
longer than one second to mark pauses, and the common logarithm of the average
background values at selected timestamps.

The current app restores that **stimulus polarity and fading behavior**, with
one full downward sweep during the existing ten-second recording and the
requested 40% increase in speed. It does not reproduce the paper's two-cycle
protocol or pixel-distance detector: current ARKit exports are face-relative
vectors/metres, and the SG script uses angle-derived velocities. Its candidate
window boundaries are not precise, validated stop-tracking timestamps.

**The paper's score is not currently calculated.** SG differentiation alone
does not implement sustained OKN-loss detection, rejection of blinks/dropouts,
selection of fade crossings or aggregation across cycles. That validated event
logic must precede any timestamp-to-background score. The old `ScoreCalculator`
is kept only for historical results and remains disconnected. Even reproducing
`log10(mean(background values))` would yield an experimental project index,
not a calibrated CSF or a clinically validated result.

## CSV format (schema v3)

`schemaVersion` in the sidecar tells recordings apart:

- **v1** (`trials/trackingtest1`–`2`): black bars on a white→black fading
  background, so `stim_bg_gray` changes over time.
- **v2**: the sidecar adds `stimulusViewport`, `stimulus.fixedBackgroundGray` and
  `stimulus.stripeGray`. Earlier v2 settings used white bars on fixed black; the
  current default uses black bars, a white → black fade over ten seconds, and
  126 pt/s motion. Read the saved stimulus settings for each session rather than
  inferring appearance from schema version. CSV columns are unchanged.
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

Run Python commands from the repository root after activating the environment
created above:

```bash
python3 -m pip install -r scripts/requirements.txt
python3 -m unittest discover scripts/tests -v

# Smoke tests on real device exports; output paths keep source trials unchanged.
python3 scripts/plot_gaze.py trials/trackingtest1/trackingtest1.csv --output /tmp/trackingtest1-raw.png
python3 scripts/detect_okn.py trials/trackingtest1/trackingtest1.csv --plot /tmp/trackingtest1-okn.png
python3 scripts/detect_okn.py trials/trackingtest2/trackingtest2.csv --plot /tmp/trackingtest2-okn.png
```

With the current defaults, `trackingtest1` has 0 fast phases and no candidate
windows; `trackingtest2` has 27 fast phases but no accepted beats or candidate
windows with the quality gates. The earlier slope-only baseline counted 9 beats
and a candidate interval around 0.14–5.14 s. These are reproducibility checks,
not validated labels or accuracy measurements.

For Swift tests, select the installed Xcode toolchain and simulator. The device
name below is an example; replace it with one listed by `-showdestinations`:

```bash
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcodebuild -showdestinations -project NystagmuSense.xcodeproj -scheme NystagmuSense
xcodebuild test -project NystagmuSense.xcodeproj -scheme NystagmuSense \
  -destination 'platform=iOS Simulator,name=iPhone 18 Pro' \
  -parallel-testing-enabled NO \
  -only-testing:NystagmuSenseTests \
  -only-testing:NystagmuSenseUITests/NystagmuSenseUITests/testRecordingRequiresLandscape
```

The November 5 health fixes passed **110 Swift unit tests, 1 landscape UI test
and 164 Python tests**. The preceding four-PR integration also passed all
7 UI tests. The simulator verifies
lifecycle/UI logic with mock gaze; TrueDepth capture and perceived stimulus
motion require a physical phone. The `Tests` GitHub Actions workflow runs the
Python suite, Swift unit tests and the landscape UI regression on future PRs
and pushes to `main`, and uploads its Xcode result bundle.

### Pilot 03 evaluation readiness

Use the frozen manifest for annotation queues. Direct CSV queues also recognize
its held-out recordings and disable suggestions:

```bash
python3 scripts/annotate_okn.py --plan analysis/pilot_03/manifest.csv \
  --split development --annotator RS --labels-dir /path/to/private-labels \
  --trials-dir /path/to/trials
```

The proposed candidate C is available as `evaluate_okn.py --detector sg-direction`
(SG at 22 deg/s plus the recorded stimulus direction). The original SG at
40 deg/s remains the default. `--fast-threshold` makes an override explicit;
exported results include the detector, threshold and annotator. Development
sweeps and comparisons require `--annotator` when multiple annotators are
present and refuse assisted labels. Missing recordings block a complete sweep.
Still-stripe controls contribute false alarms, never true OKN resets.

Complete the [blinded second review](analysis/pilot_03/second_review.md), decide
the label policy and record the frozen commit/configuration **before** running
the one-time evaluation. Then use the selected detector with `--manifest
analysis/pilot_03/manifest.csv --split evaluation --allow-evaluation --annotator
AA --artifacts exclude`. No held-out scoring was run during the code review.
Raw P03 recordings and private labels must be supplied locally; Git does not
sync these ignored files. The label checker defaults to development and also
requires explicit opt-in for evaluation.

## Known limitations

- Earlier schema-v1 phone recordings demonstrate capture/export at about 60 Hz
  (see [trials/README.md](trials/README.md)). They do not validate the new
  landscape stimulus flow, gaze calibration, or the detector. Confirm the newly
  merged behavior on a physical phone; the eye-direction sign remains unverified.
- Signals are raw ARKit model outputs in face coordinates. There's no calibration,
  no conversion to degrees of visual angle, and head movement isn't removed
  (head pose isn't recorded yet).
- Stimulus/gaze alignment uses the *scheduled* stimulus state. Display and camera
  latency aren't measured or compensated.
- Stimulus speed and stripe size are in screen points, so not physically
  standardised across devices. Screen brightness isn't controlled.
- A static grating appears before capture. Motion and recording start together
  after the first tracked face frame arrives; startup time is not recorded.
- The background fade varies display values and absolute luminance difference;
  it is not a calibrated sweep of normalized grating contrast. For example,
  Michelson contrast uses `(Lmax - Lmin) / (Lmax + Lmin)`: if black luminance
  were exactly zero, reducing the other level would leave this ratio at 1 until
  both vanish. Actual display luminance and black level must be measured; see
  [this study’s grating-contrast definition](https://www.nature.com/articles/s41598-017-16873-6).
  The legacy shade-based score is not used.
