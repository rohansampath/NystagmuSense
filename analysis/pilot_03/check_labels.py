#!/usr/bin/env python3
"""Flag Pilot 03 development labels for human review (never edits them).

    python3 analysis/pilot_03/check_labels.py --labels-dir <annotations_p03> [--trials-dir trials]

Uses the raw eye-angle signal only (the SG velocity the annotation tool
shows), never detector output. For each fast_phase label it looks at the
largest |velocity| within -100..+150 ms of the click:

- opposite:  the jump goes the wrong way for an OKN reset in that trial
             (stripes right → resets are + in the plotted convention, left → -),
             so it is more likely a saccade than an OKN reset;
- weak:      peak under 12 deg/s, barely above fixation noise;
- close:     two labels under 250 ms apart (possible double click);
- still:     any fast_phase in a still-stripe trial (allowed, but check it
             isn't an isolated saccade);
- unreviewed / in_progress trials in the manifest are listed too.
Writes label_flags.csv next to this script. Evaluation requires both
--split evaluation and --allow-evaluation; it is never inspected by default.
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import annotate_okn  # noqa: E402

HERE = Path(__file__).resolve().parent
EXPECTED_SIGN = {"RIGHT": 1, "LEFT": -1}
WEAK_DEG_S, CLOSE_S = 12.0, 0.25


def flags_for_trial(signal, times, direction):
    t, v, ok = signal["t"], signal["velocity"], signal["valid"]
    out = []
    times = sorted(times)
    for x in times:
        w = (t >= x - 0.10) & (t <= x + 0.15) & ok & np.isfinite(v)
        if not w.any():
            out.append((x, "invalid", "no valid samples near the label"))
            continue
        peak = float(v[w][np.argmax(np.abs(v[w]))])
        sign = EXPECTED_SIGN.get(direction)
        if direction == "NONE":
            out.append((x, "still", f"fast_phase in a still-stripe trial (peak {peak:+.0f} deg/s)"))
        elif sign and np.sign(peak) != sign:
            out.append((x, "opposite", f"peak {peak:+.0f} deg/s is against the reset direction"))
        elif abs(peak) < WEAK_DEG_S:
            out.append((x, "weak", f"peak only {peak:+.0f} deg/s"))
    for a, b in zip(times, times[1:]):
        if b - a < CLOSE_S:
            out.append((a, "close", f"next label {1000 * (b - a):.0f} ms later"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--manifest", type=Path, default=HERE / "manifest.csv")
    ap.add_argument("--output", type=Path, default=HERE / "label_flags.csv")
    ap.add_argument("--split", choices=("development", "evaluation"), default="development")
    ap.add_argument("--allow-evaluation", action="store_true",
                    help="inspect held-out labels only after the detector is frozen")
    ap.add_argument("--annotator", help="independent annotator whose labels should be checked")
    args = ap.parse_args(argv)
    if args.split == "evaluation" and not args.allow_evaluation:
        ap.error("the evaluation split is held out; --allow-evaluation is required")
    with args.manifest.open(newline="") as f:
        manifest = [r for r in csv.DictReader(f) if r["eligibility"] == "primary" and r["split"] == args.split]
    events = annotate_okn._read_rows(args.labels_dir / "events.csv")
    import evaluate_okn
    reviews = evaluate_okn.development_reviews(args.labels_dir, {r["trial_id"]: r for r in manifest}, args.annotator)
    rows = []
    for m in manifest:
        tid = m["trial_id"]
        review = reviews.get(tid)
        status = review["status"] if review else "not opened"
        if status != "complete":
            rows.append(dict(trial_id=tid, split=m["split"], time_s="", flag="unreviewed", detail=status))
        times = [t for t, label in evaluate_okn.review_events(events, review) if label == "fast_phase"] if review else []
        if times:
            signal = annotate_okn.load_signal(args.trials_dir / tid / f"{tid}.csv")
            for x, flag, detail in flags_for_trial(signal, times, m["direction"]):
                rows.append(dict(trial_id=tid, split=m["split"], time_s=f"{x:.3f}", flag=flag, detail=detail))
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["trial_id", "split", "time_s", "flag", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["flag"]] = counts.get(r["flag"], 0) + 1
    print(f"wrote {args.output}: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
