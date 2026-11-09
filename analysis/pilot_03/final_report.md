# Pilot 03: final report

**Scope:** frozen OKN fast-phase detector and one-time held-out evaluation.

**Status:** exploratory pilot with two participants. Labels are from one
annotator and describe eye movements visible in ARKit's gaze estimate. They
are not physiological ground truth. Nothing here indicates clinical accuracy.

## 1. Objective

NystagmuSense aims to estimate motion contrast sensitivity from optokinetic
nystagmus (OKN), using only an iPhone's front-camera ARKit eye tracking.

Pilot 03 asks a narrower question: on a full-contrast stimulus, how well does
an interpretable detector find the OKN fast phases (resets) that a human marks
in the ARKit signal?

## 2. Recording protocol (`docs/PILOT_03.md`)

**Stimulus:**
- black bars on a constant white background, maximum display contrast;
- bar width 2 % of the screen, period 2.4 × bar width;
- 126 pt/s, about 0.6–0.75 cycles/deg at about 4.0–4.8 deg/s at 25–30 cm (geometry estimates; not photometrically measured);
- 10 s per trial, landscape;
- viewing distance 25–30 cm, checked before each trial.

**Phone:** a single iPhone with fixed brightness. Auto-Brightness, True Tone and Night Shift are off.

**Signal:** ARKit face tracking at 60.01 Hz. Horizontal eye angle comes from the eye transforms.

**Conditions per participant:**
- **OKN:** watch the stripes. 4 Right and 4 Left.
- **Dot + moving:** fixate a centred dot while the stripes move. 3 Right and 3 Left.
- **Dot + still:** fixate the dot while the stripes are stationary. 6 trials.

Trial order is balanced across each half of the session.

## 3. Dataset (`manifest.csv`, built from file names and sidecars only)

| | n | |
|---|---|---|
| Primary | 40 | P01 and P02, 20 each, exactly the planned cells |
| Extra | 5 | recorded after the planned count; exploratory only |
| Excluded | 4 | P01 T008–T010 set aside by the experimenter; P01 T056 technical failure (1 % face-tracked) |

Every primary recording passed the technical checks:
- metadata matches the file name;
- correct stimulus;
- at least 570 samples;
- at least 90 % face-tracked;
- increasing timestamps;
- no logged issues.

Irregular eye traces were never a reason to exclude a recording.

## 4. Annotation

**Process:**
- One annotator (AA) labelled every primary recording in independent mode.
  Detector suggestions are never computed in that mode, and held-out trials
  can't show them.
- Labels:
  - `fast_phase` marks a reset *against* the stripe motion, after a drift *with* it;
  - `uncertain` marks a doubtful candidate;
  - `artifact` marks a blink or tracking glitch.
- All 40 recordings are complete reviews. Every label maps to its own recording
  and falls inside it, and there are no duplicates.

**Label counts in the primary set:**

| | Labels |
|---|---|
| OKN | 127 |
| Dot + moving | 87 |
| Dot + still | 0 |
| `uncertain` / `artifact` | 0 |

**Label storage:** private and git-ignored, at `analysis/annotations_p03/`. A
checksum-verified local backup is at
`~/NystagmuSense-label-backups/20261106T193526Z/`.

**Limitation:** the evaluation uses manually reviewed annotations from one
annotator. Inter-annotator reliability was not measured, and these labels
should not be interpreted as independently verified physiological ground
truth.

The Dot + moving labels are the least certain. Their median step is 1.3°,
against 3.2° for OKN, and a third are under 1°. They are reported separately.

## 5. Development / evaluation split

**Method:** seed 20261105, a stratified random draw within each participant ×
condition × direction cell. Frozen before any detector output was looked at.

| | Development (28) | Evaluation (12) |
|---|---|---|
| OKN · Left | P01 T012–T014; P02 T033, T034, T036 | P01 T011; P02 T035 |
| OKN · Right | P01 T015–T017; P02 T037, T039, T040 | P01 T018; P02 T038 |
| Dot + moving · Left | P01 T024, T025; P02 T041, T042 | P01 T023; P02 T045 |
| Dot + moving · Right | P01 T019, T020; P02 T043, T044 | P01 T021; P02 T047 |
| Dot + still | P01 T027, T029, T030, T032; P02 T049, T051, T053, T054 | P01 T028, T031; P02 T050, T052 |

Both participants appear on both sides of the split. The held-out set tests
new recordings from known people, not generalisation to unseen people.

**Deviation to disclose:** during annotation quality review (5 Nov), a plot of
every P03 recording's *labels* was shown, held-out trials included. It showed
labels on the eye trace only, never detector output. The labels were not
changed afterwards.

## 6–9. Detector development (development split only)

**Scoring** (all stages): one-to-one matching within ±100 ms; TP, FP and FN
pooled over recordings.

| Stage | Detector | Precision | Recall | F1 | FP / 10 s |
|---|---|---|---|---|---|
| Original | SG velocity > 40 deg/s | 0.72 | 0.33 | 0.45 | 0.75 |
| Threshold sweep (`benchmark_summary.md`) | SG > 24 deg/s | 0.60 | 0.57 | 0.59 | 2.23 |
| Direction check (`comparison_report.md`) | SG > 22 deg/s, resets against the stripes only | 0.79 | 0.59 | 0.67 | 0.90 |
| Butterworth (`filter_comparison/`) | BW 8 Hz > 20 deg/s, with direction | 0.83 | 0.59 | 0.69 | 0.68 |
| Butterworth + SG | 15 Hz > 22 deg/s, with direction | 0.82 | 0.59 | 0.69 | 0.75 |

**Threshold and direction:**
- Lowering the threshold recovered short resets that the 5-sample SG
  derivative attenuates.
- Requiring resets to run against the stripes removed most false positives.
  The sign relation was measured without labels.
- The direction check was the largest single gain, and it held when settings
  were chosen on one participant and tested on the other.

**Negative results:**
- **Butterworth** (5–15 Hz, before differentiation or before SG) plateaued at
  the same F1 of 0.68–0.69. It recovered only 1–2 of 15 SG-missed OKN resets,
  because SG is already a ~10 Hz low-pass differentiator.
- **Local piecewise-linear segmentation** found some sub-threshold resets, but
  fired on still-stripe saccades.

**Final selection: SG + direction at 22 deg/s** (`frozen_detector.md`).

**Disclosure:** BW+SG technically met the replacement rule declared before the
filter experiment (F1 +0.014, both participants no worse, cross-participant
+0.003). SG was kept anyway:
- the margin is about 4 events;
- participant-level performance is comparable;
- SG is simpler, with no extra parameter, and causal.

## 10. Held-out performance (one run, 2026-11-08, commit `8da2e8a`)

**Run:** detector frozen and committed before scoring; run once with
`--allow-evaluation`; nothing changed afterwards.

**Outputs:** `heldout/heldout_report.txt`, `heldout/heldout_trials.csv`,
`heldout/summary.csv`, `heldout/dev_vs_heldout.png`.

| | Recordings | TP | FP | FN | Precision | Recall | F1 | FP / 10 s | Timing error |
|---|---|---|---|---|---|---|---|---|---|
| **Held-out** | 12 | 25 | 10 | 29 | **0.71** | **0.46** | **0.56** | 0.84 | 20 ms |
| Development (same code; not an independent test) | 28 | 94 | 25 | 66 | 0.79 | 0.59 | 0.67 | 0.90 | 20 ms |

**Uncertainty:** a bootstrap over recordings gives a held-out F1 95 % interval
of 0.29–0.75 (development 0.53–0.79). With 12 recordings and 54 labelled
resets, this is a rough estimate.

### 11. By participant (held-out)

| | Precision | Recall | F1 | FP / 10 s |
|---|---|---|---|---|
| P01 | 0.65 | 0.44 | 0.52 | 1.01 |
| P02 | 0.78 | 0.48 | 0.60 | 0.67 |

### 12. By condition and stimulus direction (held-out)

| | TP / FP / FN | Precision | Recall | F1 | FP / 10 s | Development F1 |
|---|---|---|---|---|---|---|
| OKN (4) | 20 / 2 / 7 | 0.91 | 0.74 | **0.82** | 0.50 | 0.85 |
| Dot + moving (4) | 5 / 4 / 22 | 0.56 | 0.19 | 0.28 | 1.01 | 0.25 |
| Dot + still (4, controls) | 0 / 4 / – | – | – | – | 1.01 | (0.88 FP / 10 s) |
| Left stripes (4) | 12 / 3 / 12 | 0.80 | 0.50 | 0.62 | 0.75 | 0.68 |
| Right stripes (4) | 13 / 3 / 17 | 0.81 | 0.43 | 0.57 | 0.75 | 0.70 |

### Interpretation

1. **Regular OKN generalises.** F1 is 0.82 against 0.85 in development, with
   precision 0.91. This is the condition the detector is meant for.
2. **The overall drop (0.67 → 0.56) is mostly about the mix of trials.**
   - Half of the held-out labels (27 of 54) come from Dot + moving trials,
     against 37 % in development.
   - Dot + moving recall is about 0.2 in both splits.
   - Two held-out Dot + moving trials (P01 T021, P02 T045) have 15 labels and
     not one correct detection.
   - Whether those labels are real resets is the open label question from §4.
     The detector and the labels can't be told apart on this evidence.
3. **False positives stay controlled.** 0.84 per 10 s overall, against 0.90 in
   development. Still-stripe controls give 4 false detections in 40 s
   (1.0 per 10 s), all isolated saccade-like movements, which no direction
   rule can remove.
4. **P02 does a little better than P01** (F1 0.60 vs 0.52). The difference is
   a handful of events.
   - P01's OKN is near perfect (recall 0.91).
   - P02 T038 (OKN Right) found only 3 of 7 resets, the short-reset failure
     mode from development.
5. **Timing:** detections start about 20 ms before the human mark, the same
   as in development.

## 13. Failure modes (from development analysis, consistent with held-out)

| Failure | Cause | Addressed? |
|---|---|---|
| Missed short resets | the 1–2 frame reset's velocity peak is spread by the SG derivative | lower threshold helps partly; filtering doesn't |
| Missed Dot + moving labels | about 1° deflections at the noise floor, never reaching 22 deg/s unsmoothed | not by threshold; the labels are unverified |
| Wrong-direction movements (largest original FP source) | detector reported every fast movement | **fixed by the direction check** |
| Still-stripe false positives | isolated saccades, sometimes at a tracking edge | by design not removable by direction |

## 14. Limitations

- **Sample:**
  - two participants, one session each;
  - both participants appear in both splits;
  - 40 recordings, 12 held out.
- **Labels and signal:**
  - one annotator, with no inter-rater reliability;
  - the Dot + moving labels are uncertain;
  - labels describe ARKit-visible movement, which is uncalibrated, about
    60 Hz, and has no reference eye tracker.
- **Stimulus:**
  - one full-contrast stimulus, so nothing here measures contrast sensitivity;
  - screen luminance and contrast were not measured photometrically.
- **Selection:**
  - the detector was chosen on development data, after several comparisons;
  - one design choice (SG over BW+SG) departed from a pre-set rule, as disclosed above.

## 15. Next research phase (plan only; nothing implemented here)

**Goal:** move from *finding resets* to *measuring OKN response strength*,
because that is what a contrast-response measurement needs.

### Measures (per trial, between detected fast phases)

1. **Slow-phase velocity (SPV):**
   - a robust (median, or trimmed mean) line fit to eye angle over each
     inter-reset segment;
   - only segments ≥ 150 ms;
   - excluding ±50 ms around detected fast phases and masked samples.

   This follows EyePhone-style SPV estimation.
2. **Direction consistency:** the time-weighted fraction of slow-phase
   segments drifting with the stimulus (sign = −reset sign), as in Dakin &
   Turnbull's stimulus-direction consistency.
3. **Gain:** median SPV divided by the stimulus angular velocity. The stimulus
   is about 4–5 deg/s; it should be computed per trial from the sidecar and the
   measured distance.

   ARKit's eye angle is uncalibrated, so gain is *relative*. Development
   slow-drift medians of about 1–3 deg/s suggest an apparent gain of about
   0.2–0.6 ^[estimate].
4. **Trial-level OKN response:** a detection-then-validation rule, in the
   spirit of Essig et al. A trial counts as responding if SPV direction
   consistency and |SPV| both exceed thresholds fixed in advance, with no
   tuned classifier.

### Experiment (Pilot 04)

- **Data:** reuse all Pilot 03 recordings, with no new data, to set and check
  the measures. OKN and Dot + moving trials are expected-response; Dot + still
  trials are the null.
- **Splits:** development settings must be chosen on development trials only.
  The 12 Pilot 03 evaluation recordings are **spent** and must not be used to
  tune these measures.
- **Then:** a small contrast series. Same stimulus at, for example, 4–5
  contrast levels, two or three participants, randomised order, with
  photometric luminance measurement of the screen.

### Evaluation criteria (to fix before looking)

- **Separation:** SPV and consistency separate OKN from Dot + still trials
  (AUC, plus effect size with interval).
- **Repeatability:** SPV and gain repeat within a participant (between-trial
  CV, and ICC once there are more participants).
- **Stimulus direction:** SPV sign follows the stimulus direction in ≥ 95 % of
  OKN trials.
- **Contrast series:** gain falls monotonically with contrast within each
  participant.

Keep the measures interpretable. No machine learning or new segmentation
unless a simple measure demonstrably fails.

## Reproduce

```bash
python3 analysis/pilot_03/build_manifest.py --trials-dir trials --check
# Development check (any time):
python3 scripts/evaluate_okn.py --manifest analysis/pilot_03/manifest.csv --split development \
    --labels-dir analysis/annotations_p03 --annotator AA --artifacts exclude --detector sg-direction
# Held-out: the command in frozen_detector.md was run once; don't run it again for tuning.
python3 analysis/pilot_03/heldout/summarize.py          # tables and figure from the saved per-trial CSVs
```
