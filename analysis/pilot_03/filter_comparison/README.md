# Pilot 03: SG vs. Butterworth vs. Butterworth + SG velocity

**Question:** does a Butterworth low-pass give a better eye-velocity estimate
for OKN reset detection than the 5-sample Savitzky–Golay derivative?

**What changes and what doesn't:** only the velocity estimate differs between
methods. Every method then uses the same downstream steps:
- the same fast-phase detection and merging from `detect_okn.py`;
- the same stimulus-direction check;
- the same scoring.

**Data:**
- the 28 primary **development** recordings in `../manifest.csv`, seed 20261105;
- one annotator (AA), with independent manual labels only.

The 12 held-out evaluation recordings were never loaded. This is an offline,
exploratory comparison, and the labels are not physiological ground truth.

## Methods (`scripts/okn_filters.py`)

| | Velocity estimate | Then |
|---|---|---|
| **SG** | `detect_okn.sg_velocity`: 5-sample, order-2 SG derivative on the raw angle, using real timestamps (unchanged) | detection, then the direction check |
| **BW** | Butterworth order 2 (`butter(..., output="sos")`), zero-phase `sosfiltfilt`, then `np.gradient` against the measured timestamps | the same |
| **BW+SG** | The same Butterworth low-pass, then the SG 5/2 derivative | the same |

**Shared rules:**
- **Sampling:** every Pilot 03 development run is 60.01 Hz, and no interval
  deviates from its run's median by more than 0.01 %. Each run's rate is
  measured from its timestamps. A run whose intervals deviate by more than
  1 % is refused rather than filtered as uniform.
- **Gaps:** nothing is filtered or differentiated across a blink, tracking
  loss or missing frame. The tool uses `detect_okn.continuous_runs` throughout.
  Runs shorter than 5 samples get no velocity, the same as SG.
- **Boundaries:** odd-reflection padding of up to 9 samples, shortened for
  short runs. A linear trend passes through the ends unchanged (tested). Edge
  effects: detections within 100 ms of a run boundary are 15 (SG), 14 (BW)
  and 15 (BW+SG).
- **Still stripes:** there is no expected direction, so every fast phase is
  kept, and each one counts as a false positive. No still-stripe recording has
  a `fast_phase` label.
- **Offline only:** forward–backward filtering uses future samples, so none of
  this works as is on the device in real time.

### Different frequency behaviour (`frequency_response.csv`)

Each estimator's gain relative to an ideal differentiator, at 60 Hz:

| Estimator | 5 Hz | 8 Hz | 10 Hz | 12 Hz | 15 Hz |
|---|---|---|---|---|---|
| SG 5/2 derivative | 0.85 | 0.65 | 0.50 | 0.34 | 0.13 |
| Central difference alone | 0.95 | 0.89 | 0.83 | 0.76 | 0.64 |
| BW 8 Hz + central difference | 0.84 | 0.44 | 0.22 | 0.09 | 0.02 |
| BW 15 Hz + central difference | 0.95 | 0.85 | 0.74 | 0.59 | 0.32 |
| BW 15 Hz + SG 5/2 | 0.85 | 0.63 | 0.45 | 0.26 | 0.06 |

The SG derivative is already a low-pass differentiator, with gain falling to
half by about 10 Hz. "Adding Butterworth" therefore means comparing low-pass
shapes, not adding smoothing to an unsmoothed signal. Specifically:
- BW at 8 Hz smooths **more** than SG above 5 Hz.
- BW+SG at 15 Hz is almost the same as SG below 10 Hz.

## Grid and selection (fixed before results)

**Grid:**
- **SG:** thresholds 10, 12, …, 40 deg/s.
- **BW and BW+SG:** cutoffs 5, 8, 12 and 15 Hz × the same thresholds.

That is 144 configurations, all in `filter_sweep.csv`.

**Within a method:**
- Pick the highest pooled F1.
- Ties within 0.01 go to fewer false positives per 10 s, then to the higher
  threshold, then to the higher cutoff (less smoothing).
- Overfitting check: choose the setting on one participant's trials, score it
  on the other's, both ways ("cross-participant F1").

**Across methods:** replace direction-aware SG only if the other method meets
all three:
1. pooled F1 is more than 0.01 higher;
2. it is at least as good for both participants;
3. its cross-participant F1 is higher.

**Scoring:** one-to-one matching within ±100 ms. TP, FP and FN are pooled
over recordings. Predictions near `uncertain` or `artifact` labels are left
unscored (there are none in this set).

## Results

**Reference check:** the reference reproduces exactly. SG at 22 deg/s with the
direction check gives TP 94, FP 25, FN 66, F1 0.674.

| Method | Chosen setting | TP | FP | FN | Precision | Recall | F1 | Cross-participant F1 | FP / 10 s | Mean signed timing (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| SG | 22 deg/s | 94 | 25 | 66 | 0.79 | 0.59 | 0.674 | 0.664 | 0.90 | −18 |
| BW | 8 Hz, 20 deg/s | 95 | 19 | 65 | 0.83 | 0.59 | 0.693 | **0.653** | 0.68 | −24 |
| BW+SG | 15 Hz, 22 deg/s | 95 | 21 | 65 | 0.82 | 0.59 | 0.688 | 0.667 | 0.75 | −19 |

Timing is the predicted onset minus the label. All methods fire about 20 ms
before the click.

**Best F1 anywhere in each method's grid** (`f1_vs_threshold.png`):

| Method | Best F1 | Setting |
|---|---|---|
| SG | 0.680 | 20 deg/s |
| BW | 0.693 | 8 Hz, 20 deg/s |
| BW+SG | 0.691 | 12 Hz, 18 deg/s |

Eight configurations from the two Butterworth methods are within 0.01 of the
best. Heavier smoothing simply moves the best threshold down. At 5 Hz the
best threshold is 14 deg/s; at 15 Hz it is 22.

**Settings chosen on one participant:**

| Method | Chosen on P01 | Chosen on P02 |
|---|---|---|
| SG | 22 deg/s | 20 deg/s |
| BW | 8 Hz, 20 deg/s | 8 Hz, 16 deg/s |
| BW+SG | 15 Hz, 22 deg/s | 12 Hz, 18 deg/s |

### By condition (P / R / F1 · FP per 10 s)

| | OKN | Dot + moving | Dot + still (FP only) |
|---|---|---|---|
| SG | 0.85 / 0.85 / 0.85 · 1.26 | 0.75 / 0.15 / 0.25 · 0.38 | 7 FP · 0.88 |
| BW | 0.88 / 0.86 / 0.87 · 1.01 | 0.75 / 0.15 / 0.25 · 0.38 | 4 FP · 0.50 |
| BW+SG | 0.88 / 0.86 / 0.87 · 1.01 | 0.75 / 0.15 / 0.25 · 0.38 | 6 FP · 0.75 |

**Dot + moving** is identical for all three methods: 9 of 60 labels found.
Their median peak speed is about 13 deg/s, 0.6× threshold, under every
estimator. These labels haven't been independently validated
(`../second_review.md`). Filtering can't separate them from noise either way.

### By participant (F1)

| | P01 | P02 |
|---|---|---|
| SG | 0.624 | 0.714 |
| BW | 0.633 | 0.740 |
| BW+SG | 0.634 | 0.732 |

The direction of the effect is the same for both participants, but P01's gain
is only about 0.01. Left and right stripe directions are also within 0.02 of each
other for every method.

### Short resets (`label_peaks.csv`)

At each `fast_phase` label, the peak |velocity| within ±100 ms:

| Method | Median OKN peak (deg/s) | Peak / threshold | Labels over threshold | SG-missed OKN labels recovered |
|---|---|---|---|---|
| SG 22 | 40.2 | 1.83 | 88 % | — (SG misses 15) |
| BW 8 Hz, 20 | 36.2 | 1.81 | 87 % | 2 of 15 |
| BW+SG 15 Hz, 22 | 39.2 | 1.78 | 87 % | 1 of 15 |

**Butterworth does not preserve short resets better.**
- BW at 8 Hz lowers OKN peaks by about 10 %. Its lower threshold makes up for
  that, so the share of labels over threshold doesn't change.
- Only 1–2 of the 15 OKN resets SG misses are recovered.
- The peak sits at the label's sample for every method (median shift 0 ms),
  so the filters don't move the peak in time.

**The gain is fewer false positives, not more detections.** Compared with SG:
- BW has 6 fewer FP: 3 on OKN trials and 3 on still stripes.
- BW+SG has 4 fewer FP.
- Both find 1 more TP.

## Interpretation

1. **BW vs. SG.** BW is +0.019 F1 in-sample, but worse across participants
   (0.653 vs 0.664). It **fails** the pre-set replacement rule.
2. **BW+SG.** It **passes** the rule, but only just. It is 0.014 better in
   pooled F1 (against SG's tie-break choice), ahead for both participants, and
   0.003 better across participants.
   - The difference is 1 TP and 4 FP across 28 recordings.
   - Against SG's best grid point (0.680), the gap is 0.008, inside the tie band.
   - Double filtering neither clearly helps nor hurts: at 15 Hz it barely
     changes SG's response below 10 Hz.
   - Lower cutoffs hurt badly at moderate and high thresholds. At 5 Hz and
     30 deg/s, BW+SG drops to F1 0.32.
3. **Short resets.** No method preserves them meaningfully better. SG
   attenuation is not fixed by swapping the low-pass, because any filter that
   removes the noise also removes energy from 1–2 frame resets.
4. **False positives.** BW at 8 Hz has the fewest, especially on still stripes
   (0.50 vs 0.88 per 10 s), but that is 3 events.
5. **Complexity.** Not justified yet. All three plateau at F1 0.68–0.69. The
   differences are a handful of events on two participants. Every Butterworth
   variant adds a parameter, and is non-causal as implemented.

## Recommendation

**Keep direction-aware SG at 22 deg/s as the frozen candidate for the held-out
evaluation.**

**On the BW+SG rule pass:** the pre-set rule technically favours BW+SG, but
the margin is about 4 events. I don't consider that evidence of improvement.
If you prefer to follow the rule to the letter, freeze BW+SG at 15 Hz,
22 deg/s instead. Decide this *before* the evaluation split is scored, and
record the decision.

## Reproduce

```bash
python3 analysis/pilot_03/compare_filters.py --labels-dir analysis/annotations_p03 --annotator AA
python -m unittest scripts/tests/test_okn_filters.py
```

**Inputs:** raw recordings in `trials/` and the labels in
`analysis/annotations_p03/` are both private and git-ignored.

**Outputs:**

| File | Contents |
|---|---|
| `filter_sweep.csv` | All 144 configurations |
| `filter_comparison.csv` | The selected settings, by group |
| `label_peaks.csv` | Velocity peaks at the labels |
| `frequency_response.csv` | Estimator gains by frequency |
| `filter_comparison.png` | Precision, recall and F1 for each method |
| `f1_vs_threshold.png` | F1 against threshold for every cutoff |
| `false_positives.png` | False positives per 10 s by condition |
| `waveform_examples.png` | P01 T012 clean OKN, P02 T034 short resets, P01 T020 noisy Dot + moving, P02 T051 still control |

## Limitations

- **Sample:**
  - two participants, known on both sides of the split;
  - 28 development recordings;
  - one annotator.
- **Tuning:** 144 configurations were compared on these labels, so small
  differences are expected from tuning alone.
- **Dot + moving labels:** not yet independently checked.
- **Signal:** ARKit gaze at about 60 Hz. One- or two-frame resets are
  undersampled, whatever the filter.
