#!/usr/bin/env python3
"""Tables and figure for the Pilot 04 external validation (no detector is run).

    python3 analysis/pilot_04/validation/summarize.py

Reads validation_results.csv (the one-time run of the frozen Pilot 03 SG +
direction detector) and writes validation_by_participant.csv,
validation_by_condition.csv and validation_overview.png. Pooled TP/FP/FN;
still stripes report false positives only. The bootstrap resamples whole
recordings (seed 20261111) as a rough interval.
"""

import csv
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
STATUS = {"P01": "returning", "P02": "returning", "P03": "new"}
FIELDS = ["group", "value", "n_recordings", "tp", "fp", "fn", "precision", "recall", "f1", "fp_per_10s",
          "mean_abs_timing_ms", "f1_bootstrap_2.5", "f1_bootstrap_97.5"]


def pool(rows):
    tp, fp, fn = (sum(int(r[k]) for r in rows) for k in ("tp", "fp", "fn"))
    seconds = sum(float(r["duration_s"]) for r in rows)
    weighted = sum(float(r["mean_abs_offset_ms"]) * int(r["tp"]) for r in rows if r["mean_abs_offset_ms"])
    return dict(n=len(rows), tp=tp, fp=fp, fn=fn, precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None, f1=2 * tp / (2 * tp + fp + fn) if tp + fn else None,
                fp_per_10s=10 * fp / seconds, timing_ms=weighted / tp if tp else None)


def bootstrap_f1(rows, n=5000, seed=20261111):
    counts = np.array([[int(r["tp"]), int(r["fp"]), int(r["fn"])] for r in rows])
    if not counts[:, [0, 2]].sum():
        return None, None
    rng = np.random.default_rng(seed)
    f1 = []
    for _ in range(n):
        tp, fp, fn = counts[rng.integers(0, len(counts), len(counts))].sum(0)
        if tp + fn:
            f1.append(2 * tp / (2 * tp + fp + fn))
    return tuple(np.percentile(f1, [2.5, 97.5]))


def fmt(v, d=3):
    return "" if v is None else f"{v:.{d}f}"


def row(kind, value, rows):
    g = pool(rows)
    lo, hi = bootstrap_f1(rows)
    return [kind, value, g["n"], g["tp"], g["fp"], g["fn"], fmt(g["precision"]), fmt(g["recall"]), fmt(g["f1"]),
            fmt(g["fp_per_10s"]), fmt(g["timing_ms"], 1), fmt(lo), fmt(hi)]


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        w.writerows(rows)


def main():
    data = list(csv.DictReader(open(HERE / "validation_results.csv")))
    for r in data:
        r["status"] = STATUS[r["participant"]]
    by = lambda key, value: [r for r in data if r[key] == value]
    moving = [r for r in data if r["condition"] != "FIXSTILL"]
    part = [row("all", "all", data), row("all", "moving stripes only", moving)]
    part += [row("participant", p, by("participant", p)) for p in sorted(STATUS)]
    part += [row("participant status", s, by("status", s)) for s in ("returning", "new")]
    part += [row("participant x condition", f"{p} {c}", [r for r in by("participant", p) if r["condition"] == c])
             for p in sorted(STATUS) for c in ("OKN", "FIXMOVE", "FIXSTILL")]
    write(HERE / "validation_by_participant.csv", part)
    cond = [row("condition", c, by("condition", c)) for c in ("OKN", "FIXMOVE", "FIXSTILL")]
    cond += [row("direction", d, by("direction", d)) for d in ("LEFT", "RIGHT", "NONE")]
    cond += [row("condition x direction", f"{c} {d}", [r for r in by("condition", c) if r["direction"] == d])
             for c in ("OKN", "FIXMOVE") for d in ("LEFT", "RIGHT")]
    write(HERE / "validation_by_condition.csv", cond)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    conds = [("OKN", "OKN"), ("FIXMOVE", "Dot + moving"), ("FIXSTILL", "Dot + still")]
    colors = {"P01": "#4C72B0", "P02": "#55A868", "P03": "#C44E52"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4))
    x = np.arange(len(conds))
    for i, p in enumerate(sorted(STATUS)):
        g = {c: pool([r for r in by("participant", p) if r["condition"] == c]) for c, _ in conds}
        label = f"{p} ({STATUS[p]})"
        bars = a1.bar(x[:2] + (i - 1) * 0.26, [g[c]["f1"] or 0 for c, _ in conds[:2]], 0.26, color=colors[p], label=label)
        a1.bar_label(bars, fmt="%.2f", fontsize=7, padding=2)
        bars = a2.bar(x + (i - 1) * 0.26, [g[c]["fp_per_10s"] for c, _ in conds], 0.26, color=colors[p], label=label)
        a2.bar_label(bars, fmt="%.1f", fontsize=7, padding=2)
    a1.set_xticks(x[:2], [n for _, n in conds[:2]])
    a1.set(ylim=(0, 1), ylabel="event F1 (pooled)", title="Reset detection")
    a2.set_xticks(x, [n for _, n in conds])
    a2.set(ylabel="false positives per 10 s", title="False detections")
    for ax in (a1, a2):
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Pilot 04 external validation — frozen Pilot 03 SG detector (22 deg/s), 60 recordings", fontsize=10)
    fig.tight_layout()
    fig.savefig(HERE / "validation_overview.png", dpi=130)
    plt.close(fig)
    print(f"wrote validation_by_participant.csv, validation_by_condition.csv, validation_overview.png in {HERE}")


if __name__ == "__main__":
    main()
