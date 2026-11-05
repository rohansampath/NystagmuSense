#!/usr/bin/env python3
"""Blinded second-annotator review of Pilot 03 development recordings.

    python3 analysis/pilot_03/second_review.py select [--seed 20261106]
    python3 analysis/pilot_03/second_review.py agree --first <labels AA> --second <labels RS> \\
        [--first-id AA] [--second-id RS]

select: picks 4 Dot + moving recordings (one per participant × stripe
direction) and 2 OKN recordings (one per participant, opposite directions)
from the primary DEVELOPMENT trials, skipping any recording shown in a
committed figure (the second annotator may have seen those). Writes
second_review_trials.csv. The choice uses the manifest and the seed only.

agree: one-to-one matching of the two annotators' fast_phase labels within
±100 ms (evaluate_okn.match_events), per trial and pooled. Agreement =
2·matched / (2·matched + first-only + second-only). Every unmatched label is
listed. Neither label set is modified.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import annotate_okn  # noqa: E402
import evaluate_okn  # noqa: E402

HERE = Path(__file__).resolve().parent
SHOWN_IN_FIGURES = {12, 20, 29, 34, 39, 43}   # failure_examples.png, comparison/examples.png
TRIALS_CSV = HERE / "second_review_trials.csv"


def select(manifest, seed):
    rows = [r for r in annotate_okn._read_rows(manifest)
            if r["eligibility"] == "primary" and r["split"] == "development"
            and int(r["trial_number"]) not in SHOWN_IN_FIGURES]
    rng = random.Random(seed)
    cell = lambda p, c, d: sorted((r for r in rows if (r["participant"], r["condition"], r["direction"]) == (p, c, d)),
                                  key=lambda r: int(r["trial_number"]))
    picked = [rng.choice(cell(p, "FIXMOVE", d)) for p in ("P01", "P02") for d in ("LEFT", "RIGHT")]
    first = rng.choice(("LEFT", "RIGHT"))
    second = "RIGHT" if first == "LEFT" else "LEFT"
    picked += [rng.choice(cell("P01", "OKN", first)), rng.choice(cell("P02", "OKN", second))]
    return picked


def agreement(first_events, second_events, tolerance=evaluate_okn.DEFAULT_TOLERANCE_S):
    """(matched pairs, first-only times, second-only times) for fast_phase labels."""
    a = [t for t, lab in first_events if lab == "fast_phase"]
    b = [t for t, lab in second_events if lab == "fast_phase"]
    return evaluate_okn.match_events(a, b, tolerance)


def agree_score(matched, only_first, only_second):
    denominator = 2 * matched + only_first + only_second
    return 2 * matched / denominator if denominator else None


def load(labels_dir, annotator):
    reviews = {r["trial_id"]: r for r in annotate_okn._read_rows(Path(labels_dir) / "reviews.csv")
               if r["annotator_id"] == annotator}
    events = {}
    for e in annotate_okn._read_rows(Path(labels_dir) / "events.csv"):
        if e["annotator_id"] == annotator:
            events.setdefault(e["trial_id"], []).append((float(e["event_time_s"]), e["label"]))
    return reviews, events


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--manifest", type=Path, default=HERE / "manifest.csv")
    s.add_argument("--seed", type=int, default=20261106)
    g = sub.add_parser("agree")
    g.add_argument("--first", type=Path, required=True)
    g.add_argument("--second", type=Path, required=True)
    g.add_argument("--first-id", default="AA")
    g.add_argument("--second-id", default="RS")
    g.add_argument("--trials", type=Path, default=TRIALS_CSV)
    args = ap.parse_args(argv)
    if args.cmd == "select":
        picked = select(args.manifest, args.seed)
        with open(TRIALS_CSV, "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["trial_id", "participant", "condition", "direction"])
            for r in picked:
                w.writerow([r["trial_id"], r["participant"], r["condition"], r["direction"]])
        print(f"wrote {TRIALS_CSV}")
        for r in picked:
            print(f"  {r['trial_id']}")
        return 0
    trial_ids = [r["trial_id"] for r in annotate_okn._read_rows(args.trials)]
    rev_a, ev_a = load(args.first, args.first_id)
    rev_b, ev_b = load(args.second, args.second_id)
    if args.first.resolve() == args.second.resolve() and args.first_id == args.second_id:
        ap.error("agreement requires two different annotators")
    for reviews in (rev_a, rev_b):
        for tid in trial_ids:
            if tid in reviews and reviews[tid]["annotation_method"] != "manual":
                ap.error(f"{tid}: blinded agreement requires independent manual labels")
    total = [0, 0, 0]
    print(f"{'trial':42} matched {args.first_id}-only {args.second_id}-only agreement")
    lines = []
    for tid in trial_ids:
        if rev_b.get(tid, {}).get("status") != "complete" or rev_a.get(tid, {}).get("status") != "complete":
            print(f"{tid:42} not completely reviewed by both annotators; skipped")
            continue
        pairs, only_a, only_b = agreement(ev_a.get(tid, []), ev_b.get(tid, []))
        counts = (len(pairs), len(only_a), len(only_b))
        total = [x + y for x, y in zip(total, counts)]
        print(f"{tid:42} {counts[0]:7d} {counts[1]:7d} {counts[2]:7d} {evaluate_okn.fmt(agree_score(*counts))}")
        lines += [f"  {tid}: {args.first_id} only at {t:.3f} s" for t in only_a]
        lines += [f"  {tid}: {args.second_id} only at {t:.3f} s" for t in only_b]
    print(f"{'pooled':42} {total[0]:7d} {total[1]:7d} {total[2]:7d} {evaluate_okn.fmt(agree_score(*total))}")
    if lines:
        print("\ndisagreements:\n" + "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
