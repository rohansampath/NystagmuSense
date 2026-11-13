# Pilot 04 external validation — frozen Pilot 03 SG detector

**This is the primary Pilot 04 result.** The detector frozen on Pilot 03 (SG +
direction, 22 deg/s; `../../pilot_03/frozen_detector.md`) was run **once** on
all 60 Pilot 04 recordings, unchanged, before any Pilot 04 tuning.

**Run:** commit `4f01f48`, recorded in `run_record.md` before scoring.

**Outputs** (`validation_results.csv`, `validation_report.txt`) are not to be
edited. SHA-256:

| File | SHA-256 |
|---|---|
| `validation_results.csv` | `cfdb5fbd1638d86173cc9678b82e19d65672a6750e5c40745b5560c5377eb0f1` |
| `validation_report.txt` | `83e4794723b4d5f8b508be96b4e344b3a2c87d824e151b87bc7346482f7066f6` |

**Labels:** one annotator (AA), with targeted human QC before scoring
(`../annotation_qc.md`).

| Label set | `events.csv` | `reviews.csv` |
|---|---|---|
| Scored (post-QC) | `ecc7dee1…31bc6e` | `75b7b39f…d293` |
| Pre-QC | `3e1cbdaa…20336d` | `a28c7bf2…9341` |

## Overall (60 recordings, pooled, ±100 ms one-to-one)

| | TP | FP | FN | Precision | Recall | F1 (bootstrap 95 %) | FP / 10 s | Timing error |
|---|---|---|---|---|---|---|---|---|
| **All 60** | 135 | 74 | 153 | **0.65** | **0.47** | **0.54** (0.43–0.65) | 1.24 | 17 ms |
| Moving stripes only (48) | 135 | 39 | 153 | 0.78 | 0.47 | 0.58 (0.48–0.69) | 0.82 | 17 ms |

## By participant

| | Status | Precision | Recall | F1 (95 %) | FP / 10 s |
|---|---|---|---|---|---|
| P01 | returning | 0.47 | 0.41 | 0.44 (0.27–0.60) | 2.31 |
| P02 | returning | 0.80 | 0.35 | 0.49 (0.27–0.68) | 0.45 |
| **P03** | **new** | 0.75 | 0.69 | **0.72** (0.56–0.84) | 0.96 |
| Returning (P01 + P02) | | 0.59 | 0.38 | 0.46 | 1.38 |

## By condition and direction

| | Recordings | TP / FP / FN | Precision | Recall | F1 | FP / 10 s |
|---|---|---|---|---|---|---|
| OKN | 24 | 112 / 26 / 37 | 0.81 | 0.75 | **0.78** | 1.09 |
| Dot + moving | 24 | 23 / 13 / 116 | 0.64 | 0.17 | 0.26 | 0.55 |
| Dot + still (controls) | 12 | 0 / 35 / – | – | – | – | **2.93** |
| Left (moving) | 24 | 63 / 26 / 75 | 0.71 | 0.46 | 0.56 | 1.09 |
| Right (moving) | 24 | 72 / 13 / 78 | 0.85 | 0.48 | 0.61 | 0.55 |

**OKN by participant (F1):**

| P01 | P02 | P03 |
|---|---|---|
| 0.79 | 0.71 (recall 0.59) | 0.84 (recall 0.94) |

**Still-stripe false positives per trial:**

| Participant | Trials | False positives |
|---|---|---|
| P01 | T074, T075, T076, T077 | 4, 13, 9, 4 (30 in 40 s) |
| P02 | T094–T097 | 1, 1, 1, 0 |
| P03 | T114–T117 | 0, 0, 0, 2 |

**The 3 P01 still-stripe `fast_phase` labels** (T074, T075) are ignored by the
documented control rule, as stated before the run. If they had counted as
references, at most 3 of those 30 false positives could have matched.

## Compared with Pilot 03

| | Precision | Recall | F1 | OKN F1 | Dot + moving F1 | Still FP / 10 s |
|---|---|---|---|---|---|---|
| Pilot 03 development (28, used for selection) | 0.79 | 0.59 | 0.67 | 0.85 | 0.25 | 0.88 |
| Pilot 03 held-out (12) | 0.71 | 0.46 | 0.56 | 0.82 | 0.28 | 1.01 |
| **Pilot 04 external (60)** | 0.65 | 0.47 | **0.54** | **0.78** | 0.26 | **2.93** |

## Answers

1. **Similar to Pilot 03 held-out, below development.** Overall F1 is 0.54,
   against 0.56 held-out and 0.67 development. The OKN condition holds up at
   F1 0.78, against 0.82 and 0.85. The development figure was optimistic, as
   expected.
2. **The new participant generalises.** P03 has the best results (F1 0.72;
   OKN recall 0.94), so the detector isn't tied to the two people it was
   tuned on.
   - The returning participants do worse (0.44 and 0.49), for different reasons.
   - **P01:** many false detections on still stripes.
   - **P02:** low recall, missing 24 of 58 OKN resets.
3. **Dot + moving is hardest.** Recall is 0.17 (23 of 139 labels), the same
   picture as Pilot 03 (0.15–0.19). Most of the misses are there: 116 of 153.
4. **Still-stripe false positives are acceptable for P02 and P03** (0.5–0.75
   per 10 s), **but not for P01** (7.5 per 10 s). P01's original labels marked
   15 movements on these trials, so P01 made many saccades while fixating. A
   direction-free still trial can't screen these out. Pooled 2.93 per 10 s is
   driven by one person.
5. **Most failures are misses** (153 FN vs 74 FP):
   - 116 of the misses are in Dot + moving trials;
   - 35 of the false positives are on still stripes, 30 of them P01's.
6. **For exploratory contrast work:** yes for regular OKN, which is what a
   contrast series would use. Reset detection there is F1 0.78 and stable
   across both pilots and a new person. Use it for measuring slow-phase response
   between detected resets. Don't use it as a trial-level OKN-present classifier
   in fixation conditions.
   - Per-participant fixation stability, as P01 shows, should be checked before
     each session.

## Limitations

- **Participants:** three, two of whom (P01, P02) also took part in Pilot 03,
  the data the detector was developed on. Only P03 is a genuinely new person.
- **Labels:** one annotator, with no inter-rater reliability. Labels describe
  ARKit-visible movement (about 60 Hz, uncalibrated), not physiological ground
  truth. Five recordings were re-reviewed before scoring, disclosed above.
- **Protocol deviation:** 4 trials of every condition per participant, not the
  planned 4/4/3/3/6. That gives fewer still-stripe controls (12 rather than 18)
  and more weight on Dot + moving.
- **Event F1 isn't trial-level sensitivity.** Nothing here is a clinical
  validation.
