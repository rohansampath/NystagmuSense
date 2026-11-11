# Pilot 04 (P04): three-participant external validation set

**Purpose:** 60 new recordings to test the **frozen Pilot 03 detector** (SG +
stimulus direction, 22 deg/s) on data it was never tuned on.

Only *after* that validation is saved may Pilot 04 become development data for
a small SG hyperparameter study. The two stages stay separate (see
"After collection").

**Participants:** recorded under pseudonymous codes only. A person keeps their
code across pilots:

| Code | Status |
|---|---|
| P01 | returning (Pilot 03) |
| P02 | returning (Pilot 03) |
| P03 | new |

Names never go into the app, file names, metadata or this repository.

## Conditions (per participant)

| Condition (app) | Direction | Trials | All participants |
|---|---|---:|---:|
| OKN: watch the stripes naturally | Right | 4 | 12 |
| OKN | Left | 4 | 12 |
| Dot + moving: keep looking at the still red dot while the stripes move | Right | 3 | 9 |
| Dot + moving | Left | 3 | 9 |
| Dot + still: keep looking at the still red dot; stripes don't move | none | 6 | 18 |
| **Total** | | **20** | **60** |

The fixation dot never moves.

### Protocol deviation (as collected, 8–9 Nov 2026)

Each participant actually recorded **4 trials of every one of the five
conditions**:

| Condition | Direction | Planned per participant | Collected per participant | Collected, all |
|---|---|---:|---:|---:|
| OKN | Right | 4 | 4 | 12 |
| OKN | Left | 4 | 4 | 12 |
| Dot + moving | Right | 3 | **4** | 12 |
| Dot + moving | Left | 3 | **4** | 12 |
| Dot + still | none | 6 | **4** | 12 |
| **Total** | | **20** | **20** | **60** |

**Totals:** 24 OKN, 24 Dot + moving and 12 Dot + still recordings.

**Decision:** all 60 recordings are primary, and none were dropped to fit the
original plan. The decision was made on recording counts only, before any
detector was run on Pilot 04. `analysis/pilot_04/build_manifest.py` uses
4 per cell.

**Consequences:**
- there are fewer still-stripe control trials (12 instead of 18);
- Dot + moving carries more weight in pooled metrics.

The checklists below show the original plan.

## Stimulus

Identical to Pilot 03. The app applies it automatically for the Pilot 04 test
type, and every sidecar records what was actually shown.

| Parameter | App setting |
|---|---|
| Background | constant white, code value 1.0 (`stimulus.fixedBackgroundGray = 1`), no fade |
| Bars | black, code value 0 (`stripeGray = 0`) |
| Bar width | 2 % of the screen width (`stripeWidthRatio 0.02`); period 2.4 × bar width |
| Speed | 126 pt/s (0 for still stripes) |
| Duration | 10 s, landscape only, ARKit face tracking at about 60 Hz |
| Fixation dot | 12 pt red, 1.5 pt dark outline, centred (dot conditions only) |
| Viewing distance | 25–30 cm, checked before each trial |

**Checking the actual values:**
- The manifest builder checks each recording's sidecar: background 1, speed
  matching the condition, and name/metadata agreement.
- Write the session log below during collection. Don't fill it from memory.

## Keep constant

- Same iPhone and the same app build for all 60 trials. Note the build below
  and don't update the app mid-pilot.
- Same room and similar lighting.
- Before each session:
  - turn off Auto-Brightness, True Tone, Night Shift and Low Power Mode;
  - set brightness to maximum and leave it there;
  - hold the phone in landscape.
- Give the same instructions every time:
  - **OKN:** "Just watch the stripes."
  - **Dot conditions:** "Keep your eyes on the red dot the whole time."

## Session log (fill in during collection)

| Item | Value |
|---|---|
| Date(s) | |
| iPhone model / iOS version | |
| App build (git commit) | |
| Room / lighting | |
| Experimenter | |
| Mac receiver running from commit | |

## Collection order

**Blocks:** alternate participants in blocks of ten, to spread fatigue and
drift:
1. P01 1–10
2. P02 1–10
3. P03 1–10
4. P01 11–20
5. P02 11–20
6. P03 11–20

**Orders:**
- P01 and P02 repeat their Pilot 03 orders.
- P03 uses P01's order with the halves swapped.

Each half of each order is balanced, and no condition appears more than twice
in a row.

**Trial numbers:** the phone hands them out automatically, continuing its own
counter, so they won't start at 1. Write the number the result card shows into
the checklist.

**Repeats:** if a trial fails technically, record it again straight away with
the same settings. Keep the failed recording and note it; never delete it. The
replacement gets the next trial number.

**What doesn't need a repeat:** a trial with weak or no visible OKN is **not** a
failure. Keep it, especially in dot conditions.

### P01 (returning)

| # | Condition | Direction | Menu "Next:" starts with | Trial no. | Uploaded | Notes |
|---:|---|---|---|---|---|---|
| 1 | OKN | Right | `P04-P01_T…_OKN_RIGHT` | | ☐ | |
| 2 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 3 | Dot + moving | Left | `P04-P01_T…_FIXMOVE_LEFT` | | ☐ | |
| 4 | OKN | Left | `P04-P01_T…_OKN_LEFT` | | ☐ | |
| 5 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 6 | Dot + moving | Right | `P04-P01_T…_FIXMOVE_RIGHT` | | ☐ | |
| 7 | OKN | Left | `P04-P01_T…_OKN_LEFT` | | ☐ | |
| 8 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 9 | OKN | Right | `P04-P01_T…_OKN_RIGHT` | | ☐ | |
| 10 | Dot + moving | Right | `P04-P01_T…_FIXMOVE_RIGHT` | | ☐ | |
| 11 | Dot + moving | Left | `P04-P01_T…_FIXMOVE_LEFT` | | ☐ | |
| 12 | OKN | Left | `P04-P01_T…_OKN_LEFT` | | ☐ | |
| 13 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 14 | OKN | Right | `P04-P01_T…_OKN_RIGHT` | | ☐ | |
| 15 | Dot + moving | Right | `P04-P01_T…_FIXMOVE_RIGHT` | | ☐ | |
| 16 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 17 | OKN | Right | `P04-P01_T…_OKN_RIGHT` | | ☐ | |
| 18 | Dot + moving | Left | `P04-P01_T…_FIXMOVE_LEFT` | | ☐ | |
| 19 | Dot + still | — | `P04-P01_T…_FIXSTILL_NONE` | | ☐ | |
| 20 | OKN | Left | `P04-P01_T…_OKN_LEFT` | | ☐ | |

### P02 (returning)

| # | Condition | Direction | Menu "Next:" starts with | Trial no. | Uploaded | Notes |
|---:|---|---|---|---|---|---|
| 1 | OKN | Left | `P04-P02_T…_OKN_LEFT` | | ☐ | |
| 2 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 3 | Dot + moving | Right | `P04-P02_T…_FIXMOVE_RIGHT` | | ☐ | |
| 4 | OKN | Right | `P04-P02_T…_OKN_RIGHT` | | ☐ | |
| 5 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 6 | Dot + moving | Left | `P04-P02_T…_FIXMOVE_LEFT` | | ☐ | |
| 7 | OKN | Right | `P04-P02_T…_OKN_RIGHT` | | ☐ | |
| 8 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 9 | OKN | Left | `P04-P02_T…_OKN_LEFT` | | ☐ | |
| 10 | Dot + moving | Left | `P04-P02_T…_FIXMOVE_LEFT` | | ☐ | |
| 11 | Dot + moving | Right | `P04-P02_T…_FIXMOVE_RIGHT` | | ☐ | |
| 12 | OKN | Right | `P04-P02_T…_OKN_RIGHT` | | ☐ | |
| 13 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 14 | OKN | Left | `P04-P02_T…_OKN_LEFT` | | ☐ | |
| 15 | Dot + moving | Left | `P04-P02_T…_FIXMOVE_LEFT` | | ☐ | |
| 16 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 17 | OKN | Left | `P04-P02_T…_OKN_LEFT` | | ☐ | |
| 18 | Dot + moving | Right | `P04-P02_T…_FIXMOVE_RIGHT` | | ☐ | |
| 19 | Dot + still | — | `P04-P02_T…_FIXSTILL_NONE` | | ☐ | |
| 20 | OKN | Right | `P04-P02_T…_OKN_RIGHT` | | ☐ | |

### P03 (new)

| # | Condition | Direction | Menu "Next:" starts with | Trial no. | Uploaded | Notes |
|---:|---|---|---|---|---|---|
| 1 | Dot + moving | Left | `P04-P03_T…_FIXMOVE_LEFT` | | ☐ | |
| 2 | OKN | Left | `P04-P03_T…_OKN_LEFT` | | ☐ | |
| 3 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 4 | OKN | Right | `P04-P03_T…_OKN_RIGHT` | | ☐ | |
| 5 | Dot + moving | Right | `P04-P03_T…_FIXMOVE_RIGHT` | | ☐ | |
| 6 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 7 | OKN | Right | `P04-P03_T…_OKN_RIGHT` | | ☐ | |
| 8 | Dot + moving | Left | `P04-P03_T…_FIXMOVE_LEFT` | | ☐ | |
| 9 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 10 | OKN | Left | `P04-P03_T…_OKN_LEFT` | | ☐ | |
| 11 | OKN | Right | `P04-P03_T…_OKN_RIGHT` | | ☐ | |
| 12 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 13 | Dot + moving | Left | `P04-P03_T…_FIXMOVE_LEFT` | | ☐ | |
| 14 | OKN | Left | `P04-P03_T…_OKN_LEFT` | | ☐ | |
| 15 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 16 | Dot + moving | Right | `P04-P03_T…_FIXMOVE_RIGHT` | | ☐ | |
| 17 | OKN | Left | `P04-P03_T…_OKN_LEFT` | | ☐ | |
| 18 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` | | ☐ | |
| 19 | OKN | Right | `P04-P03_T…_OKN_RIGHT` | | ☐ | |
| 20 | Dot + moving | Right | `P04-P03_T…_FIXMOVE_RIGHT` | | ☐ | |

## Per trial

1. **On the menu**, set:
   - **Test Type:** Pilot 04;
   - **Participant:** P01, P02 or P03 (remembered between trials);
   - **Condition**;
   - **Direction:** moving stripes only. Still stripes show "Direction: none".

   Check that the "Next:" line matches the checklist row exactly.
2. **Record 10 Seconds**, rotate to landscape and tap **Check Position**. Wait
   for "Ready to record", then **Start Trial**.
3. **Check the result card.** It should show the file name and
   **Uploaded to Mac**.
   - If the upload fails, the files stay on the phone. **Retry Upload** sends
     the same files under the same name.
   - The Mac accepts an identical retry and refuses a different recording with
     the same name, so nothing is ever overwritten.

## File names and metadata

**Name format:** file-name contract 1, unchanged from Pilot 03.

```
P04-{P01|P02|P03}_T{trial ≥ 3 digits}_{OKN|FIXMOVE|FIXSTILL}_{RIGHT|LEFT|NONE}_{UTC yyyyMMdd_HHmmss}
e.g. P04-P03_T061_FIXMOVE_RIGHT_20261109_150100
```

- The condition code is `FIXMOVE`, not `FIXMOV`.
- Pilot and participant codes use the digit zero. The Mac refuses `PO4` and
  `PO1` with a letter O.
- The folder, `.csv` and `.json` share the name.

**Sidecar** (schema 6, unchanged), with fields that must match the name:
- `experimentID` `"P04"`;
- `testTypeName` `"Pilot 04"`;
- `participantID`;
- `trialNumber`;
- `directionCode`;
- `recordingName`.

`stimulus` holds the actual stimulus. The receiver refuses a pair whose
metadata disagrees with its name.

## Mac receiver

Run it from the repository on the branch that has Pilot 04 support (`feature/pilot-04`, or `main` once merged):

```bash
openssl rand -hex 6 > ~/.nystagmusense_token        # only if it doesn't exist yet
NS_UPLOAD_TOKEN=$(cat ~/.nystagmusense_token) python3 scripts/receive_recordings.py --lan
ipconfig getifaddr en0                              # the Mac's IP for the phone's Mac Transfer screen
curl -H "X-Upload-Token: $(cat ~/.nystagmusense_token)" http://localhost:8765/health   # {"status": "ok", "name_contract": 1}
```

Recordings arrive in `trials/<name>/`. That folder is git-ignored, so nothing
is committed.

## Before the first participant: five-trial smoke test

Use the real phone, receiver and Wi-Fi. Then move the five smoke recordings to
`trials/_smoke_P04/`, so the manifest never counts them.

| # | Participant | Condition | Direction | "Next:" starts with |
|---|---|---|---|---|
| 1 | P01 | OKN | Right | `P04-P01_T…_OKN_RIGHT` |
| 2 | P02 | OKN | Left | `P04-P02_T…_OKN_LEFT` |
| 3 | P03 | Dot + moving | Right | `P04-P03_T…_FIXMOVE_RIGHT` |
| 4 | P01 | Dot + moving | Left | `P04-P01_T…_FIXMOVE_LEFT` |
| 5 | P03 | Dot + still | — | `P04-P03_T…_FIXSTILL_NONE` |

**For each smoke trial:**
1. The result card shows **Uploaded to Mac**.
2. `ls trials/<name>/` shows exactly `<name>.csv` and `<name>.json`.
3. The sidecar fields match the name:
   ```bash
   python3 -c "import json,sys; m=json.load(open(sys.argv[1])); print(m['experimentID'], m['participantID'], m['trialNumber'], m['directionCode'], m['recordingName'], m['stimulus']['fixedBackgroundGray'], m['stimulus']['speedPointsPerSecond'])" trials/<name>/<name>.json
   ```
4. Downstream parsing works:
   `python3 scripts/detect_okn.py trials/<name>/<name>.csv`
   prints a report without errors.

**After trial 5:**
- Tap **Retry Upload** on its card. The Mac log shows "already received", and
  no second folder appears.
- Turn the receiver off and record one more P01 OKN Right trial. The card shows
  the upload failed, and the files stay on the phone.
- Restart the receiver and tap **Retry Upload**. The trial arrives under the
  same name.
- Move it to `trials/_smoke_P04/` too.

Then move all smoke recordings:

```bash
mkdir -p trials/_smoke_P04 && mv trials/P04-* trials/_smoke_P04/
```

## After collection

These steps run in order. Each is a separate pull request, and nothing is
tuned before step 4.

1. **Quality and manifest.** `python3 analysis/pilot_04/build_manifest.py`
   writes `analysis/pilot_04/manifest.csv`.
   - Technical status is set per recording.
   - Primary recordings get `role=external_validation` and `split=evaluation`.
   - Later recordings are `extra`.
   - Folders moved to `trials/_excluded_P04/` are `excluded`.

   It reports any cell below its planned count. Don't change the manifest by
   hand.
2. **Annotation.** One reviewer, no detector suggestions; Pilot 04 trials are
   held out, so the tool never computes suggestions for them:
   ```bash
   python3 scripts/annotate_okn.py --split evaluation --plan analysis/pilot_04/manifest.csv \
       --annotator AA --labels-dir analysis/annotations_p04
   python3 analysis/pilot_04/build_manifest.py --review-status --annotator AA    # all 60 must be complete (manual)
   ```
   - Labels stay in `analysis/annotations_p04/`, git-ignored and separate from
     Pilot 03.
   - A reviewed trial with zero resets is valid.
   - Labels are never changed after scoring.
3. **External validation (Report A).** Score the **frozen Pilot 03 detector**
   once, unchanged (`analysis/pilot_03/frozen_detector.md`, PR #19):
   ```bash
   python3 scripts/evaluate_okn.py --manifest analysis/pilot_04/manifest.csv --split evaluation --allow-evaluation \
       --labels-dir analysis/annotations_p04 --annotator AA --artifacts exclude --detector sg-direction \
       --output-csv analysis/pilot_04/validation/validation_results.csv
   ```
   - Report by participant (returning P01/P02 separately from new P03), by
     condition and by direction.
   - Still stripes report false positives only.
   - Dot + moving is reported as its own condition: fixation doesn't rule out
     real OKN.
   - Save `validation_summary.md` and a few plots, and never edit them
     afterwards.
4. **SG study (Report B, exploratory).** Only after Report A is committed.
   - Pilot 04 is relabelled `p04_development_after_validation` in a **new**
     manifest. The original manifest and Report A stay as they were.
   - Pool it with the Pilot 03 development trials. The 12 Pilot 03 held-out
     recordings stay out.
   - **Grid:**
     - threshold 18–28 deg/s in steps of 2;
     - SG window 5 or 7;
     - SG order 2 or 3;
     - direction check always on.

     That is 24 configurations. All are valid, since the order is always below
     the window. `detect_okn.Params` already has `sg_window` and `sg_polyorder`.
   - Use participant-grouped cross-validation, holding out one participant at a
     time. P01 and P02 appear in both pilots, so only P03 tests an unseen
     person.
   - **Scoring:**
     - F1;
     - still-stripe false positives;
     - OKN recall;
     - consistency across participants;
     - SG 22 deg/s (window 5, order 2) as the reference.
   - Prefer the simpler setting when gains are small.
   - Report B is never presented as independent validation. A new
     configuration must be frozen and tested on future recordings.

## Labels

Reference annotations come from one reviewer. Inter-annotator reliability is
not measured, and labels describe what is visible in the ARKit signal. They
are not physiological ground truth.
