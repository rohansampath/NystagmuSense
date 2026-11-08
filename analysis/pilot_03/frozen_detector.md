# Pilot 03 frozen detector

**Frozen:** 2026-11-08, before any held-out scoring.

**Basis:** chosen on the 28 development recordings only. See:
- `benchmark_summary.md`
- `comparison_report.md`
- `filter_comparison/README.md`

**Rule:** nothing below may change after the evaluation split has been scored.

## Detector: SG + stimulus direction, 22 deg/s

| Setting | Value | Where |
|---|---|---|
| Gaze signal | horizontal eye angle = −mean over both eyes of degrees(atan2(dir_x, dir_z)) | `detect_okn.eye_angle` |
| Invalid samples | tracked ≠ 1, non-finite or zero-length eye direction, blink > 0.5 (either eye); each padded ±50 ms | `detect_okn.valid_mask` |
| Gaps | split at invalid samples and at frame gaps > 2.5 × median interval; nothing is fitted, filtered or detected across a split | `detect_okn.continuous_runs` |
| Velocity | Savitzky–Golay first derivative, window 5 samples, polynomial order 2, real timestamps (SciPy `savgol_filter` on uniform runs, local polynomial fit on jittered runs); runs < 5 samples get no velocity | `detect_okn.sg_velocity` |
| Fast phase | contiguous \|velocity\| > **22 deg/s**, split by sign; same-direction runs < 50 ms apart are merged | `detect_okn.detect_fast_phases` |
| Direction check | moving stripes: keep fast phases whose sign equals the stimulus sign (`RESET_SIGN_PER_STIMULUS = 1`; sign of d `stim_displacement_pt`/dt, measured label-free); still stripes (direction 0): keep all; missing or non-finite displacement, or a reversing stimulus: refuse | `okn_variants.direction_filter`, `evaluate_okn.detector_predictions` |
| Event time | start time (first above-threshold sample) of each kept fast phase | `evaluate_okn.detector_predictions` |
| Other constraints | none: no minimum separation beyond the 50 ms merge, no slow-phase or beat requirement | — |

**Slow-phase and beat settings** are computed by `detect_okn.analyse` but don't
affect the scored predictions:
- `min_slow_s` 0.15;
- `min_slow_velocity` 1;
- `min_slow_r2` 0.8;
- `min_slow_direction_agreement` 0.8;
- `beat_max_gap_s` 0.1;
- windows 2.0 s / 0.5 s, with `min_beats` 2 and `min_agreement` 0.75.

## Scoring protocol

| Rule | Value |
|---|---|
| Recordings | primary trials of the requested split in `manifest.csv` (seed 20261105, 28 development / 12 evaluation); a missing recording or review is an error |
| Labels | one annotator (AA), complete manual reviews only (suggestions never shown) |
| Matching | one-to-one, ±100 ms, earliest unmatched prediction per label in time order |
| `uncertain` / `artifact` | `--artifacts exclude`: predictions within 100 ms are unscored, and these labels are never misses |
| Still stripes | controls: `fast_phase` labels on `FIXSTILL` are ignored, so every detection there is a false positive; recall and F1 not reported |
| Metrics | TP, FP and FN pooled over recordings; precision, recall, F1 = 2TP/(2TP+FP+FN); FP per 10 s of recording; mean absolute timing error of matched pairs |

## Code and inputs

**Code:**
- Commit `63298de` (PR #17 head, `fix/code-health-evaluation`). The run
  branch's `scripts/` is identical to it.
- Python 3.12.4, NumPy 1.26.4, SciPy 1.13.1.

**SHA-256 checksums:**

| File | SHA-256 |
|---|---|
| `scripts/detect_okn.py` | `1a858f0b6b804857359a92afadd06dac5f5956047bbb8457b857427454866a1f` |
| `scripts/evaluate_okn.py` | `72d0203aa08d883eb57ca8f4fe61a290dcaea931d5d6f2674a08907f145bf149` |
| `scripts/okn_variants.py` | `152c2999a62a774c0b006df6b769541a4dac43de73beb9f39e4fa4360139a683` |
| `scripts/annotate_okn.py` | `65ebc91c968f9e5364ebb63bf2e7a60e0c86c519129cb98683ec9df5f60cc07f` |
| `analysis/pilot_03/manifest.csv` | `81672f0355fb44e8a1b4e77c925fa311ad8ad7f24066222cfc4eb949453f73ad` |
| labels `events.csv` (private) | `e0383a223663bc89a0c2763f3b5be7b656ad56ff0a6fb6aaa20b35ceab14fb95` |
| labels `reviews.csv` (private) | `104344d9c4d7389cc561379fb40f371f9089c5b47fa7ce59e853720d1338a1ae` |

**Development check with this exact command and code:** TP 94, FP 25, FN 66,
precision 0.79, recall 0.59, F1 0.67, 0.90 FP per 10 s.

## One-time held-out command

```bash
python3 scripts/evaluate_okn.py --manifest analysis/pilot_03/manifest.csv --split evaluation --allow-evaluation \
    --labels-dir analysis/annotations_p03 --trials-dir trials --annotator AA --artifacts exclude \
    --detector sg-direction --output-csv analysis/pilot_03/heldout/heldout_trials.csv \
    | tee analysis/pilot_03/heldout/heldout_report.txt
```
