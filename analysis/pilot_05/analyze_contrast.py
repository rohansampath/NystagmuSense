#!/usr/bin/env python3
"""Pilot 05: OKN response vs nominal contrast (runs only on real recordings).

    python3 analysis/pilot_05/analyze_contrast.py [--trials-dir trials] [--output-dir analysis/pilot_05/results]

Reads the primary recordings of analysis/pilot_05/manifest.csv and computes,
per trial, the response metrics of analysis/okn_response/response_metrics.py.
Those use the frozen SG detector, unchanged. Every metric is relative to the
trial's INTENDED stimulus direction, taken from stim_displacement_pt, which
moves at every contrast including 0 %. So a 0 % trial is scored like any
other trial and is never treated as a still-stripe control.

No thresholds, psychometric fits or contrast-sensitivity estimates. Contrasts
are nominal (docs/PILOT_05.md).

Feasibility criteria (fixed before any Pilot 05 data; reported, not tuned):
  1  high-contrast response: per participant, median aligned slow-phase
     velocity > 0 and median direction consistency > 0.5 at 40 % and 80 %
  2  weak 0 % response: per participant, median aligned velocity at 0 % is
     below 25 % of the median at 80 %
  3  rising with contrast: per participant, Spearman rho between nominal
     contrast and aligned velocity > 0 (reported with its value)
  4  direction reversal: at 20 % and above, the signed slow-phase median has
     the expected sign for its direction in >= 90 % of trials
  5  repeatability: within-cell spread (|rep1 - rep2|) vs the range of cell
     medians across contrast, per participant (reported)
  6  tracking: Spearman rho between valid-tracking fraction and aligned
     velocity within each contrast level (reported; |rho| near 0 is reassuring)

Writes trial_metrics.csv, contrast_summary.csv, criteria.csv,
response_vs_contrast.png and consistency_vs_contrast.png.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analysis" / "okn_response"))
sys.path.insert(0, str(HERE))
import annotate_okn  # noqa: E402
import contrast_model  # noqa: E402
import detect_okn  # noqa: E402
import response_metrics as rm  # noqa: E402

DIRECTION_SIGN = {"RIGHT": 1, "LEFT": -1}


def load(manifest, trials_dir):
    rows = [m for m in annotate_okn._read_rows(manifest) if m["eligibility"] == "primary"]
    if not rows:
        raise SystemExit(f"no primary Pilot 05 recordings in {manifest}; nothing to analyse")
    out = []
    for m in rows:
        folder = Path(trials_dir) / m["trial_id"]
        csv_path, json_path = folder / f"{m['trial_id']}.csv", folder / f"{m['trial_id']}.json"
        if not csv_path.exists() or not json_path.exists():
            raise SystemExit(f"{m['trial_id']}: recording not found in {trials_dir}")
        meta = json.loads(json_path.read_text())
        data = detect_okn.load_session(csv_path)
        intended = detect_okn.stimulus_direction(data)
        if intended != DIRECTION_SIGN[m["direction"]]:
            raise SystemExit(f"{m['trial_id']}: recorded stimulus motion disagrees with direction {m['direction']}")
        x = rm.trial_metrics(data, meta["stimulus"].get("speedPointsPerSecond"),
                             (meta.get("device") or {}).get("model"), (meta.get("faceDistance") or {}).get("medianCm"))
        out.append(dict(trial_id=m["trial_id"], participant=m["participant"], contrast_percent=int(m["contrast_percent"]),
                        direction=m["direction"], valid_s=x["valid_s"], valid_fraction=x["valid_fraction"],
                        fast_rate_consistent=x["fast_rate_consistent"], aligned_slow_median=x["aligned_slow_median"],
                        slow_median=x["slow_median"], slow_consistency=x["slow_consistency"],
                        reset_consistency=x["reset_consistency"], slow_available=x["slow_available"],
                        stimulus_deg_s=x["stimulus_deg_s"], apparent_gain_uncalibrated=x["apparent_gain"]))
    return out


def rho(pairs):
    """Spearman rho, or None when undefined (under 3 pairs or a constant variable)."""
    if len(pairs) < 3 or any(len(set(v)) < 2 for v in zip(*pairs)):
        return None
    return float(spearmanr(*zip(*pairs)).statistic)


def med(values):
    vals = [v for v in values if v is not None]
    return float(np.median(vals)) if vals else None


def criteria(rows):
    out = []
    people = sorted({r["participant"] for r in rows})
    cell = lambda p, c, k: [r[k] for r in rows if r["participant"] == p and r["contrast_percent"] == c]
    for p in people:
        high = [(c, med(cell(p, c, "aligned_slow_median")), med(cell(p, c, "slow_consistency"))) for c in (40, 80)]
        ok1 = all(v is not None and v > 0 and k is not None and k > 0.5 for _, v, k in high)
        out.append(dict(criterion="1 high-contrast response", participant=p, met=ok1,
                        value="; ".join(f"{c}%: v={v} C={k}" for c, v, k in high)))
        v0, v80 = med(cell(p, 0, "aligned_slow_median")), med(cell(p, 80, "aligned_slow_median"))
        ok2 = v0 is not None and v80 is not None and v80 > 0 and v0 < 0.25 * v80
        out.append(dict(criterion="2 weak 0 % response", participant=p, met=ok2, value=f"0%: {v0}; 80%: {v80}"))
        pairs = [(r["contrast_percent"], r["aligned_slow_median"]) for r in rows
                 if r["participant"] == p and r["aligned_slow_median"] is not None]
        r3 = rho(pairs)
        out.append(dict(criterion="3 rising with contrast", participant=p,
                        met=r3 is not None and r3 > 0, value=f"Spearman rho {r3}"))
        spreads = []
        for c in contrast_model.LEVELS:
            for d in DIRECTION_SIGN:
                v = [r["aligned_slow_median"] for r in rows if r["participant"] == p and r["contrast_percent"] == c
                     and r["direction"] == d and r["aligned_slow_median"] is not None]
                if len(v) == 2:
                    spreads.append(abs(v[0] - v[1]))
        meds = [m for m in (med(cell(p, c, "aligned_slow_median")) for c in contrast_model.LEVELS) if m is not None]
        out.append(dict(criterion="5 repeatability", participant=p, met="",
                        value=f"median |rep1-rep2| {med(spreads)}; range of contrast medians "
                              f"{(max(meds) - min(meds)) if meds else None}"))
    strong = [r for r in rows if r["contrast_percent"] >= 20]
    # Unavailable responses provide no evidence of direction reversal; keep
    # them in the denominator instead of inflating success by dropping them.
    share = np.mean([r["slow_median"] is not None and
                     np.sign(r["slow_median"]) == -DIRECTION_SIGN[r["direction"]] for r in strong]) if strong else None
    out.append(dict(criterion="4 direction reversal (>= 20 %)", participant="all",
                    met=share is not None and share >= 0.9, value=f"{share} of {len(strong)} trials"))
    for c in contrast_model.LEVELS:
        sel = [(r["valid_fraction"], r["aligned_slow_median"]) for r in rows
               if r["contrast_percent"] == c and r["aligned_slow_median"] is not None]
        out.append(dict(criterion="6 tracking vs response", participant=f"C{c:03d}", met="",
                        value=f"Spearman rho {rho(sel)}"))
    return out


def plot(rows, key, ylabel, path, chance=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    people = sorted({r["participant"] for r in rows})
    colors = dict(zip(people, ["#4C72B0", "#55A868", "#C44E52"]))
    x_of = {c: i for i, c in enumerate(contrast_model.LEVELS)}
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for j, p in enumerate(people):
        off = (j - (len(people) - 1) / 2) * 0.12
        for d, marker in (("LEFT", "<"), ("RIGHT", ">")):
            sel = [r for r in rows if r["participant"] == p and r["direction"] == d and r[key] is not None]
            ax.scatter([x_of[r["contrast_percent"]] + off for r in sel], [r[key] for r in sel], marker=marker,
                       s=28, color=colors[p], alpha=0.8, lw=0)
        meds = [(x_of[c] + off, med([r[key] for r in rows if r["participant"] == p and r["contrast_percent"] == c]))
                for c in contrast_model.LEVELS]
        meds = [(x, m) for x, m in meds if m is not None]
        if meds:
            ax.plot(*zip(*meds), "-", color=colors[p], lw=1.2, label=f"{p} median")
    if chance is not None:
        ax.axhline(chance, color="0.5", ls=":", lw=1)
    ax.set_xticks(range(len(contrast_model.LEVELS)), [f"{c}" for c in contrast_model.LEVELS])
    ax.set(xlabel="nominal Michelson contrast (%) — not photometrically measured", ylabel=ylabel)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, title="◀ left  ▶ right trials", title_fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fmt(v):
    return "" if v is None else (f"{v:.4f}" if isinstance(v, float) else v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, default=HERE / "manifest.csv")
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--output-dir", type=Path, default=HERE / "results")
    args = ap.parse_args(argv)
    if not args.manifest.exists():
        raise SystemExit(f"{args.manifest} does not exist; build it with analysis/pilot_05/build_manifest.py")
    rows = load(args.manifest, args.trials_dir)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "trial_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({k: fmt(v) for k, v in r.items()} for r in rows)
    with open(out / "contrast_summary.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["participant", "contrast_percent", "n", "median_aligned_slow_velocity", "median_slow_consistency",
                    "median_fast_rate_consistent", "values_aligned_slow_velocity"])
        for p in sorted({r["participant"] for r in rows}):
            for c in contrast_model.LEVELS:
                sel = [r for r in rows if r["participant"] == p and r["contrast_percent"] == c]
                w.writerow([p, c, len(sel), fmt(med([r["aligned_slow_median"] for r in sel])),
                            fmt(med([r["slow_consistency"] for r in sel])),
                            fmt(med([r["fast_rate_consistent"] for r in sel])),
                            " ".join(fmt(r["aligned_slow_median"]) for r in sel)])
    crit = criteria(rows)
    with open(out / "criteria.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["criterion", "participant", "met", "value"], lineterminator="\n")
        w.writeheader()
        w.writerows(crit)
    plot(rows, "aligned_slow_median", "aligned median slow-phase velocity (deg/s)", out / "response_vs_contrast.png", 0)
    plot(rows, "slow_consistency", "slow-phase direction consistency", out / "consistency_vs_contrast.png", 0.5)
    for c in crit:
        print(f"{c['criterion']:32} {c['participant']:6} {str(c['met']):6} {c['value']}")
    print(f"{len(rows)} recordings analysed; outputs in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
