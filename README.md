# NystagmuSense

Experimental iOS moving-grating and gaze-capture prototype. Today's path records
about ten seconds of raw ARKit estimated look-at points and exports them for Python.
It does not detect OKN or calculate a contrast-sensitivity score. Historical scoring
code remains in the repo but is not used by this recording flow.
The full supplied roadmap is in [NYSTAGMUSENSE_PROJECT_SPEC.md](NYSTAGMUSENSE_PROJECT_SPEC.md);
only Deliverable 1 is implemented here.

## Record on an iPhone

1. Open `NystagmuSense.xcodeproj` in Xcode. The current deployment target is iOS 18.5.
   Select your signing team under Signing & Capabilities and a physical iPhone
   running iOS 18.5 or later. The app checks `ARFaceTrackingConfiguration.isSupported`;
   the simulator cannot provide real gaze measurements.
2. Build and run. Tap **Record 10 Seconds** and allow Camera access. If denied,
   enable Camera in iOS Settings for NystagmuSense, return, and start a new test.
3. Hold the phone steadily with the front camera unobstructed and your face visible
   in good lighting. The existing bars move right and the background continues its
   original fade. Recording starts with the first AR frame and stops automatically
   after about ten seconds. Startup has a separate 15-second no-frame timeout.
4. Inspect the valid-estimate and total-frame counts. **Zero valid estimates is a
   failed capture**, even though a diagnostic JSON can still be exported. Cancel,
   leaving the app, or an ARKit interruption stops and marks a partial session.
5. Tap **Export JSON**, then AirDrop to the Mac or Save to Files. Each recording is
   also saved locally in `Documents/GazeRecordings`. In Files, look under **On My
   iPhone > NystagmuSense > GazeRecordings**, or use Finder device file sharing.
   Export errors are displayed with a retry button. Recordings remain on the phone
   until you delete them; no camera images/video are saved or uploaded.
6. Tap **Back** to return to the menu and start another independent recording.

## Plot the exported session

From the repository directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r scripts/requirements.txt
python3 scripts/plot_gaze.py /path/to/gaze-SESSION.json
```

A PNG is saved beside the JSON. Use `--output trace.png` to choose a path or `--show`
for an interactive window. The script prints valid/invalid counts, frame coverage,
observed frame rate, median/max frame intervals, and stop reason. It fails clearly
for empty/all-invalid recordings or decreasing/malformed timestamps. It plots raw
points against actual elapsed seconds, with no smoothing, interpolation, or OKN
classification. Missing AR frames cannot be counted from a nominal frame rate.

## What the measurements mean

The project has no third-party eye-tracking package. The capture reuses its built-in
ARKit session and reads `ARFaceAnchor.lookAtPoint`. The previous code took eye
transform translations (eye positions), which were not gaze locations.

Schema version 1 contains:

- `samples`: native `ARFrame.timestamp` in seconds; `x`, `y`, `z` estimates in
  **meters in face-local coordinates**; `faceTracked`, `valid`, and available
  left/right blink coefficients. Invalid coordinates are omitted in JSON.
- `beginTime`/`endTime`: ISO 8601 app session dates, `stopReason`, requested duration,
  hardware identifier (`deviceModel`), and iOS version.
- UI uptime markers for stimulus appearance/removal and recording start/end.
  These mark lifecycle events, not measured display presentation times. The grating
  appears before permission/startup completes; exact stimulus-to-camera alignment
  and latency have **not** been verified. Plot elapsed time is relative to the first
  recorded AR frame, which may itself have invalid gaze.
- Stimulus settings: existing 90 SwiftUI points/s motion, bar width 2% of view width,
  pitch 2.4 widths, and white-to-black background fade over 30 seconds.

As documented by [Apple](https://developer.apple.com/documentation/arkit/arfaceanchor),
face coordinates have +x toward the viewer's right (subject's left), +y up relative
to the face, and +z outward. These estimates are **not** screen pixels/points,
calibrated visual angles, or diagnostic measurements. `valid` means face-tracked
with finite coordinates; it does not establish gaze accuracy. Blink coefficients
are retained but not used to reject samples; no eye-confidence score is invented.
Head motion, blinks, geometry, lighting, and device limitations may affect results.

## Verification status and device checklist

Verified here: Swift source syntax parsing, plist validation, Python parser tests,
and PNG generation from explicitly synthetic schema-contract data. These checks
provide no evidence of human gaze capture. This Mac has no Xcode installation;
iOS compilation, UI behavior, and physical-device capture remain unverified.

The milestone is complete only after a device test confirms:

- Grating still moves throughout capture; automatic stop is near ten seconds.
- A real session contains nonempty, ordered gaze samples and exports successfully.
- Its Python chart uses actual elapsed timestamps; inspect whether signals vary
  plausibly rather than assuming that finite values establish eye-tracking quality.
- Denied permission, unsupported hardware, loss of face, cancellation, and app
  backgrounding report honest results and do not continue capture invisibly.

Run the offline parser checks with:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```
