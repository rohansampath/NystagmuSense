# Pilot 03 — first OKN detector benchmark (development only)

**Detector:** the SG fast-phase detector in `scripts/detect_okn.py`. Only
`fast_threshold` was varied; every other parameter stayed at its default.

**Scope:**
- Every number here comes from the 28 **development** recordings.
- The 12 held-out evaluation recordings have not been scored or looked at.

**Labels:** human-reviewed events visible in the ARKit signal, made by one
annotator. They are not physiological ground truth.

## Dataset

The 49 recordings are described in `manifest.csv`. All 45 annotated recordings
are complete, manual (suggestions hidden), and checked:
- every annotation points at the right CSV;
- every event lies within the recording's time range;
- there are no duplicate reviews or events and no unknown labels;
- the per-trial counts in `reviews.csv` agree with `events.csv`.

| | Count | Notes |
|---|---|---|
| Primary | 40 | 20 per participant |
| Extra | 5 | P01 T022, T026; P02 T046, T048, T055. Recorded after the planned count, kept for exploratory use |
| Excluded | 4 | P01 T008–T010, moved to `_excluded_P03/` by the experimenter; P01 T056, technical failure (1 % face-tracked), not annotated |

Per participant, the primary set has:
- 4 OKN · Right and 4 OKN · Left;
- 3 Dot + moving · Right and 3 Dot + moving · Left;
- 6 Dot + still.

Eligibility uses recording order and technical checks only. Weak or irregular
traces were never a reason to exclude a recording.

**Labels in the primary 40:**

| | OKN | Dot + moving | Dot + still |
|---|---|---|---|
| P01 | 48 | 52 | 0 |
| P02 | 79 | 35 | 0 |

There are no `uncertain` or `artifact` labels in the final set.

## Split (seed 20261105, frozen before any detector output was viewed)

| | Development (28) | Evaluation (12) |
|---|---|---|
| P01 OKN · Left | T012 T013 T014 | T011 |
| P01 OKN · Right | T015 T016 T017 | T018 |
| P01 Dot + moving · Left | T024 T025 | T023 |
| P01 Dot + moving · Right | T019 T020 | T021 |
| P01 Dot + still | T027 T029 T030 T032 | T028 T031 |
| P02 OKN · Left | T033 T034 T036 | T035 |
| P02 OKN · Right | T037 T039 T040 | T038 |
| P02 Dot + moving · Left | T041 T042 | T045 |
| P02 Dot + moving · Right | T043 T044 | T047 |
| P02 Dot + still | T049 T051 T053 T054 | T050 T052 |

Both participants are on both sides of the split. This tests new recordings
from known people, not generalisation to unseen people.

## Scoring

- **Matching:** detector fast-phase starts are matched one-to-one to
  `fast_phase` labels within ±100 ms.
- **Metrics:** TP, FP and FN are pooled over trials. F1 = 2TP / (2TP + FP + FN).
- **Masked labels:** predictions within 100 ms of an `uncertain` or `artifact`
  label are left unscored, and those labels are never counted as misses. None
  are present in this set.
- **Still-stripe trials:** they add only false positives and never raise F1.
  For them recall is undefined and F1 has no meaning, so read them through
  false positives per 10 s.

## Threshold sweep (`threshold_sweep.csv`, `threshold_sweep.png`)

| deg/s | Precision | Recall | F1 | FP / 10 s | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| 10 | 0.23 | 0.91 | 0.36 | 17.9 | 146 | 499 | 14 |
| 16 | 0.38 | 0.72 | 0.50 | 6.8 | 116 | 190 | 44 |
| 20 | 0.50 | 0.64 | 0.56 | 3.8 | 103 | 105 | 57 |
| 22 | 0.57 | 0.61 | 0.59 | 2.7 | 97 | 74 | 63 |
| **24 (chosen)** | **0.60** | **0.57** | **0.59** | **2.2** | 92 | 62 | 68 |
| 28 | 0.60 | 0.49 | 0.54 | 1.9 | 79 | 52 | 81 |
| 32 | 0.63 | 0.44 | 0.52 | 1.5 | 71 | 42 | 89 |
| 36 | 0.71 | 0.38 | 0.50 | 0.9 | 61 | 25 | 99 |
| **40 (baseline)** | **0.72** | **0.33** | **0.45** | **0.75** | 53 | 21 | 107 |

**How 24 was chosen:** the rule was fixed before the sweep (highest F1; ties
within 0.01 go to fewer FP per 10 s, then to the higher threshold). 22 and 24
tie on F1 (0.587 vs 0.586), and 24 has fewer false positives.

**Change from 40 to 24 deg/s:**
- Precision −0.12;
- recall +0.25;
- F1 +0.13.

**By condition and participant:**

| | 40 deg/s P / R / F1 · FP/10 s | 24 deg/s P / R / F1 · FP/10 s |
|---|---|---|
| OKN (12 trials) | 0.75 / 0.49 / 0.59 · 1.34 | 0.65 / 0.83 / **0.73** · 3.69 |
| Dot + moving (8) | 0.44 / 0.07 / 0.12 · 0.63 | 0.39 / 0.15 / 0.22 · 1.76 |
| Dot + still (8) | no resets · **0.00** | no resets · **0.50** |
| P01 (14) | 0.86 / 0.25 / 0.39 · 0.22 | 0.72 / 0.51 / 0.59 · 1.08 |
| P02 (14) | 0.65 / 0.40 / 0.50 · 1.29 | 0.54 / 0.64 / 0.58 · 3.38 |

- **OKN:** P01 reaches F1 0.83 and P02 0.67 at 24 deg/s.
- **Dot + moving:** both participants stay below 0.30 at every threshold from 10 to 40.

**False positives on the control conditions at 24 deg/s** (`false_positives.png`):
- Dot + still: 4 in 8 trials, 0.50 per 10 s.
- Dot + moving: 14 in 8 trials, 1.76 per 10 s.

## Failure cases (`failure_cases.csv`, `failure_summary.csv`, `failure_examples.png`)

**How errors were classified:**
- Every development error at 24 deg/s was classified from the signal.
- The expected reset direction was measured from matched OKN fast phases:
  - stripes Left → reset in the detector's − direction (41 of 42);
  - stripes Right → reset in the + direction (40 of 41).

| Error | Count | Main cause |
|---|---|---|
| OKN miss | 17 | 12 have a raw peak above 24 deg/s that SG smoothing (5 samples ≈ 83 ms) pulls below it; 5 are small movements |
| OKN false positive | 44 | 29 jump *with* the stripes (wrong direction for a reset); 15 are the right direction but have no qualified slow phase before them |
| Dot + moving miss | 51 | 43 have a peak below 24 deg/s even unsmoothed (≈ 1° deflections); 6 are SG-attenuated; 2 were detected 100–200 ms away |
| Dot + moving false positive | 14 | 10 in the wrong direction |
| Dot + still false positive | 4 | isolated saccades or noise; one is the first sample of a trial |

**Causes ranked:**
1. **Ignoring the reset direction.** The detector reports every fast movement,
   whichever way it goes. Keeping only fast phases that run against the
   stripes would change the development result as follows:

   | | TP | FP | Precision | Recall | F1 |
   |---|---|---|---|---|---|
   | Now | 92 | 62 | 0.60 | 0.57 | 0.59 |
   | With direction check | 90 | 22 | 0.80 | 0.56 | 0.66 |

   This is a diagnostic, not a tuned detector.
2. **Velocity threshold versus SG smoothing.** Most OKN misses are short
   resets whose peak the 5-sample SG filter spreads out. Lowering the threshold
   recovers them, but it also admits noise.
3. **Dot + moving labels at the noise floor.** Most missed labels are ≈ 1°
   deflections that never reach 24 deg/s in either the smoothed or raw signal.
   Either the detector can't see these resets, or some labels are noise. No
   threshold fixes this, and the labels should be second-reviewed.
4. **Slow-phase validation is too strict to use as a gate.** Requiring a
   qualified slow phase (a "beat") removes every false positive, but it keeps
   only 12 of 160 resets: precision 1.00, recall 0.07. The line-fit (R² ≥ 0.8)
   and duration gates reject most real slow phases in this noisy signal.
5. **Minimum event separation** contributes almost nothing. Only 2 errors are
   timing near-misses, and no labels are closer than 100 ms.
6. **Noise and artifacts** are minor. 16 of the 62 false positives sit
   next to masked (blink or untracked) data.

**Recommended next change.** Restrict predictions to fast phases in the
expected reset direction. The detector already knows the stripe direction (it
computes `stimulus`) and the sign of each fast phase. Two rules apply:
- Dot + still trials keep every fast phase, since they have no expected direction.
- The threshold then needs to be re-swept on development data, because it was
  chosen without the direction check.

Leave the smoothing and the beat gate for a later step.

## Is SG threshold tuning enough?

**Partly.**
- **OKN:** lowering the threshold from 40 to 24 deg/s is a real gain, with F1
  rising from 0.59 to 0.73.
- **Overall:** F1 plateaus at 0.59. Below that point every extra true reset
  costs about one false positive.
- **Dot + moving:** recall stays at or below 0.15 at any threshold where
  false positives are tolerable.

The threshold alone can't separate resets from same-sized movements in the
wrong direction. The direction check is the next lever.

## Limitations

- **Annotators:** one annotator labelled everything, and there is no
  inter-rater agreement yet. The Dot + moving labels (P01: 52 labels on traces
  of about ±1°) are the least certain.
- **Sample size and generalisation:**
  - two participants;
  - 28 development recordings;
  - one session each;
  - known participants on both sides of the split.
- **Signal:** labels mark what is visible in ARKit's uncalibrated gaze angle
  at about 60 Hz. Short resets may be undersampled.
- **Selection and evaluation:** the threshold was picked on development data,
  so the 24 deg/s numbers are optimistic. The held-out evaluation split should
  be scored once, with `--allow-evaluation`, after the detector is frozen.

## Reproduce

```bash
cd NystagmuSense-bench   # branch feature/p03-benchmark
PY=/Applications/anaconda3/anaconda3/bin/python   # any Python with numpy, scipy, matplotlib
T=~/CS_Projects/NystagmuSense/trials
L=~/CS_Projects/NystagmuSense-annot/analysis/annotations_p03

$PY analysis/pilot_03/build_manifest.py --trials-dir $T --check
$PY scripts/sweep_okn_threshold.py --manifest analysis/pilot_03/manifest.csv \
    --labels-dir $L --trials-dir $T --output-dir analysis/pilot_03
$PY analysis/pilot_03/failure_cases.py --labels-dir $L --trials-dir $T --threshold 24
```

**Where the data lives:**
- **Raw recordings:** stay in the git-ignored `trials/` folder.
- **Human labels:** `NystagmuSense-annot/analysis/annotations_p03/`. They are
  not committed to this branch.
- **Label backup:** a private dated copy is kept in
  `~/CS_Projects/NystagmuSense-private/annotations_p03_backups/`. Its SHA-256
  values are:
  - `events.csv`: e0383a22…14fb95
  - `reviews.csv`: 104344d9…8a1ae
