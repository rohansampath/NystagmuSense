# Pilot 03 dataset and detector benchmark

Pilot 03 is a high-contrast OKN validation set: participants P01 and P02, and
three conditions:
- OKN (watch the moving stripes);
- fixation dot + moving stripes;
- fixation dot + still stripes.

The protocol is in `docs/PILOT_03.md`. Raw recordings stay in the git-ignored
`trials/` folder.

Labels are human-reviewed events **visible in the ARKit signal**, not
physiological ground truth.

## Files

| File | What it is |
|---|---|
| `manifest.csv` | Every P03 recording, with its technical status, eligibility and development/evaluation split. **Frozen**: `build_manifest.py --check` must reproduce it exactly. |
| `build_manifest.py` | Builds the manifest from file names, sidecars and CSV timing only. It never reads labels or detector output. |
| `check_labels.py` | Writes `label_flags.csv`, the labels to look at again. It uses the raw signal and never edits labels. |
| `sweep/` | Output of `scripts/sweep_okn_threshold.py`, development trials only. |

## Eligibility (fixed before any detector results)

- **Technical failure → excluded.** Any of the following:
  - metadata that disagrees with the file name;
  - not the P03 stimulus: background not fixed white, or stripe speed wrong for the condition;
  - under 570 samples;
  - under 90 % of samples face-tracked;
  - timestamps that don't increase;
  - any issue logged in the sidecar.

  None of the 48 P03 recordings failed.
- **Notes, not exclusions:**
  - Distance drift outside 25–30 cm. Participants leaned in to a median of 22–25 cm in 12 trials.
  - The bypassed distance check in P01 T017. Its measured distance stayed at 26.9–28.7 cm.

  Irregular or weak eye traces are never a reason to exclude.
- **Primary dataset (40).** For each participant, condition and direction, the first technically valid recordings in trial order, up to:

  | Condition | Per direction |
  |---|---|
  | OKN | 4 |
  | Dot + moving | 3 |
  | Dot + still | 6 (no direction) |
- **Extra (5).** Later recordings beyond those counts, kept for exploratory use:
  - P01 T022 and T026;
  - P02 T046, T048 and T055.
- **Excluded (3).** P01 T008–T010, the first three OKN · Left trials, which the experimenter moved to `trials/_excluded_P03/`.

## Split (seed 20261105)

Within each primary cell, a seeded random sample goes to evaluation:
- 1 per OKN direction;
- 1 per Dot + moving direction;
- 2 still-stripe trials.

That is 6 per participant, **12 evaluation and 28 development** in total. Whole
recordings only.

Both participants appear on both sides, so results don't generalise to unseen
people. They are reported per participant.

## What is labelled

The primary target is the **OKN fast phase**: a reset that moves the eye
*against* the stripe motion, coming after a slow drift *with* it. It's the same
definition in every condition. In the plotted convention (+ = subject's left):

| Stripes | Slow phase | Reset (`fast_phase`) |
|---|---|---|
| Right → | gradual drift down | sharp jump **up** |
| ← Left | gradual drift up | sharp jump **down** |
| Still | none | none expected |

**Still stripes:**
- A still-stripe trial may still contain OKN-like events; don't assume zero.
- Don't label ordinary isolated saccades as fast phases.
- Mark candidates you can't decide on as `uncertain`.
- Mark blink or tracking glitches as `artifact`.
- A reviewed trial with zero fast phases is valid.

**Every condition:**
- A sharp jump in the *wrong* direction is not an OKN reset. Leave it unlabelled, or use `uncertain`.

## Scoring policy (`scripts/evaluate_okn.py`)

- **Trials scored:** only completely reviewed trials, and with `--manifest`, only that split's primary trials.
- **References and predictions:** references are `fast_phase` labels; predictions are the starts of the detector's fast phases.
- **Matching:** one-to-one, within ±100 ms.
- **`uncertain` labels:** never counted as a miss; predictions within 100 ms of one are left unscored.
- **`artifact` labels:** with `--artifacts exclude` (used for P03), predictions within 100 ms are left unscored. The default, `false-positive`, keeps the Pilot 01 behaviour.
- **Trials with no resets:** every prediction is a false positive; recall is n/a. False positives are also reported per 10 s.
- **Metrics:** precision, recall and F1 = 2TP / (2TP + FP + FN), pooled over trials, and broken down by participant, condition, and participant × condition.

## Threshold choice (fixed before the sweep)

1. Sweep thresholds 10, 12, …, 40 deg/s on **development trials only**. All other SG parameters stay at their defaults.
2. Pick the highest pooled development F1.
3. Treat thresholds within 0.01 F1 of it as tied, and among those pick the one with the fewest false positives per 10 s, then the higher threshold.
4. Report 40 deg/s as the baseline.

The evaluation split is scored **once**, after the detector configuration is
frozen, and needs `--allow-evaluation`.

## Commands

The recordings live in the main checkout's `trials/`. The labels are in the
annotation worktree.

```bash
T=~/CS_Projects/NystagmuSense/trials
L=~/CS_Projects/NystagmuSense-annot/analysis/annotations_p03

python3 analysis/pilot_03/build_manifest.py --trials-dir $T --check           # manifest unchanged?
python3 analysis/pilot_03/check_labels.py --labels-dir $L --trials-dir $T     # labels to re-check
python3 scripts/evaluate_okn.py --manifest analysis/pilot_03/manifest.csv --split development \
    --labels-dir $L --trials-dir $T --artifacts exclude --output-csv analysis/pilot_03/sweep/dev_baseline_trials.csv
python3 scripts/sweep_okn_threshold.py --manifest analysis/pilot_03/manifest.csv \
    --labels-dir $L --trials-dir $T --output-dir analysis/pilot_03/sweep
```
