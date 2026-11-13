# Pilot 04 external validation: run record (written before scoring)

**Pilot 04 external validation — frozen Pilot 03 SG detector.**

## Detector

The detector is exactly the one in `analysis/pilot_03/frozen_detector.md`,
frozen 2026-11-08 before any Pilot 03 held-out scoring:
- SG derivative, window 5, polynomial order 2, real timestamps;
- fast phase where |velocity| > 22 deg/s;
- same-direction runs merged within 50 ms;
- direction check: keep resets whose sign equals the stimulus sign, all fast phases on still stripes;
- blinks over 0.5, tracking loss and frame gaps masked, ±50 ms padding;
- event time = fast-phase start;
- no beat or slow-phase requirement.

**Parameter changes:** none.

## Code

**Run commit:** branch `analysis/pilot-04-validation` on `main` at `6e68303`.

| File | SHA-256 | Same as freeze (`63298de`)? |
|---|---|---|
| `scripts/detect_okn.py` | `1a858f0b6b804857359a92afadd06dac5f5956047bbb8457b857427454866a1f` | yes, identical |
| `scripts/okn_variants.py` | `152c2999a62a774c0b006df6b769541a4dac43de73beb9f39e4fa4360139a683` | yes, identical |
| `scripts/evaluate_okn.py` | `c9b3fc6509edc446a8268fe72d12f092a6db132ed2633ef241104a64838af1b3` | no; see below |

**The `evaluate_okn.py` difference:** one later commit, `f1278e9` (Rohan,
"Protect Pilot 04 holdout"), extends the no-`--manifest` safety check to Pilot
04 held-out reviews. `detector_predictions`, `score_manifest_trial`,
`match_events` and every metric are unchanged. That branch is not used when
`--manifest` is given.

## Data

| Input | Value |
|---|---|
| Manifest | `analysis/pilot_04/manifest.csv`, SHA-256 `d599b699f941de65b5293074175e0c5dadb17d363aaceb710da2f124958a881b`; 60 primary recordings, role `external_validation`, split `evaluation` |
| Protocol | 4 recordings of each of the five conditions per participant; a deviation from the planned 4/4/3/3/6 (`docs/PILOT_04.md`) |
| Labels | one annotator (AA), 60 of 60 complete manual reviews, no suggestions; targeted QC of 5 recordings before scoring (`../annotation_qc.md`) |
| Labels scored (post-QC) | `events.csv` `ecc7dee1630d3efee38d7d1038cc11cf722f66428b85ed08bc797f55c531bc6e`; `reviews.csv` `75b7b39f65774c658894cf30890aa878cb58a94ee9c3b56895e651de5c90d293` |
| Labels before QC | `events.csv` `3e1cbdaa9538899076742ded6a8d635017e936f67643a3bfc250e40f5f20336d`; `reviews.csv` `a28c7bf28e8d702830d60a37880477aa733528b1114569332227ddd44cc09341` |

## Scoring rules

- One-to-one matching within ±100 ms.
- `--artifacts exclude`; no `uncertain` or `artifact` labels are present.
- Pooled TP/FP/FN.
- **Still-stripe trials:** controls. The 3 `fast_phase` labels on P01 T074/T075
  are ignored by `score_manifest_trial`, so every detection on a `FIXSTILL`
  trial is a false positive. Checked synthetically before the run: predictions
  placed exactly on those 3 labels score TP 0, FP 3.

## Command (run once)

```bash
python3 scripts/evaluate_okn.py --manifest analysis/pilot_04/manifest.csv --split evaluation --allow-evaluation \
    --labels-dir analysis/annotations_p04 --trials-dir trials --annotator AA --artifacts exclude \
    --detector sg-direction --output-csv analysis/pilot_04/validation/validation_results.csv \
    | tee analysis/pilot_04/validation/validation_report.txt
```

## After the run

- Outputs in this folder are not edited.
- Labels and scoring rules don't change.
- Any optimization uses `../optimization/`, and its results are not independent validation.
