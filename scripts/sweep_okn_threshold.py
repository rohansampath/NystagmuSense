#!/usr/bin/env python3
"""Development-only sweep of the SG fast-phase velocity threshold.

    python3 scripts/sweep_okn_threshold.py --manifest analysis/pilot_03/manifest.csv \\
        --labels-dir <labels> [--trials-dir trials] [--output-dir analysis/pilot_03]

Scores detect_okn.py's SG detector (all other parameters at their defaults)
on the manifest's primary DEVELOPMENT trials only, with evaluate_okn.py's
rules: one-to-one matching within ±100 ms, uncertain labels excluded,
predictions on artifact labels excluded (--artifacts exclude). It never reads
evaluation trials and refuses to run while any development trial is not
completely reviewed (override: --allow-incomplete).

Selection rule (fixed before looking at results): the threshold with the
highest pooled development F1; thresholds within 0.01 of it are treated as
tied, and among those the one with the fewest false positives per 10 s wins
(then the higher threshold). The original 40 deg/s is reported as the
baseline.

Writes threshold_sweep.csv (every threshold × group), per_condition.csv
(best vs 40 deg/s), dev_trials_<thr>.csv (per trial, best and 40 deg/s),
threshold_sweep.png (P/R/F1) and false_positives.png (FP per 10 s).
Labels are ARKit-visible events, not physiological ground truth.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402

THRESHOLDS = list(range(10, 41, 2))
BASELINE = 40
TIE_F1 = 0.01


def predictions_at(threshold):
    params = detect_okn.Params(fast_threshold=threshold)
    return lambda path: [f["start"] for f in detect_okn.analyse(detect_okn.load_session(path), params)["fast"]]


def sweep(labels_dir, trials_dir, include, thresholds=THRESHOLDS, tolerance=evaluate_okn.DEFAULT_TOLERANCE_S,
          annotator=None, allow_incomplete=True):
    """({threshold: [(kind, value, summary)]}, {threshold: per-trial scores}) on the given trials."""
    reviews = evaluate_okn.development_reviews(labels_dir, include, annotator)
    who = next((r["annotator_id"] for r in reviews.values()), annotator)
    if who is None:
        raise ValueError("no development reviews found")
    results, trials = {}, {}
    for thr in thresholds:
        scored, skipped = evaluate_okn.evaluate(labels_dir, trials_dir, tolerance, annotator=who, predict=predictions_at(thr),
                                          include=include, artifacts="exclude")
        if skipped and not allow_incomplete:
            raise ValueError("development trials could not be scored: " + "; ".join(f"{t}: {why}" for t, _, why in skipped))
        if not scored:
            raise ValueError("no development recordings could be scored")
        results[thr] = evaluate_okn.group_rows(scored)
        trials[thr] = scored
    return results, trials


def overall(rows):
    return next(g for kind, _, g in rows if kind == "all")


def choose(results):
    """Best threshold under the documented rule."""
    f1 = {t: overall(rows)["f1"] or 0 for t, rows in results.items()}
    best = max(f1.values())
    tied = [t for t in results if f1[t] >= best - TIE_F1]
    return min(tied, key=lambda t: (overall(results[t])["fp_per_10s"] or 0, -t))


FIELDS = ["threshold", "group", "value", "n_trials", "tp", "fp", "fn", "precision", "recall", "f1",
          "fp_per_10s", "mean_abs_offset_ms"]


def row(thr, kind, value, g):
    num = lambda v, d=3: "" if v is None else f"{v:.{d}f}"
    return dict(threshold=thr, group=kind, value=value, n_trials=g["n_trials"], tp=g["tp"], fp=g["fp"], fn=g["fn"],
                precision=num(g["precision"]), recall=num(g["recall"]), f1=num(g["f1"]),
                fp_per_10s=num(g["fp_per_10s"]), mean_abs_offset_ms=num(g["mean_abs_offset_ms"], 1))


def write_outputs(results, trials, best, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "threshold_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for thr, rows in results.items():
            w.writerows(row(thr, kind, value, g) for kind, value, g in rows)
    with open(out_dir / "per_condition.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for thr in sorted({best, BASELINE}):
            w.writerows(row(thr, kind, value, g) for kind, value, g in results[thr] if kind != "all")
    for thr in sorted({best, BASELINE}):
        evaluate_okn.write_trial_csv(trials[thr], out_dir / f"dev_trials_{thr}.csv")
    ts = list(results)
    get = lambda key, rows: [overall(results[t])[key] for t in ts] if rows is None else \
        [next((g[key] for k, v, g in results[t] if (k, v) == rows), None) for t in ts]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for key, color in (("precision", "tab:blue"), ("recall", "tab:orange"), ("f1", "k")):
        ax.plot(ts, [v if v is not None else float("nan") for v in get(key, None)], "o-", color=color, label=key)
    for x, ls, name in ((best, "-", f"best {best}"), (BASELINE, "--", f"baseline {BASELINE}")):
        ax.axvline(x, color="0.5", ls=ls, lw=1, label=name)
    ax.set(xlabel="SG fast-phase threshold (deg/s)", ylabel="event-level score (development)", ylim=(0, 1.02))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "threshold_sweep.png", dpi=120)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(ts, get("fp_per_10s", None), "o-", color="k", label="all development")
    conditions = sorted({v for k, v, _ in results[ts[0]] if k == "condition"})
    for cond in conditions:
        ax.plot(ts, get("fp_per_10s", ("condition", cond)), "o-", lw=1, label=cond)
    ax.axvline(best, color="0.5", lw=1)
    ax.axvline(BASELINE, color="0.5", ls="--", lw=1)
    ax.set(xlabel="SG fast-phase threshold (deg/s)", ylabel="false positives per 10 s (development)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "false_positives.png", dpi=120)
    plt.close("all")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--annotator", help="independent annotator to score (required if more than one is present)")
    ap.add_argument("--trials-dir", type=Path, default=Path(__file__).resolve().parents[1] / "trials")
    ap.add_argument("--output-dir", type=Path, default=Path("analysis/pilot_03"))
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="run even though some development trials aren't completely reviewed")
    args = ap.parse_args(argv)
    include = evaluate_okn.load_manifest(args.manifest, "development")      # never the evaluation split
    try:
        reviews = evaluate_okn.development_reviews(args.labels_dir, include, args.annotator)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    missing = sorted(t for t in include if reviews.get(t, {}).get("status") != "complete")
    if missing and not args.allow_incomplete:
        print(f"error: {len(missing)} development trials aren't completely reviewed:\n  " + "\n  ".join(missing),
              file=sys.stderr)
        return 1
    try:
        results, trials = sweep(args.labels_dir, args.trials_dir, include, annotator=args.annotator,
                               allow_incomplete=args.allow_incomplete)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    best = choose(results)
    write_outputs(results, trials, best, args.output_dir)
    print(f"development trials scored: {overall(results[BASELINE])['n_trials']} of {len(include)}")
    print(f"{'thr':>4}  P     R     F1    FP/10s")
    for thr, rows in results.items():
        g = overall(rows)
        mark = "  ← best" if thr == best else ("  ← baseline" if thr == BASELINE else "")
        print(f"{thr:4d}  {evaluate_okn.fmt(g['precision']):5} {evaluate_okn.fmt(g['recall']):5} "
              f"{evaluate_okn.fmt(g['f1']):5} {evaluate_okn.fmt(g['fp_per_10s'])}{mark}")
    print(f"outputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
