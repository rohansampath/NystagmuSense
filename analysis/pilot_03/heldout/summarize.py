#!/usr/bin/env python3
"""Summarise the frozen detector's per-trial results (no detector is run here).

    python3 analysis/pilot_03/heldout/summarize.py

Reads heldout_trials.csv (the one-time evaluation run) and
dev_reference_trials.csv (the same command on the development split) and
writes summary.csv and dev_vs_heldout.png. Pooled TP/FP/FN per group; still
stripes report false positives only. The bootstrap resamples whole recordings
(seed 20261108) as a rough interval, not a formal test.
"""

import csv
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SPLITS = {"development": HERE / "dev_reference_trials.csv", "evaluation": HERE / "heldout_trials.csv"}


def pool(rows):
    tp, fp, fn = (sum(int(r[k]) for r in rows) for k in ("tp", "fp", "fn"))
    seconds = sum(float(r["duration_s"]) for r in rows)
    weighted = sum(float(r["mean_abs_offset_ms"]) * int(r["tp"]) for r in rows if r["mean_abs_offset_ms"])
    return dict(n=len(rows), tp=tp, fp=fp, fn=fn,
                precision=tp / (tp + fp) if tp + fp else None, recall=tp / (tp + fn) if tp + fn else None,
                f1=2 * tp / (2 * tp + fp + fn) if tp + fn else None,     # n/a when there are no resets
                fp_per_10s=10 * fp / seconds, timing_ms=weighted / tp if tp else None)


def bootstrap_f1(rows, n=5000, seed=20261108):
    counts = np.array([[int(r["tp"]), int(r["fp"]), int(r["fn"])] for r in rows])
    rng = np.random.default_rng(seed)
    f1 = []
    for _ in range(n):
        tp, fp, fn = counts[rng.integers(0, len(counts), len(counts))].sum(0)
        if 2 * tp + fp + fn:
            f1.append(2 * tp / (2 * tp + fp + fn))
    return np.percentile(f1, [2.5, 97.5])


def groups(rows):
    yield "all", "all", rows
    for key in ("participant", "condition", "direction"):
        for value in sorted({r[key] for r in rows}):
            yield key, value, [r for r in rows if r[key] == value]


def fmt(v, d=3):
    return "" if v is None else f"{v:.{d}f}"


def main():
    data = {s: list(csv.DictReader(open(p))) for s, p in SPLITS.items()}
    with open(HERE / "summary.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["split", "group", "value", "n_recordings", "tp", "fp", "fn", "precision", "recall", "f1",
                    "fp_per_10s", "mean_abs_timing_ms", "f1_bootstrap_2.5", "f1_bootstrap_97.5"])
        for split, rows in data.items():
            for kind, value, sel in groups(rows):
                g = pool(sel)
                lo, hi = bootstrap_f1(sel) if kind == "all" else ("", "")
                w.writerow([split, kind, value, g["n"], g["tp"], g["fp"], g["fn"], fmt(g["precision"]),
                            fmt(g["recall"]), fmt(g["f1"]), fmt(g["fp_per_10s"]), fmt(g["timing_ms"], 1),
                            fmt(lo) if lo != "" else "", fmt(hi) if hi != "" else ""])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    conds = [("OKN", "OKN"), ("FIXMOVE", "Dot + moving"), ("FIXSTILL", "Dot + still")]
    colors = {"development": "#9AA5B1", "evaluation": "#2F5D8A"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
    x = np.arange(len(conds))
    for i, split in enumerate(data):
        g = {c: pool([r for r in data[split] if r["condition"] == c]) for c, _ in conds}
        label = f"{split} ({len(data[split])} recordings)"
        f1 = [g[c]["f1"] if g[c]["f1"] is not None else 0 for c, _ in conds[:2]]
        bars = a1.bar(x[:2] + (i - 0.5) * 0.36, f1, 0.36, color=colors[split], label=label)
        a1.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
        bars = a2.bar(x + (i - 0.5) * 0.36, [g[c]["fp_per_10s"] for c, _ in conds], 0.36, color=colors[split], label=label)
        a2.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
    a1.set_xticks(x[:2], [n for _, n in conds[:2]])
    a1.set(ylim=(0, 1), ylabel="event F1 (pooled)", title="Reset detection")
    a2.set_xticks(x, [n for _, n in conds])
    a2.set(ylabel="false positives per 10 s", title="False detections")
    for ax in (a1, a2):
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Frozen SG + direction detector (22 deg/s): development vs one-time held-out", fontsize=10)
    fig.tight_layout()
    fig.savefig(HERE / "dev_vs_heldout.png", dpi=130)
    plt.close(fig)
    print(f"wrote {HERE / 'summary.csv'} and {HERE / 'dev_vs_heldout.png'}")


if __name__ == "__main__":
    main()
