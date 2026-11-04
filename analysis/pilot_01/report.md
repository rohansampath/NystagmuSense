# NystagmuSense Pilot 01: first real-device experiment

*Recorded 2026-11-04, 00:13–00:21 local time · 1 participant · iPhone 16 Pro (`iPhone17,1`), iOS 26.6.2 · analysed 2026-11-04*

All numbers come from [`run_pilot.py`](run_pilot.py). It runs the existing
`plot_gaze.py` and `detect_okn.py` **unchanged**, with the detector's default
parameters. Raw files in `trials/` were only read.
The raw recordings, the per-trial plots (`figures/trials/`) and the detector
text output (`detector_output/`) are not published with this report; see
[README.md](README.md). Measurements labelled
*exploratory* use a different threshold or a simple peak count; they are
diagnostic only and are **not** detector results.

**Summary.** ARKit picks up deliberate eye movements and blinks clearly, with
no lost frames. Free viewing of the moving bars (A) produces a visible OKN-like
sawtooth in all 5 trials. Fixating the dot (B, C) produces none in any of the 11
trials. The current detector, however, finds only 1–2 beats per A trial and
**zero OKN windows in every trial**. Its 40 deg/s fast-phase threshold misses
most of the resets, and each missed reset then gets the neighbouring slow
phases rejected. Batch 1 also shows that the detector's documented sign
convention is **inverted**.

---

## A. Experiment overview

| | |
|---|---|
| Batch 1 (validation) | 5 trials, all *dot + still stripes*: centre; left→right; right→left; alternate ~2 s; centre + blinks |
| Batch 2 (comparison) | **A** OKN: watch the moving stripes · **B** fixate the red dot while the stripes move · **C** fixate the dot, stripes still |
| Planned Batch 2 order | ABC · BCA · CAB · ACB · BAC (5 of each) |
| Stimulus | black bars (17.5 pt wide, 42 pt pitch) drifting **rightward at 126 pt/s**; background fades linearly from sRGB 1 to 0 over the 10 s; red dot (12 pt) at the screen centre in B and C |
| Physical stimulus (estimate) | 1 pt ≈ 0.166 mm, so 20.9 mm/s and a 6.95 mm pitch. At an assumed **30 cm** (viewing distance was not recorded): about **4.0 deg/s**, 0.75 cycles/deg, 3.0 Hz |
| Recording | 10 s of ARKit face tracking (TrueDepth), uploaded over Wi-Fi to `trials/` |

### Manifest

Order was checked two independent ways: by the sidecar `startedAt` (wall
clock) and by the first frame's `host_time_s` (monotonic uptime). Both give the
same order. Conditions come from each sidecar's `stimulus.trialMode`, which the
app writes itself, so the grouping by condition does not depend on the order.

| Trial | Batch | Expected behaviour | Recorded mode | Filename | Timestamp (UTC) |
|---|---|---|---|---|---|
| T01 V1 | 1 | centre 10 s | fixationStillStripes ✓ | NS_20261104-001330_EDD9E3AB_fixstill | 05:13:30 |
| T02 V2 | 1 | left 5 s → right 5 s | fixationStillStripes ✓ | NS_20261104-001355_1F937E52_fixstill | 05:13:55 |
| T03 V3 | 1 | right 5 s → left 5 s | fixationStillStripes ✓ | NS_20261104-001415_BFD61ACA_fixstill | 05:14:15 |
| T04 V4 | 1 | alternate L/R ~2 s | fixationStillStripes ✓ | NS_20261104-001438_CCE2CEC9_fixstill | 05:14:38 |
| T05 V5 | 1 | centre + blinks | fixationStillStripes ✓ | NS_20261104-001457_0DB297A4_fixstill | 05:14:57 |
| T06 A1 | 2 (R1) | A | okn ✓ | NS_20261104-001649_3B564048_okn | 05:16:49 |
| T07 B1 | 2 (R1) | B | fixationMovingStripes ✓ | NS_20261104-001709_9A6B885A_fixmove | 05:17:09 |
| T08 C1 | 2 (R1) | C | fixationStillStripes ✓ | NS_20261104-001727_3611D4CA_fixstill | 05:17:27 |
| T09 B2 | 2 (R2) | B | fixationMovingStripes ✓ | NS_20261104-001755_51DB182F_fixmove | 05:17:55 |
| T10 C2 | 2 (R2) | C | fixationStillStripes ✓ | NS_20261104-001822_12E51902_fixstill | 05:18:22 |
| T11 A2 | 2 (R2) | A | okn ✓ | NS_20261104-001846_1935C8DE_okn | 05:18:46 |
| T12 C3 | 2 (R3) | C | fixationStillStripes ✓ | NS_20261104-001918_C78484EE_fixstill | 05:19:18 |
| T13 A3 | 2 (R3) | A | okn ✓ | NS_20261104-001938_2F10DCDB_okn | 05:19:38 |
| T14 B3 | 2 (R3) | B | fixationMovingStripes ✓ | NS_20261104-001957_DC24C342_fixmove | 05:19:57 |
| T15 C4 | 2 (R4?) | A | fixationStillStripes ✗ | NS_20261104-002014_8283DFED_fixstill | 05:20:14 |
| T16 A4 | 2 (R4?) | C | okn ✗ | NS_20261104-002030_1D472ADC_okn | 05:20:30 |
| T17 B4 | 2 (R4?) | B | fixationMovingStripes ✓ | NS_20261104-002044_02710D72_fixmove | 05:20:44 |
| T18 C5 | 2 (R5?) | B | fixationStillStripes ✗ | NS_20261104-002058_9B808040_fixstill | 05:20:58 |
| T19 B5 | 2 (R5?) | A | fixationMovingStripes ✗ | NS_20261104-002121_448005B6_fixmove | 05:21:21 |
| T20 A5 | 2 (R5?) | C | okn ✗ | NS_20261104-002134_F5DFEFF3_okn | 05:21:34 |
| T21 C6 | 2 (?) | — (not in plan) | fixationStillStripes | NS_20261104-002149_1A2F66B1_fixstill | 05:21:49 |

**Discrepancies (reported, not resolved):**
- **There are 21 recordings, not 20.** Batch 2 has 16, split A = 5, B = 5,
  **C = 6**, so one C trial is extra.
- **Rounds 1–3 match the plan exactly. Rounds 4–5 do not.** The recorded
  sequence for the last 7 trials is C A B C B A C, against the planned A C B B A C.
  If T18 is the extra trial, round 5 matches (B A C) and round 4 was run as
  C A B. If T15 is the extra, round 4 was run as A B C. The data alone can't
  tell which. The gaps between recordings (13–24 s) show no obvious retake.
  C is analysed with all 6 trials; dropping T15 or T18 changes no C result,
  because every C metric is 0 or near the noise floor in all six.
- The first test upload from 2026-11-03 (`NS_20261103-235818_713BD53C_fixmove`)
  **is no longer in `trials/`**. It isn't part of this pilot.

---

## B. Data quality

| Measure (all 21 recordings) | Value |
|---|---|
| Samples per trial | 597–600 (2–3 frames outside the 10 s window dropped by the app, as designed) |
| Effective rate | 60.01 Hz in every trial; median Δt 16.66 ms, max Δt 16.665 ms, SD of Δt < 0.001 ms |
| Gaps (Δt > 2.5 × median) | **0** |
| Face tracked | **100 %** of samples in every trial |
| Detector-valid samples | 100 % in 20 trials; **60.9 %** in T05 (deliberate blinks) |
| Blink coefficient | exactly 0 throughout 18 trials; max 0.05 (T09) and 0.009 (T10); 0.96 in T05 |
| Single-frame jumps > 3° | 0 in Batch 2; 3 and 11 in T03 and T04 (the deliberate saccades) |
| Left eye vs right eye | r ≥ 0.989 in every trial (≥ 0.9925 in all but T01); left minus right is a constant **4.0–4.7°**, SD 0.02–0.20° within a trial |

Interpretation:
- **Tracking was not a limiting factor in this session.** Lighting and head
  position were apparently good.
- **The timestamps are perfectly regular** (Δt SD < 1 µs). This means
  `ARFrame.timestamp` is tied to the display frame rate, so it can't show
  camera exposure jitter.
- **The left- and right-eye signals are not independent.** They move together
  almost perfectly, with a fixed ~4° offset. ARKit appears to derive both eye
  transforms from one shared gaze estimate *(inferred)*. Consequences:
  - "Both eyes agree" carries no information here.
  - Averaging the two eyes does not reduce noise.
  - Binocular agreement can't be used as a quality check.
- **No missed blinks are evident.** In T05 every blink produces a large,
  stereotyped artefact (§C), and that signature never appears in the 18 trials
  whose blink value is 0. The participant probably held back blinks during these
  short trials *(inferred; there's no video to confirm)*.

---

## C. Eye-tracking validation (Batch 1)

Figures: [batch1_validation_traces.png](figures/batch1_validation_traces.png),
[batch1_V5_blinks.png](figures/batch1_V5_blinks.png).

"Detector angle" = −mean(atan2(dir_x, dir_z)) over both eyes, exactly as in
`detect_okn.py`. Its documentation says **+ = subject's right**.

| Trial | Instructed | Result |
|---|---|---|
| T01 V1 | centre 10 s | mean −5.8° (centre is **not** 0°), **SD 0.36°**, range 2.0°, median 1 s SD 0.23°, drift −0.04 deg/s (≈0.4° over 10 s). No fast phases, no beats |
| T02 V2 | left → right | first half −2.4°, second half −11.9°: **step −9.5°** (left eye −9.6°, right eye −9.3°). Transition in two saccades at 4.35 s (−4.5°) and 4.75 s (−6.0°) |
| T03 V3 | right → left | first half −9.9°, second half +6.1°: **step +16.0°** (left eye +16.2°, right eye +15.8°). Transitions at 0.8 s (to the right) and 4.9 s (to the left) |
| T04 V4 | alternate ~2 s | clean square wave, **7 switches** at 0.35, 1.40, 3.15, 4.57, 6.17, 7.37 and 8.73 s (about every 1.2–1.8 s); about 12–15° peak to peak |
| T05 V5 | centre + blinks | **15 blink events** (both eyes, 83–233 ms). Each produces a **+8.1 to +10.0°** fake angle swing (see below) |

### Sign convention: the documented sign is inverted

Looking **right** makes the detector angle **more negative** (T02 second half,
T03 first half). Looking **left** makes it more positive (T03 second half).
`lookat_x_m` moves the same way, and that contradicts the sidecar's
`+x = subject's left` description too.

Both deliberate step trials agree, in opposite orders, so a constant offset or
drift can't explain it. **Assuming the instructions were followed, the
detector's angle is + = subject's *left*.** Confidence is moderate to high:
2 trials, no on-screen targets, no video.

Consequences:
- Every slow-phase direction the detector reports is mirrored, including its
  "OPPOSITE to stimulus" labels.
- That also covers the older `trackingtest3` and `trackingtest3_2` notes.

### Amplitude can't be validated

There were no on-screen targets and no viewing distance, so the true eye
rotation is unknown. The amplitudes also differ between movements:
- "left" in T02 was only about 3° from the T01 centre value;
- "left" in T03 was about 12° from centre;
- the T04 swings were about 12–15° peak to peak.

Gaze to the screen edges at about 30 cm would be about ±13° (about 27° peak to
peak). So either the participant didn't look to the edges, or **ARKit
compresses eye rotation** *(uncertain)*.

### Saccade speed is underestimated

The 10–12° saccades in T04 peak at **160–195 deg/s** of SG velocity. Saccades of
that size normally reach about 300–400 deg/s. So the measured speed is roughly
half the real speed *(inferred)*. The cause could be 60 Hz sampling, ARKit's own
smoothing, or the 5-sample SG filter.

### Blinks

**The blink mask works.** Each deliberate blink causes a large artefact,
roughly +9° for 0.1–0.25 s. The detector masks anything over 0.5, padded by
±50 ms. That covers almost every artefact, leaving **1 residual fast phase**: a
single sample at 1.34 s, −59 deg/s, right at a mask edge. That trial has
**0 beats and 0 windows**.

As an exploratory check, with the mask turned off (blink threshold 1.0) the same
trial gives **30 fast phases and 2 beats**. The cost of the mask is data:
frequent blinking left only 61 % of samples usable.

**Assessment:**
- **Usable for OKN analysis:** ARKit's horizontal gaze signal tracks the
  direction and timing of deliberate movements, the fixation noise floor is low
  (about 0.3–0.6° SD), and blinks are registered and maskable.
- **Not yet usable for:** absolute amplitude, true velocity, or anything that
  compares the two eyes.

---

## D. OKN detection results (Batch 2)

Figures: [batch2_condition_comparison.png](figures/batch2_condition_comparison.png),
[batch2_all_traces.png](figures/batch2_all_traces.png).

### Condition summary: detector metrics at default parameters

Values are mean ± SD, followed by each trial in recording order.

| Metric | A: OKN (n=5) | B: dot + moving (n=5) | C: dot + still (n=6) |
|---|---|---|---|
| Candidate beats | **1.2 ± 0.45**: 1, 1, 2, 1, 1 | **0**: 0, 0, 0, 0, 0 | **0**: all 6 = 0 |
| Fast phases (> 40 deg/s) | 3.8 ± 1.6: 2, 5, 6, 3, 3 | 0.2 ± 0.45: 1, 0, 0, 0, 0 | 0: all 6 = 0 |
| Median beat SPV, detector sign | −3.62 ± 0.56 deg/s: −3.32, −3.12, −3.27, −4.48, −3.89 | n/a (no beats) | n/a (no beats) |
| Median beat SPV, **sign corrected** | **+3.62 deg/s, rightward = with the stimulus** | n/a | n/a |
| OKN-positive windows | **0 / 17 in every trial** | 0 / 17 | 0 / 17 |
| OKN-positive fraction | **0.00 in every trial** | 0.00 | 0.00 |
| Detector-valid samples | 100 % | 100 % | 100 % |
| Accepted slow-phase fits / all fits | 8 / 24 | 0 / 5 | 0 / 6 |

### Descriptive and exploratory measures (not detector output)

| Metric | A | B | C |
|---|---|---|---|
| Angle SD (deg) | **1.58 ± 0.36**: 1.55, 1.96, 1.89, 1.44, 1.07 | 0.51 ± 0.12: 0.46, 0.54, 0.34, 0.61, 0.62 | 0.51 ± 0.15: 0.54, 0.55, 0.34, 0.30, 0.65, 0.67 |
| 99th percentile of \|velocity\| (deg/s) | 52.5 ± 9.8 | 10.4 ± 6.2 | 10.4 ± 3.5 |
| \|velocity\| peaks > 20 deg/s per trial | **8.8 ± 2.3**: 8, 8, 12, 10, 6 | 0.2 ± 0.45: 1, 0, 0, 0, 0 | 0.67 ± 0.52: 1, 1, 1, 0, 1, 0 |
| Beats if the fast threshold were 20 deg/s | 4.8 ± 1.9: 5, 4, 7, 6, 2 | 0 | 0 |
| OKN fraction if the fast threshold were 20 deg/s | 0.47 ± 0.31: 0.40, 0.45, 0.80, 0.70, 0.00 | 0 | 0 |

Per-trial values for everything: [`metrics_per_trial.csv`](metrics_per_trial.csv).
Summary values: [`condition_summary.csv`](condition_summary.csv). Full detector
reports: [`detector_output/`](detector_output/).

### Answers to the comparison questions

1. **Does A produce more beats than B and C?** Yes, but the counts are tiny.
   Every A trial has at least 1 beat and every B and C trial has 0, so there's
   no overlap. Fast phases (2–6 vs 0–1), angle SD (≥ 1.07° vs ≤ 0.67°) and
   velocity peaks (6–12 vs 0–1) also don't overlap between A and B/C. With
   n = 5 vs 11 from one person, that is a strong separation but not a
   statistical result.
2. **Does B suppress OKN relative to A?** Yes, completely, in this
   participant. B's traces are as flat as C's: angle SD 0.51 vs 0.51°, the same
   velocity percentiles, no sawtooth. The only B fast phase (T07, t ≈ 0.0 s) is
   a start-of-trial transient, not OKN. There was no OKN breakthrough here, but
   that may not hold for other participants.
3. **Does C produce very few detections?** Yes: zero fast phases, beats or
   windows in all 6 trials.
4. **Consistent across repetitions?** Yes, qualitatively. All 5 A trials show
   the sawtooth and none of the 11 B/C trials do. T20 (the last A trial) is the
   weakest: 6 peaks over 20 deg/s, and 0 OKN fraction even at the exploratory
   threshold. That could be fatigue or adaptation, but n = 1 per round can't
   show it.
5. **Do the plots support the detector's classifications?** Partly:
   - **For B and C, yes:** the traces are flat, matching "no OKN".
   - **For A, no:** every A trial shows a regular sawtooth with about 6–12
     resets of about 2–4°. The detector marks only 2–6 of them as fast phases,
     accepts 1–2 beats, and declares **no OKN windows**. See
     [batch2_representative_ABC.png](figures/batch2_representative_ABC.png):
     T16 has about 11 visible resets, 3 detected fast phases and 1 beat.
6. **Is the difference explained by tracking quality?** No. All 16 trials have
   100 % tracking, no gaps, no blinks and identical sampling. The B and C noise
   floors are the same. The A vs B/C difference is in the eye-movement signal
   itself.

---

## E. Representative figures

| Figure | What it shows |
|---|---|
| [batch1_validation_traces.png](figures/batch1_validation_traces.png) | Clean steps and square waves for deliberate gaze, with the sign inversion visible; the two eyes overlap with a ~4° offset; the blink artefacts in V5 |
| [batch1_V5_blinks.png](figures/batch1_V5_blinks.png) | Each blink coefficient peak lines up with a ~9° fake angle swing; the mask removes them |
| [batch2_all_traces.png](figures/batch2_all_traces.png) | **The main result:** all 16 Batch 2 traces in recording order. Every blue (A) trace shows a sawtooth; orange (B) and grey (C) are flat. Few resets are marked as fast phases |
| [batch2_representative_ABC.png](figures/batch2_representative_ABC.png) | One median trial per condition with velocity: A's reset peaks mostly sit between 20 and 40 deg/s, under the threshold |
| [batch2_velocity_peaks.png](figures/batch2_velocity_peaks.png) | Exploratory: 61 velocity peaks in A, only 19 above 40 deg/s; B and C peaks are all below 40 and mostly below 20 |
| [batch2_condition_comparison.png](figures/batch2_condition_comparison.png) | Every trial plotted per metric and condition, with mean ± SD |
| [batch2_beat_timing.png](figures/batch2_beat_timing.png) | Beats occur throughout the trial, including after 8 s when the background is below 0.2 sRGB |
| `figures/trials/Txx_*_gaze.png`, `*_okn.png` | Standard `plot_gaze.py` and `detect_okn.py` plots for all 21 trials |

---

## F. Detector evaluation: four kinds of observation

Here "confirmed" means visible in the raw traces and explained. It does not
mean validated against labelled ground truth. No sensitivity, specificity or
accuracy figure is claimed.

| Type | Observation | Evidence |
|---|---|---|
| **Confirmed measurement issue** | The detector's sign convention is inverted (+ is the subject's left) | T02 and T03 steps (§C) |
| **Confirmed measurement issue** | Left- and right-eye signals aren't independent | r ≥ 0.989, constant 4° offset |
| **Confirmed measurement issue** | Blinks produce ~9° fake gaze swings | T05: 15 of 15 blinks |
| **Confirmed measurement issue** | Peak speed is about half normal saccade speed | T04: 10–12° saccades peak at 160–195 deg/s |
| **Suspected detector error: missed beats** | The 40 deg/s threshold misses about 2/3 of the A resets (42 of 61 peaks fall under it) | velocity-peak figure |
| **Suspected detector error: cascade** | An undetected reset stays inside the "slow phase", so the fit covers several saw teeth. 16 of 24 A slow-phase fits are rejected (R² 0.00–0.79, often marked "too slow" because the net slope cancels out) | `detector_output/T*_A*.txt` |
| **Suspected detector error: windows unreachable** | "≥ 2 beats in 2 s" can't be met at 1–2 beats per 10 s, so the OKN fraction is 0 even in clear A trials | condition table |
| **Detector behaving correctly** | No false positives in B or C (0 beats in 11 trials); blink masking prevents blink detections | condition table; T05 |
| **Physiologically plausible** | With the sign corrected, A slow phases go **rightward with the stimulus** at **+3.1 to +4.5 deg/s**. The stimulus is about 4.0 deg/s at an assumed 30 cm (3.0 at 40 cm, 4.8 at 25 cm), so gain is roughly 0.8–1.1 *if* ARKit's angle scale is right | beat SPVs |
| **Physiologically plausible** | Fixating a dot completely suppresses OKN to a moving grating (B looks the same as C) | B vs C metrics |
| **Physiologically plausible** | OKN continues into the dim end of the fade (beats at 9.0 and 9.45 s, background < 0.1) | beat-timing figure |
| **Uncertain, needs manual annotation** | How many true resets are in each A trial (my visual estimate is ~6–12); whether some small A peaks are noise | — |
| **Uncertain, needs manual annotation** | Whether the T07 fast phase at t ≈ 0 is a refixation or an artefact | T07 |
| **Uncertain, needs manual annotation** | Why T20 is weaker | T20 |
| **Uncertain, needs manual annotation** | Whether ARKit compresses amplitude (§C) | — |
| Not testable | Sensitivity to tracking loss: no tracking loss happened in this session | — |

---

## G. Limitations

- **One participant, one session, 5–6 trials per condition.** No result
  generalises. Means and SDs only describe these trials.
- **No ground truth.** There is no reference eye tracker, no video and no
  manual labels, so detector accuracy can't be measured.
- **ARKit uncertainties:**
  - the gaze signal is uncalibrated, and its angle scale and offset are unknown
    (centre was −5.8°, not 0°);
  - peak velocity is underestimated;
  - the two eyes aren't independent;
  - there are blink artefacts;
  - its internal smoothing is unknown.
- **Uncalibrated stimulus:**
  - speed and spatial frequency are in points, and the viewing distance wasn't
    recorded, so deg/s and gain are estimates;
  - the background values are scheduled sRGB codes, not measured luminance;
  - the fade ties luminance to time within each trial;
  - only the rightward direction was tested, so a sign-independent check of
    direction (leftward stimulus produces leftward slow phases) isn't possible.
- **Timing:** the timestamps are frame-locked, and the stimulus state is the
  scheduled one, not a confirmed displayed frame.
- **Protocol:**
  - the order deviated in rounds 4–5, and one C trial is extra;
  - the whole session was about 8 minutes, so fatigue or adaptation effects
    can't be ruled out (T20 is the weakest A trial);
  - 10 s trials contain only 6–12 OKN cycles.

## H. Next steps (ranked by the problems actually observed)

1. **Fix detection sensitivity, guided by labels.** Most visible resets are
   missed, which leads to 0 OKN windows. Suggested order:
   - Manually annotate the resets in the 5 A trials (and a few B and C trials)
     before changing anything.
   - Tune on part of the data and evaluate on held-out trials: fast-phase
     threshold (the 20–25 deg/s range looks promising, since B/C peaks are
     almost all < 20), slow-phase fit gates, and window rule (2 beats per 2 s
     can't be met at about 1 reset per second).
   - The fixed 40 deg/s threshold doesn't suit an ARKit signal whose saccades
     peak at about half normal speed.
   - Plain thresholds and labels are enough. **ML isn't justified yet**: the
     signal is clean and the failure has a simple, identified cause.
2. **Fix and verify the coordinate convention, and add calibration.**
   - Flip the sign in `detect_okn.py` and correct the `lookat_x_m`
     documentation, but only after a confirmation trial.
   - Add a calibration task with dots at known screen positions.
   - Record viewing distance, either measured or from ARKit's face-anchor
     transform, so angles, deg/s and OKN gain mean something.
3. **Make the protocol stronger and harder to get wrong:**
   - Have the app run the planned trial sequence itself, to prevent order errors.
   - Add **leftward** trials: slow phases that reverse with the stimulus are the
     strongest single test that this is OKN.
   - Use longer trials (20–30 s) and a constant background for the A/B/C
     comparison, with contrast changes as a separate experiment.
   - Recruit more participants.

## I. Research questions

1. **Can we reliably measure deliberate horizontal eye movements with ARKit?**
   **Direction and timing: yes.** 2 of 2 step trials go the expected way, 7
   switches are clean in T04, the fixation noise floor is 0.36° SD, and
   tracking is 100 %. **Amplitude, true velocity and per-eye differences: not
   yet.** There are no targets or distance, saccade peaks are about half normal
   speed, and the eyes are perfectly coupled. The sign was inverted relative to
   the code's assumption.
2. **Does the detector find plausible OKN in moving-grating trials?**
   **Partly.** The 6 beats it accepts across 5 A trials have the right direction
   (after the sign correction) and a plausible speed (+3.1 to +4.5 deg/s, versus
   about 4 deg/s estimated for the stimulus). But they are a small fraction of
   the visible resets, and it reports **0 OKN windows in every trial**. As a
   trial-level OKN classifier at default settings, it fails on A trials.
3. **Are the three conditions distinguishable?** **A vs B/C: yes**, using beat
   count, fast-phase count, angle SD or velocity peaks, with no overlap in 5 vs
   11 trials. The detector's main output (OKN fraction) doesn't separate them:
   it is 0 everywhere. **B vs C: no.** Fixation suppressed OKN fully, which is
   a real result for this participant rather than a failure.
4. **Largest bottleneck?** **Detection**, then **calibration** (sign, scale,
   distance), then stimulus design (direction, duration, fade). Tracking quality
   was not the limit in this session, though ARKit's low peak velocity is the
   reason the detector's threshold is wrong.
5. **Strongest claim the data supports.** *"In one participant, iPhone ARKit
   face tracking recorded an OKN-like sawtooth during free viewing of drifting
   bars in 5 of 5 trials. No sawtooth appeared in 11 of 11 trials where the
   participant fixated a stationary dot over moving or still bars. Under the
   empirically corrected sign, slow phases followed the stimulus direction at
   about the stimulus speed."* This is feasibility evidence only, with n = 1
   and no reference measurement.
6. **Evidence still missing for a credible proposal:**
   - multiple participants;
   - comparison against a reference eye tracker or EOG, or at least
     frame-accurate manual labels;
   - direction-reversal trials;
   - known-target calibration and measured viewing distance;
   - a detector tuned and tested on held-out labelled data;
   - repeat sessions to check reliability;
   - for any contrast-sensitivity aim: calibrated luminance and contrast,
     several spatial frequencies, and a threshold procedure.

**Enough for a preliminary proposal?** Yes for a **feasibility proposal**: the
A vs B/C contrast is clear and reproducible within this session, and the
remaining problems are specific and fixable. Not enough for any claim about
detector accuracy, clinical use or contrast sensitivity.
