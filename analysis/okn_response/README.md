# Trial-level OKN response: slow-phase velocity and direction consistency

**Question:** can a 10 s iPhone ARKit recording tell a stimulus-driven OKN
response apart from ordinary fixation movements, using trial-level response
measures instead of individual reset detection?

**Status:** exploratory.
- **Data:** the existing Pilot 03 (40) and Pilot 04 (60) primary recordings.
- **Already used:** Pilot 04 has been used for validation and an SG study, and
  the 12 Pilot 03 held-out recordings were already scored once.
- **Detector:** the frozen detector (SG window 5, order 2, 22 deg/s, direction
  check) is used unchanged.
- **Labels:** no manual labels are used. The target is the **experimental
  condition**, which is a proxy for OKN presence, not independent ground truth.

**Reproduce:**
`python3 analysis/okn_response/analyze_response.py`. The analysis rules were
committed before the first run (`0eb76b8`).

## Metrics (`response_metrics.py`)

| | Metric | Definition | Units |
|---|---|---|---|
| A | Fast-phase rate | frozen-detector fast phases that oppose the stimulus, per 10 s of **valid** (tracked, unmasked) time; all fast phases also reported | per 10 s |
| B | Aligned slow-phase velocity | median of the frozen detector's SG velocity over **slow-phase samples** (see below), multiplied by the expected slow-phase sign, so > 0 means drifting with the stripes | deg/s (ARKit eye angle) |
| C | Slow-phase direction consistency | share of slow-phase samples whose velocity has the expected slow-phase sign; 0.5 = chance | fraction |
| – | Also reported | mean / median / mean \|v\|, SD (within-trial variability), share of slow-phase samples, reset consistency (share of fast phases opposing the stimulus), apparent gain | |

**Slow-phase samples** must meet all of these:
- valid samples inside a continuous run, never across a blink, tracking loss
  or frame gap;
- finite SG velocity with |v| ≤ 22 deg/s;
- more than 50 ms from any detected fast phase, in **either** direction, so
  saccades and resets and their SG-smeared edges are excluded.

If under 1 s of slow-phase samples remains, B, C and gain are **unavailable**,
never 0. In this dataset all 100 recordings had enough.

**Sign convention:** the reset sign equals the stimulus sign in the eye angle.
Re-checked here: the median slow-phase drift has the opposite sign to the
stimulus in **100 %** of the 40 OKN recordings, and it reverses between left
and right (see `direction_consistency.png`).

**Still stripes have no stimulus direction, so none is invented.** A, B and C
are computed for **both** hypothetical directions and the larger value is used.
A still control is therefore scored at its best case, which makes the
specificity estimates conservative. Direction-free statistics (|median v|, all
fast phases) are in `trial_metrics.csv`.

**Relation to published work:** these are simple, explicitly defined
measures, *in the spirit of*:
- slow-phase velocity estimation in EyePhone-type work;
- detecting fast phases, then checking the slow phase (Essig et al.);
- stimulus-direction consistency (Dakin & Turnbull).

They are **not** implementations of those papers' published definitions,
which were not checked here.

### Gain

`apparent_gain` = aligned slow-phase velocity divided by the stimulus angular
velocity at screen centre. The stimulus velocity comes from:
- `speedPointsPerSecond` (126);
- the device's point size, known only for `iPhone17,1` (iPhone 16 Pro, 460 ppi
  at 3× → 0.166 mm/pt), giving 20.9 mm/s;
- ARKit's median face distance.

The result is about 4.1–4.8 deg/s. Gain is `None` for an unknown device, a
missing distance or still stripes.

**This is not a physiological gain:**
- the ARKit eye angle is uncalibrated;
- the face distance is camera-to-eyes, not eye-to-screen-centre;
- off-centre angular speed differs.

Real gain needs a gaze calibration, with known fixation targets, and a
measured viewing geometry.

## Results (100 recordings: 40 OKN, 36 Dot + moving, 24 Dot + still)

**By condition (median):**

| | OKN | Dot + moving | Dot + still (best case) |
|---|---|---|---|
| A rate (per 10 s) | 6.0 | 1.0 | 1.0 |
| B aligned velocity (deg/s) | **1.53** | 0.05 | 0.18 |
| C consistency | **0.64** | 0.50 | 0.52 |
| Apparent gain | 0.33 | 0.01 | – |

**By participant (median):**

| | OKN B | OKN C | Still B | Still C | OKN gain |
|---|---|---|---|---|---|
| P01 | 1.42 | 0.61 | 0.23 | 0.52 | 0.32 |
| P02 | 1.62 | 0.66 | 0.21 | 0.52 | 0.34 |
| P03 | 1.71 | 0.67 | 0.13 | 0.52 | 0.41 |

**OKN vs Dot + still, ROC-AUC** (bootstrap 95 %; no threshold needed):

| Score | All | P01 | P02 | P03 | Pilot 03 | Pilot 04 |
|---|---|---|---|---|---|---|
| A fast-phase rate | 0.92 (0.83–1.00) | 0.84 | 0.95 | 1.00 | 1.00 | 0.84 |
| **B aligned slow-phase velocity** | **0.97 (0.92–1.00)** | 0.92 | 0.98 | 1.00 | 1.00 | 0.94 |
| C slow-phase consistency | 0.97 (0.91–1.00) | 0.93 | 0.98 | 1.00 | 1.00 | 0.94 |

**Trial-level rules** (threshold chosen on the other two participants,
leave-one-participant-out; `classification.csv`):

| Rule | Sensitivity | Specificity | Balanced accuracy | TP / FN / TN / FP | P01 still trials called OKN | Dot + moving called OKN |
|---|---|---|---|---|---|---|
| A rate ≥ ~3.0 per 10 s | 0.95 | 0.88 | 0.91 | 38 / 2 / 21 / 3 | **3 / 10** | 17 % |
| **B velocity ≥ 0.57–1.0 deg/s** | 0.85 | **1.00** | **0.93** | 34 / 6 / 24 / 0 | **0 / 10** | 0 % |
| C consistency ≥ ~0.55 | 0.88 | 0.88 | 0.88 | 35 / 5 / 21 / 3 | 1 / 10 | 6 % |
| D = B and C | 0.85 | 1.00 | 0.93 | 34 / 6 / 24 / 0 | 0 / 10 | 0 % |

**Per participant (B):** sensitivity P01 0.69, P02 0.94, P03 1.00;
specificity 1.00 for every participant and both pilots.

**Threshold instability for B:** the threshold chosen without P01 was
1.0 deg/s; the other two folds chose 0.57. P01's Pilot 04 OKN trials have
weak drift (0.04–0.78 deg/s in 5 of 8), so the strict threshold misses them.

**Robustness:**

| Check | Result |
|---|---|
| Missed fast phases | excluding only resets found at 40 deg/s (many missed) leaves AUC unchanged: B 0.968, C 0.960 |
| Tracking quality | every recording was ≥ 93.6 % valid, and only 2 were under 95 %, so this data can't test it |

## What the results mean

1. **Regular OKN separates from still-stripe controls far better at trial
   level than by reset detection.** Slow-phase velocity and direction
   consistency give AUC 0.97 and reverse correctly with stimulus direction in
   every OKN recording.
2. **P01's false-positive problem disappears at trial level** with B: 0 of 10
   still trials are called OKN, against 3 of 10 by fast-phase rate. P01's
   extra still-stripe "fast phases" are saccades without a sustained
   stimulus-locked drift.
3. **Dot + moving shows essentially no measurable OKN** in these recordings:
   - median aligned velocity 0.05 deg/s;
   - consistency 0.50;
   - drift sign matches the stimulus in only 61 % of trials, near chance.

   Fixation appears to suppress the response below what ARKit resolves here.
   This is a finding about these participants and this task, not a reason to
   treat the condition as a negative. It was never used as one.
4. **Fast-phase rate is the weakest of the three measures,** most hurt by one
   participant's saccades.

## Limitations

- **Condition, not ground truth:** OKN and still-stripe trials differ in
  instruction ("watch the stripes" vs "look at the dot") as well as stimulus
  motion. Separating them doesn't prove the measures detect OKN rather than
  task-dependent eye behaviour. The direction reversal (left vs right) is the
  stronger evidence, because it doesn't depend on the instruction.
- **Few people:** three participants, two of whom (P01, P02) appear in both
  pilots. Folds hold out a whole person (both pilots), but there are only
  three. These are not independent generalisation estimates, and any rule
  chosen here needs a fresh cohort.
- **Everything at full contrast,** with one stimulus speed.
- **Uncalibrated units:** ARKit eye angle at about 60 Hz; gain is apparent
  only.
- **Not a diagnostic:** nothing here is clinical accuracy.

## Readiness for contrast sensitivity

**Verdict: promising, and ready for a *small exploratory* contrast series,**
not for threshold claims.

**For:**
- a reliable, direction-reversing, continuous response score (B) at full
  contrast;
- robust to missed resets;
- consistent across three people, with P01's Pilot 04 trials the weakest.

**Design the contrast series so it also removes the instruction confound:**
- the same "watch the stripes" instruction at every level, including a 0 %
  (blank) level as the null;
- both directions at every level;
- B and C, defined exactly as here, frozen before collection as the response
  scores;
- photometric luminance and contrast measured on the screen.

**The question to answer:** does B fall monotonically with contrast within
each participant, and is it repeatable?

## Files

| File | Contents |
|---|---|
| `trial_metrics.csv` | per-recording metrics; no samples or labels |
| `condition_summary.csv` | median and IQR per pilot × condition |
| `participant_summary.csv` | median and IQR per participant × condition |
| `classification.csv` | AUCs, and the leave-one-participant-out rule results with thresholds |
| `response_comparison.png` | the three metrics by condition |
| `direction_consistency.png` | left/right reversal, and consistency by participant |
