# Pilot 03 experiment: direction-aware and piecewise-linear OKN detection

This compares established signal-processing ideas on the 28 Pilot 03
**development** recordings. It is not a new algorithm and not a validated
result.

**Not used:** the 12 held-out evaluation recordings were never loaded.

**Labels:** one annotator, provisional. A blinded second review is planned
(`second_review.md`) but not done.

**Reproduce:** `python3 analysis/pilot_03/compare_detectors.py --labels-dir <labels> --trials-dir <trials>`.
The outputs are in `comparison/`.

## The current detector (`detect_okn.py`, unchanged)

1. **Gaze input:** horizontal eye angle = −mean over both eyes of atan2(x, z) of ARKit's eye direction.
2. **Masking:** samples with tracking lost, a blink above 0.5, or a non-finite angle are masked and padded by 50 ms. Nothing is fitted across a gap.
3. **Velocity:** a 5-sample, order-2 Savitzky–Golay derivative, using real timestamps.
4. **Fast phases:** runs where |velocity| exceeds a threshold (default 40 deg/s). Same-direction runs within 50 ms are merged.
5. **Beats:** a line-fitted slow phase (≥ 0.15 s, R² ≥ 0.8) followed within 0.1 s by an opposite fast phase. Beats feed sliding 2 s windows that give OKN *intervals*.
6. **Output scored here:** the start time of each fast phase. All fast phases are scored, not just beats.

**Three distinct targets:**

| Target | What it means | How the detector handles it | Scored here? |
|---|---|---|---|
| Rapid eye movement | Any fast movement | Step 4 detects these | Yes, as the prediction |
| OKN reset | A fast phase *against* the stripes, after a drift *with* them | Nothing in the scored output checks this | This is what the labels mark |
| Sustained OKN | OKN going on over a window or a trial | Step 5 intervals | No |

So the scored output and the label target don't match: rapid movements are
scored against reset labels. The direction check below narrows that gap.

The step 5 intervals are almost never produced. Only 1–2 of 12 OKN trials get
any (`trial_level.csv`), so no trial-level summary is reported.

## Direction check (`okn_variants.direction_filter`)

**Sign measured without labels:**
- `eye_angle` is perfectly anti-correlated with ARKit `lookAtPoint.x` (r = −1.00 in every recording).
- The slow drift between resets runs opposite to the stimulus sign in all 20
  tracked OKN recordings: 16 from Pilot 03 and the 4 earlier DIR/DEV direction
  recordings.
- So the reset sign in `eye_angle` equals the sign of the change in
  `stim_displacement_pt`.

The absolute mapping to the subject's left and right is unresolved. One of the
documented conventions is mirrored. Only the relative sign is used.

**Rule:**
- **Moving stripes:** keep fast phases whose sign equals the expected reset sign.
- **Still stripes:** keep every fast phase, since there is no expected direction. Their false positives are still counted.

## Local piecewise-linear step (`okn_variants.py`)

**In one sentence:** a reset is a jump between two lines. One line fits the
150 ms before a candidate transition and one fits the 150 ms after, both
inside one valid run with real timestamps.

**Features:**
- **Step amplitude:** the jump between the two lines at the transition midpoint.
- **Fit improvement:** 1 − SSE(two lines + straight connector across the transition) ÷ SSE(one line over the same samples).
- **Side linearity:** each side's residual RMS must be ≤ 0.35 × |step|. A window that contains another reset is not mistaken for a slow phase.
- **Bookkeeping:** pre and post slopes and the transition duration are also recorded.

**Rejections:**
- A spike that returns to its level has a step near 0.
- Noise has a low improvement.
- Every side needs at least 3 samples, about 50 ms.

**Two uses:**
- **D, standalone:** every transition of 1 to about 6 samples (≤ 100 ms) at every sample is scored. Candidates must also average ≥ 10 deg/s across the transition. The best step within 150 ms is kept. No SG gate.
- **E, hybrid:** permissive SG candidates are kept only if the best step inside their span passes the gates and has the same sign. E can't recover an event SG never proposed.

**Tuning:**
- **Grids:** SG threshold 10–40; amplitude 0.3–2.5°; improvement 0.3–0.95. The step-gate grids were extended until no choice sat on an edge.
- **Rule:** the same as the benchmark. Highest F1; ties within 0.01 go to fewer FP per 10 s, then to the more conservative setting.
- **Overfitting check:** choose the setting on one participant's development trials, score on the other's, and pool both directions. This is the "cross-participant F1" column.

## Results (28 development recordings, ±100 ms one-to-one)

| | Method | Setting | TP | FP | FN | Precision | Recall | F1 | Cross-participant F1 | FP / 10 s | Timing error (ms) | ms / recording |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | SG, original | 40 deg/s | 53 | 21 | 107 | 0.72 | 0.33 | 0.45 | 0.45 | 0.75 | 14 | 14 |
| B | SG, tuned | 24 | 92 | 62 | 68 | 0.60 | 0.57 | 0.59 | 0.59 | 2.23 | 22 | 17 |
| **C** | **SG + direction** | **22** | 94 | 25 | 66 | 0.79 | 0.59 | **0.67** | **0.66** | 0.90 | 20 | 23 |
| D | Piecewise standalone + direction | 1.5°, 0.85 | 108 | 57 | 52 | 0.66 | **0.68** | 0.66 | 0.65 | 2.05 | 37 | 129 |
| E | SG + direction + linear | 20 deg/s, 1.2° | 96 | 14 | 64 | **0.87** | 0.60 | **0.71** | **0.67** | **0.50** | 21 | 13 |

**References:** the existing global segmentation (`hybrid_okn.py` at its
defaults) scores F1 0.46, or 0.52 with the direction check.

**Timing:** single-machine wall time, which includes SG for every method. The
small differences between A, B, C and E are noise.

**Timing error:** D's mean absolute timing error is about 15 ms larger than
SG's. Its event time is the transition start found by the fit, not a velocity
onset.

### Ablation (pooled development F1, with cross-participant F1 in brackets)

| Base | As is | + direction | + linear validation | + both |
|---|---|---|---|---|
| SG | 0.59 (0.59) | 0.67 (0.66) | 0.63 (0.62) | 0.71 (0.67) |
| Piecewise standalone | 0.58 (0.57) | 0.66 (0.65) | n/a | n/a |
| Global segmentation | 0.46 | 0.52 | n/a | n/a |

**What the ablation shows:**
- **The direction check is the main contribution.** It adds +0.06 to +0.09 F1 for every base method and holds up across participants.
- **Linear validation helps SG without direction** (+0.04). On top of the direction check it adds +0.04 within the development set but only +0.003 across participants. Its settings also moved between folds (22 deg/s / 1.2° vs 16 deg/s / 1.5°). Its extra gain is not robust on 28 recordings.

### By condition at each method's chosen setting

| | OKN P / R / F1 · FP/10 s | Dot + moving P / R / F1 · FP/10 s | Dot + still FP/10 s |
|---|---|---|---|
| A | 0.75 / 0.49 / 0.59 · 1.34 | 0.44 / 0.07 / 0.12 · 0.63 | 0.00 |
| B | 0.65 / 0.83 / 0.73 · 3.69 | 0.39 / 0.15 / 0.22 · 1.76 | 0.50 |
| C | 0.85 / 0.85 / 0.85 · 1.26 | 0.75 / 0.15 / 0.25 · 0.38 | 0.88 |
| D | 0.75 / 0.86 / 0.80 · 2.43 | 0.81 / 0.37 / 0.51 · 0.63 | **2.89** |
| E | 0.92 / 0.88 / **0.90** · 0.67 | 1.00 / 0.13 / 0.24 · 0.00 | 0.75 |

Dot + still has no resets, so only false positives are reported. Neither the
direction check nor linear validation can remove a still-stripe saccade.

### By participant and stripe direction (F1)

| | P01 | P02 | Left | Right |
|---|---|---|---|---|
| A | 0.39 | 0.50 | 0.40 | 0.51 |
| B | 0.59 | 0.58 | 0.60 | 0.58 |
| C | 0.62 | 0.71 | 0.69 | 0.70 |
| D | 0.59 | 0.73 | 0.74 | 0.69 |
| E | 0.66 | 0.75 | 0.73 | 0.73 |

**By participant:**
- **P01 OKN** is nearly solved by E (F1 0.99) and C (0.90).
- **P01's overall** is pulled down by Dot + moving, with recall of 0.05–0.26.
- **P02** has noisier OKN but more detectable Dot + moving resets.

**Direction:** left and right are balanced.

### Does standalone segmentation find events SG misses? (`recovered.csv`)

Yes, mainly short OKN resets and some Dot + moving steps.

| Labels with no SG candidate | OKN: missed / found by D | Dot + moving: missed / found by D |
|---|---|---|
| at 24 deg/s | 17 / 9 | 51 / 15 |
| at 20 deg/s (E's candidate gate) | 8 / 3 | 49 / 13 |

**The cost:** D can't tell a still-stripe saccade from a reset, so it has
2.9 FP per 10 s on Dot + still. It also runs about 6× slower, with pure-Python
loops.

### Does the hybrid reduce false positives?

**Yes.** E has 14 FP, against 62 for B and 25 for C.

| FP per 10 s | B | E |
|---|---|---|
| OKN | 3.69 | 0.67 |
| Dot + moving | 1.76 | 0.00 |

Most of the reduction comes from the direction check (C, 25 FP). Compared
with C, E has 11 fewer false positives and 2 more true positives, because it
uses a lower SG gate (20 deg/s, against 22).

## Examples (`comparison/examples.png`, development only)

1. **Clean OKN, P02 T039.** D and E both find all 11 resets. E rejects every
   wrong-direction SG candidate (red ×).
2. **Short resets, P02 T034.** Several labelled resets are 2–3 samples long:
   - Their SG peak stays under 20 deg/s, so E never sees them.
   - D finds one more than E and adds one false positive.
3. **Noisy Dot + moving, P01 T020.** The trace stays within ±1°, and the labels
   sit on deflections the size of the surrounding fluctuations:
   - SG proposes almost nothing, so E finds 0 of 10.
   - D finds 3 of 10.
   - Whether the other 7 are resets is a label question (see below).
4. **Dot + still, P01 T029.** E and D each fire once or twice on isolated
   saccades. Direction can't help with
   still stripes.

## Dot + moving label uncertainty

This remains the main limitation.
- **Step sizes:** the median two-line step at a Dot + moving label is 1.3°,
  against 3.2° at OKN labels. A third are under 1°.
- **Recall:** every method's recall there is 0.13–0.37.

Until a second annotator agrees on them, Dot + moving event metrics are
provisional. Low recall there may be label noise as much as detector failure.

## Recommendation for the next experiment

**Freeze C: SG at 22 deg/s plus the direction check.**
- It is one extra rule on top of the existing detector.
- It reaches 0.66 F1 across participants, almost E's 0.67.
- Its settings barely moved between folds (22 vs 20 deg/s).

**Keep E as the secondary candidate.** It has better precision (0.87) and the
fewest false positives. Its extra gate isn't yet shown to generalise, so
re-check it after the second review.

**Don't adopt D now.** It is the only method that recovers sub-threshold
resets, but it fires on still-stripe saccades and is slower.

## Before the held-out evaluation

1. **Blinded second review.** Six recordings (`second_review.md`). Decide how
   Dot + moving labels are treated *before* scoring the evaluation split.
2. **Freeze one configuration.** The recommendation is C at 22 deg/s. Record
   the commit and the config.
3. **Score the 12 evaluation recordings once**, with
   `evaluate_okn.py --manifest ... --split evaluation --allow-evaluation`.
   Candidate C is now exposed as `--detector sg-direction` (22 deg/s by
   default); pass `--annotator AA --artifacts exclude` and record the frozen
   commit/configuration before running it. The baseline remains unchanged.
4. **Report with the stated limitations:**
   - two known participants;
   - one session;
   - ARKit-visible events, not physiological ground truth.
