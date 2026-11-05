# Pilot 03: blinded second-annotator review

**Why:** the Dot + moving labels are the least certain part of the benchmark.
- One third of them are steps under 1°; the median is 1.3°, against 3.2° for OKN. See `comparison/label_step_sizes.csv`.
- Many never reach 24 deg/s, even unsmoothed.

Neither the detector nor the first annotator can be assumed right. A second,
independent annotator tells us how reproducible these labels are.

## Recordings (`second_review_trials.csv`, seed 20261106)

`second_review.py select` draws from the **development** split only:
- one Dot + moving recording per participant × stripe direction;
- one OKN recording per participant, in opposite directions.

It skips every recording shown in a committed figure (T012, T020, T029, T034,
T039, T043).

| Participant | Condition | Direction | Recording |
|---|---|---|---|
| P01 | Dot + moving | Left | T024 |
| P01 | Dot + moving | Right | T019 |
| P02 | Dot + moving | Left | T041 |
| P02 | Dot + moving | Right | T044 |
| P01 | OKN | Left | T014 |
| P02 | OKN | Right | T040 |

## Rules for the second annotator (Rohan)

**Before annotating, do not open:**
- the first annotator's label folder;
- any `analysis/pilot_03` figure or CSV that names these recordings;
- detector output for them.

**While annotating:**
- Use independent mode, which is the default. Never pass `--assisted`.
- Use a separate, empty label folder, so the two label sets never mix.
- Follow the labelling definition in `README.md` ("What is labelled"):
  - `fast_phase` is a reset *against* the stripes after a drift *with* them;
  - use `uncertain` for doubtful cases;
  - leave wrong-direction jumps unlabelled.
- Press `x` on each trial to mark it reviewed, then save.

```bash
T=~/CS_Projects/NystagmuSense/trials
R=~/CS_Projects/NystagmuSense-private/annotations_p03_RS     # Rohan's own folder
for id in $(tail -n +2 analysis/pilot_03/second_review_trials.csv | cut -d, -f1); do
  python3 scripts/annotate_okn.py $T/$id/$id.csv --annotator RS --labels-dir $R
done
```

With the queue tool from PR #13, all six CSVs can be passed to one window instead.

## Agreement

```bash
python3 analysis/pilot_03/second_review.py agree \
  --first ~/CS_Projects/NystagmuSense-annot/analysis/annotations_p03 --first-id AA \
  --second ~/CS_Projects/NystagmuSense-private/annotations_p03_RS --second-id RS
```

**Matching:** the same as detector scoring, one-to-one within ±100 ms.

**Output:** per recording and pooled:
- matched, AA-only and RS-only counts;
- agreement = 2·matched / (2·matched + AA-only + RS-only);
- every disagreement, with its time.

**Using the result:**
- Neither label set is edited.
- If Dot + moving agreement is clearly below OKN agreement, report Dot + moving
  event metrics as provisional.
- Any change to the reference labels is a separate, documented decision, made
  before the evaluation split is scored.

**Status:** not yet done. All results in `comparison_report.md` use the first
annotator's labels only.
