# Reset (fast-phase) annotations

These are written by `scripts/annotate_okn.py` and read by `scripts/evaluate_okn.py`.
They are **human-reviewed labels of events visible in the ARKit signal**, not
physiological ground truth from an independent eye tracker. The raw recordings
stay in the private, git-ignored `trials/` folders.

| File | Columns |
|---|---|
| `events.csv` | `trial_id` (recording stem), `event_time_s` (`t_s` of the nearest sample), `label` (`fast_phase` / `uncertain` / `artifact`), `annotator_id`, `annotation_method` (`manual` / `assisted`) |
| `reviews.csv` | one row per trial and annotator. `status` is `complete` or `in_progress`, plus event counts, the time of the last save (UTC) and the source CSV |

- A trial is scored **only** if its review row says `complete`. A complete row
  with 0 events is a reviewed trial that has no resets; a missing row means
  nobody has annotated the trial yet.
- `manual` means the labels were made with suggestions hidden (independent).
  `assisted` means suggestions were shown at least once for that trial and
  annotator.

## Pilot 01 labelling plan

Label the **evaluation** trials first, with suggestions hidden (the default).
Don't look at the detector plots for them again beforehand. The Pilot 01
figures already showed detector fast phases on every Batch 2 trace, so these
labels are only *partly* independent. That should be stated whenever results
are reported.

| Use | Trials (Pilot 01 ID → `trial_id`) | Command flag |
|---|---|---|
| **Evaluation**, independent | A3 `NS_20261104-001938_2F10DCDB_okn`, A4 `NS_20261104-002030_1D472ADC_okn`, A5 `NS_20261104-002134_F5DFEFF3_okn`, B2 `NS_20261104-001755_51DB182F_fixmove`, B3 `NS_20261104-001957_DC24C342_fixmove`, C2 `NS_20261104-001822_12E51902_fixstill`, C3 `NS_20261104-001918_C78484EE_fixstill` | *(none)* |
| **Development**, assisted | A1 `NS_20261104-001649_3B564048_okn`, A2 `NS_20261104-001846_1935C8DE_okn`, B1 `NS_20261104-001709_9A6B885A_fixmove`, C1 `NS_20261104-001727_3611D4CA_fixstill` | `--assisted` |
| **Artifact check** | V5 blink trial `NS_20261104-001457_0DB297A4_fixstill`: mark blink artefacts as `artifact` (key 3) | `--assisted` |
