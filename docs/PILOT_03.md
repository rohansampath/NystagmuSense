# Pilot 03 (P03): high-contrast OKN validation set

Purpose: a balanced set of recordings for validating OKN fast-phase detection
against human labels. It is **not** a contrast-sensitivity measurement: every
trial uses the same full-contrast stimulus.

Participants are recorded under pseudonymous codes only, **P01** and **P02**.
Names never go into the app, file names, metadata or this repository.

## Conditions (per participant)

| Condition (app) | Direction | Trials |
|---|---|---:|
| OKN | Right | 4 |
| OKN | Left | 4 |
| Dot + moving | Right | 3 |
| Dot + moving | Left | 3 |
| Dot + still | none | 6 |
| **Total** | | **20** |

40 recordings in total: 16 OKN, 12 dot + moving stripes, 12 dot + still stripes.
The fixation dot never moves.

## Stimulus (fixed for every P03 trial)

| Parameter | Value |
|---|---|
| Background | constant white, sRGB code value 1.0 (`stimulus.fixedBackgroundGray = 1`), no fade |
| Bars | black, code value 0 (`stripeGray = 0`), so display contrast is at its maximum for the whole trial |
| Bar width | 2 % of the screen width (`stripeWidthRatio 0.02`); period 2.4 × bar width |
| Speed | 126 pt/s (0 for still stripes) |
| Duration | 10 s, landscape only, ARKit face tracking at 60 Hz |
| Fixation dot | 12 pt red, 1.5 pt dark outline, centred (dot conditions only) |
| Viewing distance | 25–30 cm, enforced by the pre-trial distance check |

On an iPhone 16 Pro in landscape (874 × 402 pt, about 0.166 mm per pt), that is
a 2.9 mm bar and a 7.0 mm period moving at 20.9 mm/s. At 30 cm this comes to about
0.75 cycles/deg at 4.0 deg/s, and at 25 cm about 0.62 cycles/deg at 4.8 deg/s.
These are estimates from screen geometry. Neither luminance nor contrast is
photometrically measured.

The constant background applies only to the Pilot 03 test type. Other test
types keep their default white → black fade, so earlier experiments are
unchanged. Every sidecar records the stimulus it was actually shown.

## Keep constant

Use the same iPhone and app build for all 40 trials. Keep the room lighting as
similar as possible.

Before the session, on the phone:
- turn off Auto-Brightness, True Tone and Night Shift;
- turn off Low Power Mode;
- set brightness to maximum and leave it there.

## Collection order

Each participant's order is balanced across their two halves (trials 1–10 and
11–20). P02 mirrors P01's directions, and no condition appears more than twice
in a row.

To spread fatigue and drift over both people, alternate blocks:
1. P01 trials 1–10
2. P02 trials 1–10
3. P01 trials 11–20
4. P02 trials 11–20

| # | P01 | P02 |
|---:|---|---|
| 1 | OKN · Right | OKN · Left |
| 2 | Dot + still | Dot + still |
| 3 | Dot + moving · Left | Dot + moving · Right |
| 4 | OKN · Left | OKN · Right |
| 5 | Dot + still | Dot + still |
| 6 | Dot + moving · Right | Dot + moving · Left |
| 7 | OKN · Left | OKN · Right |
| 8 | Dot + still | Dot + still |
| 9 | OKN · Right | OKN · Left |
| 10 | Dot + moving · Right | Dot + moving · Left |
| 11 | Dot + moving · Left | Dot + moving · Right |
| 12 | OKN · Left | OKN · Right |
| 13 | Dot + still | Dot + still |
| 14 | OKN · Right | OKN · Left |
| 15 | Dot + moving · Right | Dot + moving · Left |
| 16 | Dot + still | Dot + still |
| 17 | OKN · Right | OKN · Left |
| 18 | Dot + moving · Left | Dot + moving · Right |
| 19 | Dot + still | Dot + still |
| 20 | OKN · Left | OKN · Right |

If a trial fails technically (see below), record it again straight away with
the same settings. Keep the failed recording and note it; don't delete it. The
replacement gets the next trial number.

## Per trial

1. Menu:
   - **Test Type** Pilot 03;
   - **Participant**;
   - **Condition**;
   - **Direction** (moving stripes only).

   Check the "Next:" line, e.g. `P03-P01_T041_OKN_LEFT`.
2. **Record 10 Seconds**, then rotate to landscape and tap **Check Position**.
   Wait for "Ready to record", then **Start Trial**.
3. The result card should show the file name and **Uploaded to Mac**. If the
   upload fails, the files stay on the phone. **Retry Upload** sends the same
   files under the same name.

## Quality review (after collection)

Record a status and a reason for every recording; never delete one.

- **Technical failure**: wrong stimulus or settings for the planned trial, a
  partial recording (issues in the sidecar), large tracking loss, missing
  samples or invalid timestamps, or a failed or bypassed distance check.
- **Valid but difficult**: weak or irregular OKN, few resets, noisy trace. It is
  kept and labelled like any other trial. A trial is never excluded just
  because OKN isn't obvious; in fixation conditions that is the expected
  result.

## Development / evaluation split (before any tuning)

Once all trials are recorded and quality-reviewed, write the split to a
manifest **before** running any threshold search:

- 28 development and 12 held-out evaluation recordings;
- stratified by participant × condition × direction as closely as the counts
  allow;
- whole recordings only, never frames of one recording on both sides.

Evaluation recordings are labelled without suggestions and scored once, with
the frozen detector. Both participants appear on both sides, so results don't
show generalisation to unseen people.
