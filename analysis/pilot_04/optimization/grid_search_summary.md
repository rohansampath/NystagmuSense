# Pilot 04 SG hyperparameter study (exploratory)

**Not independent validation.** Pilot 04 was first used, untouched, for the
external validation in `../validation/`: commits `c4389e3` (outputs) and
`ef50b68` (summary), F1 0.54. Afterwards it was reused here as development
data, with role `p04_development_after_validation` in `development_manifest.csv`.
The original manifest keeps role `external_validation`.

Every number below is development performance on data that also chose the
setting. A new detector would need fresh, unseen recordings before any claim
of improvement.

## Setup (fixed before results; script and rules committed in `82002a8`)

**Grid:** the frozen SG + direction detector with only three settings varied.

| Setting | Values |
|---|---|
| Threshold | 18–28 deg/s, in steps of 2 |
| SG window | 5 or 7 samples |
| SG order | 2 or 3 |

That gives 24 valid configurations. The direction check is always on, and
every other parameter stays at its default. The derivative is correct for
every window and order (unit test on a quadratic).

**Reference:** 22 deg/s, window 5, order 2. It reproduces the validation
exactly: TP 135, FP 74, FN 153, F1 0.543.

**Selection rule:**
1. **Eligible:** still-stripe FP per 10 s no worse than the reference's; OKN
   recall within 0.02 of it; worst-participant F1 within 0.01 of it.
2. **Choice:** the eligible config with the highest pooled F1. Ties within
   0.01 go to fewer still-stripe FP, then the simpler filter, then the
   threshold closest to 22.
3. **Default:** keep the reference unless the winner is more than 0.01 F1 better.

**Validation:** leave-one-participant-out, 3 folds.

## All 24 configurations (`grid_search.csv`, `parameter_comparison.png`)

| | Threshold | Precision | Recall | F1 | FP / 10 s | OKN recall | Still FP / 10 s |
|---|---|---|---|---|---|---|---|
| **Window 5, order 2 (reference family)** | 18 | 0.57 | 0.54 | 0.555 | 1.98 | 0.78 | 4.44 |
| | 20 | 0.62 | 0.50 | 0.553 | 1.49 | 0.77 | 3.60 |
| | **22 (reference)** | 0.65 | 0.47 | 0.543 | 1.24 | 0.75 | 2.93 |
| | 24 | 0.67 | 0.44 | 0.531 | 1.02 | 0.72 | 2.51 |
| | 26 | 0.71 | 0.41 | 0.515 | 0.82 | 0.68 | 2.09 |
| | 28 | 0.73 | 0.37 | 0.492 | 0.67 | 0.62 | 1.76 |
| **Window 7, order 2** | **18 (chosen)** | 0.70 | 0.47 | **0.558** | 0.97 | 0.75 | 2.35 |
| | 20 | 0.71 | 0.41 | 0.515 | 0.82 | 0.68 | 2.18 |
| | 22 | 0.75 | 0.38 | 0.502 | 0.62 | 0.65 | 1.76 |
| | 24–28 | 0.75–0.81 | 0.27–0.34 | 0.41–0.47 | 0.32–0.54 | 0.49–0.57 | 1.09–1.59 |
| **Window 5, order 3** | 18–28 | 0.38–0.52 | 0.53–0.80 | 0.51–0.53 | 2.3–6.2 | 0.77–0.91 | **5.1–11.6** |
| **Window 7, order 3** | 18–28 | 0.49–0.65 | 0.47–0.66 | 0.54–0.56 | 1.2–3.3 | 0.75–0.86 | 3.2–6.9 |

**What the grid shows:**
- **Order 3 smooths less.** It raises recall, especially in Dot + moving
  trials (F1 up to 0.56), but it fires heavily on still-stripe controls. It
  fails the still-stripe constraint at every threshold.
- **Window 7 at 18 deg/s ≈ window 5 at about 22 deg/s.** The heavier smoothing
  is offset by a lower threshold, the same trade-off seen with Butterworth in
  Pilot 03.
- **The best F1 in the whole grid is 0.561** (18 / 7 / 3), but it has 6.9
  still-stripe FP per 10 s.

## Chosen on all 60 (`best_configuration.json`)

| | Precision | Recall | F1 | TP / FP / FN | FP / 10 s | OKN recall | Still FP / 10 s | F1 P01 / P02 / P03 | Timing |
|---|---|---|---|---|---|---|---|---|---|
| Frozen reference (22, 5, 2) | 0.65 | 0.47 | 0.543 | 135 / 74 / 153 | 1.24 | 0.75 | 2.93 | 0.44 / 0.49 / 0.72 | 17 ms |
| Development choice (18, 7, 2) | 0.70 | 0.47 | 0.558 | 134 / 58 / 154 | 0.97 | 0.75 | 2.35 | 0.46 / 0.49 / 0.73 | 23 ms |

## Grouped cross-validation (`cross_validation.csv`)

| Held out | Chosen on the other two | Reference F1 | Chosen F1 |
|---|---|---|---|
| P01 | reference (no gain over 0.01) | 0.441 | 0.441 |
| P02 | 18, 7, 2 | 0.487 | 0.486 |
| P03 (the only new person) | 18, 7, 2 | 0.717 | 0.730 |
| **Pooled** | | **0.543** | **0.548** (4 fewer FP, same TP) |

## Conclusion

The gain is marginal and inconsistent:
- +0.015 F1 in-sample, +0.005 across held-out participants;
- no change for P01 and P02, +0.013 for P03;
- timing is 6 ms later.

That is within what tuning on 60 recordings from three people produces by
chance, and it costs a different filter setting.

The chosen threshold (18 deg/s) is also the lowest value in the grid. A wider
grid might pick differently, which is another reason not to read much into
it.

**Recommendation:** keep the frozen detector (22 deg/s, window 5, order 2).
If the development setting (18 deg/s, window 7, order 2) is pursued, freeze it
first and test it on fresh recordings.

The real limits are elsewhere:
- **Dot + moving F1** stays at about 0.26 or below for every setting that keeps
  still false positives in check.
- **One participant (P01) produces many still-stripe false positives.**

Neither is fixed by SG settings.

## Limitations

- **Participants:** three folds of one participant each, so the
  cross-validation estimate is very noisy.
- **Overlap with Pilot 03:** P01 and P02 are also Pilot 03 participants, the
  data the reference was developed on. Only the P03 fold is an unseen person.
- **Labels:** from one annotator, not physiological ground truth.
- **Protocol deviation:** 4 trials of every condition per participant, so only
  12 still-stripe controls.
