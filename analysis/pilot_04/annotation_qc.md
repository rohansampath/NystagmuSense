# Pilot 04 annotation quality control

**When:** 2026-11-11, after all 60 recordings were annotated and **before any
detector was run on Pilot 04**.

**Who and how:** targeted human review by the original annotator (AA), in the
existing annotation tool, in independent mode. Detector suggestions were never
computed or shown, and no detector output for these trials was viewed.

**Why these five recordings:**
- Four still-stripe trials had fast-phase labels, unlike every other still trial.
- One Dot + moving trial had far more labels than any other.

## Changes

| Trial | Condition | Original fast labels | Revised fast labels | Uncertain | Artifact |
|---|---|---:|---:|---:|---:|
| P01 T074 | Dot + still | 9 | 1 | 0 | 0 |
| P01 T075 | Dot + still | 2 | 2 | 0 | 0 |
| P01 T076 | Dot + still | 3 | 0 | 0 | 0 |
| P01 T077 | Dot + still | 1 | 0 | 0 | 0 |
| P01 T069 | Dot + moving, Left | 18 | 0 | 0 | 0 |

**Unchanged:** the other 55 recordings. All 60 remain complete manual reviews
by AA.

**Status:** finalized before Pilot 04 was scored. No label or scoring rule was
changed after any detector output was seen.

**Checksums** (labels are private and git-ignored, kept in dated backups):

| | `events.csv` SHA-256 | `reviews.csv` SHA-256 | Backup |
|---|---|---|---|
| Pre-QC | `3e1cbdaa9538899076742ded6a8d635017e936f67643a3bfc250e40f5f20336d` | `a28c7bf28e8d702830d60a37880477aa733528b1114569332227ddd44cc09341` | `~/NystagmuSense-label-backups/p04_preQC_20261111T224721Z/` |
| Post-QC (scored) | `ecc7dee1630d3efee38d7d1038cc11cf722f66428b85ed08bc797f55c531bc6e` | `75b7b39f65774c658894cf30890aa878cb58a94ee9c3b56895e651de5c90d293` | `~/NystagmuSense-label-backups/p04_postQC_20261111T225118Z/` |

## Fast-phase labels after review

| | OKN | Dot + moving | Dot + still |
|---|---:|---:|---:|
| P01 | 43 | 56 | 3 |
| P02 | 58 | 48 | 0 |
| P03 | 48 | 35 | 0 |

## Scoring note

Still-stripe trials are stimulus-absent controls. The evaluator ignores
`fast_phase` labels on `FIXSTILL` trials, so every detection there counts as a
false positive. The 3 remaining still-stripe labels therefore don't affect any
score; they are kept as the annotator's record.

## Limitation

Labels are from one reviewer, with no inter-annotator reliability. They
describe movements visible in the ARKit signal, not physiological ground truth.
