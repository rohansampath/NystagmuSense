#!/usr/bin/env python3
"""Exploratory trial-level OKN response analysis on Pilot 03 + Pilot 04 (no new data).

    python3 analysis/okn_response/analyze_response.py [--trials-dir trials]

Recordings: the primary recordings of analysis/pilot_03/manifest.csv (40) and
analysis/pilot_04/manifest.csv (60). Labels are not used: the targets are the
experimental CONDITIONS, which are a proxy for OKN presence, not independent
ground truth. Pilot 04 is no longer untouched (validation, then SG study), and
the 12 Pilot 03 held-out recordings were already scored once. Everything here
is exploratory; a rule chosen here needs a fresh cohort.

Primary comparison: OKN (positive) vs Dot + still (negative). Dot + moving is
analysed separately and never used as a negative.

Candidate trial-level rules (fixed before results):
  A  fast-phase rate      direction-consistent fast phases per 10 s of valid time
  B  slow-phase velocity  stimulus-aligned median slow-phase velocity (deg/s)
  C  slow consistency     share of slow-phase samples moving with the stimulus
  D  B and C              both above their own thresholds
Still trials are scored against their best-case hypothetical direction (see
response_metrics.py). A trial whose score is unavailable (too little valid
slow-phase data) counts as negative: no evidence of OKN.

Thresholds: leave-one-participant-out (P01, P02, P03; P01/P02 appear in both
pilots, so their folds hold out both pilots' recordings of that person). On
the two training participants, each rule's threshold is the training score
value that maximises balanced accuracy (ties: the median of the tied values);
D uses B's and C's thresholds chosen separately. ROC-AUC (Mann-Whitney) is
reported for the continuous scores, needing no threshold.

Writes trial_metrics.csv, condition_summary.csv, participant_summary.csv,
classification.csv, response_comparison.png and direction_consistency.png.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))
import annotate_okn  # noqa: E402
import detect_okn  # noqa: E402
import response_metrics as rm  # noqa: E402

MANIFESTS = {"P03": ROOT / "analysis/pilot_03/manifest.csv", "P04": ROOT / "analysis/pilot_04/manifest.csv"}
CONDITIONS = ("OKN", "FIXMOVE", "FIXSTILL")
SCORES = {"A": ("fast_rate_consistent", "fast-phase rate (per 10 s)"),
          "B": ("aligned_slow_median", "aligned slow-phase velocity (deg/s)"),
          "C": ("slow_consistency", "slow-phase direction consistency")}
PARTICIPANTS = ("P01", "P02", "P03")
ROBUST = detect_okn.Params(fast_threshold=40)        # fewer resets excluded: robustness to missed fast phases


def load(trials_dir):
    rows = []
    for pilot, path in MANIFESTS.items():
        for m in annotate_okn._read_rows(path):
            if m["eligibility"] != "primary":
                continue
            folder = Path(trials_dir) / m["trial_id"]
            meta = json.loads((folder / f"{m['trial_id']}.json").read_text())
            data = detect_okn.load_session(folder / f"{m['trial_id']}.csv")
            stim = meta["stimulus"]
            args = (stim.get("speedPointsPerSecond"), (meta.get("device") or {}).get("model"),
                    (meta.get("faceDistance") or {}).get("medianCm"))
            x = rm.trial_metrics(data, *args)
            robust = rm.trial_metrics(data, *args, exclusion_params=ROBUST)
            x.update(robust_aligned_slow_median=robust["aligned_slow_median"],
                     robust_slow_consistency=robust["slow_consistency"])
            rows.append(dict(trial_id=m["trial_id"], pilot=pilot, participant=m["participant"],
                             condition=m["condition"], direction=m["direction"],
                             pilot_split=m.get("split", ""), **x))
    return rows


def auc(pos, neg):
    """Mann-Whitney AUC; None if either side is empty. Unavailable scores rank lowest."""
    pos = [-np.inf if v is None else v for v in pos]
    neg = [-np.inf if v is None else v for v in neg]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def bootstrap_auc(pos, neg, n=2000, seed=20261112):
    rng = np.random.default_rng(seed)
    out = [auc(list(rng.choice(np.array(pos, dtype=object), len(pos))),
               list(rng.choice(np.array(neg, dtype=object), len(neg)))) for _ in range(n)]
    return tuple(np.percentile(out, [2.5, 97.5]))


def positive(v, thr):
    return v is not None and v >= thr


def best_threshold(pos, neg):
    """Training score value maximising balanced accuracy; ties → median of the tied values."""
    cands = sorted({v for v in pos + neg if v is not None})
    if not cands:
        return np.inf
    ba = lambda t: (np.mean([positive(v, t) for v in pos]) + np.mean([not positive(v, t) for v in neg])) / 2
    scores = [ba(t) for t in cands]
    tied = [t for t, s in zip(cands, scores) if s >= max(scores) - 1e-12]
    return float(np.median(tied))


def predict(rule, row, thr):
    if rule == "D":
        return positive(row[SCORES["B"][0]], thr["B"]) and positive(row[SCORES["C"][0]], thr["C"])
    return positive(row[SCORES[rule][0]], thr[rule])


def thresholds(train):
    pos = [r for r in train if r["condition"] == "OKN"]
    neg = [r for r in train if r["condition"] == "FIXSTILL"]
    return {k: best_threshold([r[c] for r in pos], [r[c] for r in neg]) for k, (c, _) in SCORES.items()}


def confusion(rows, rule, thr_of):
    tp = fn = tn = fp = 0
    for r in rows:
        hit = predict(rule, r, thr_of(r))
        if r["condition"] == "OKN":
            tp, fn = tp + hit, fn + (not hit)
        elif r["condition"] == "FIXSTILL":
            fp, tn = fp + hit, tn + (not hit)
    sens = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    bal = (sens + spec) / 2 if sens is not None and spec is not None else None
    return dict(tp=tp, fn=fn, tn=tn, fp=fp, sensitivity=sens, specificity=spec, balanced_accuracy=bal)


def fmt(v, d=3):
    return "" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def describe(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return dict(n=0, median="", q1="", q3="")
    q1, med, q3 = np.percentile(vals, [25, 50, 75])
    return dict(n=len(vals), median=f"{med:.3f}", q1=f"{q1:.3f}", q3=f"{q3:.3f}")


SUMMARY_METRICS = ["fast_rate_consistent", "fast_rate_all", "aligned_slow_median", "slow_consistency",
                   "reset_consistency", "slow_mean_abs", "slow_sd", "slow_fraction", "valid_fraction", "apparent_gain"]


def write_summary(path, rows, keys):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(list(keys) + ["metric", "n_trials", "n_available", "median", "q1", "q3"])
        groups = sorted({tuple(r[k] for k in keys) for r in rows})
        for g in groups:
            sel = [r for r in rows if tuple(r[k] for k in keys) == g]
            for m in SUMMARY_METRICS:
                d = describe([r[m] for r in sel])
                w.writerow(list(g) + [m, len(sel), d["n"], d["median"], d["q1"], d["q3"]])


def plots(rows, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"P01": "#4C72B0", "P02": "#55A868", "P03": "#C44E52"}
    markers = {"P03": "o", "P04": "s"}
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    names = {"OKN": "OKN", "FIXMOVE": "Dot + moving", "FIXSTILL": "Dot + still\n(best-case direction)"}
    for ax, (k, (col, label)) in zip(axes, SCORES.items()):
        for i, c in enumerate(CONDITIONS):
            sel = [r for r in rows if r["condition"] == c and r[col] is not None]
            for r in sel:
                ax.scatter(i + rng.uniform(-0.18, 0.18), r[col], s=16, color=colors[r["participant"]],
                           marker=markers[r["pilot"]], alpha=0.75, lw=0)
            if sel:
                ax.hlines(np.median([r[col] for r in sel]), i - 0.3, i + 0.3, color="k", lw=2)
        ax.set_xticks(range(3), [names[c] for c in CONDITIONS], fontsize=8)
        ax.set_title(f"{k}: {label}", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    axes[2].axhline(0.5, color="0.5", ls=":", lw=1)
    axes[1].axhline(0, color="0.5", ls=":", lw=1)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=colors[p], label=p) for p in PARTICIPANTS] + \
        [Line2D([], [], marker=markers[s], ls="", color="0.4", label=f"Pilot {s[1:]}") for s in markers]
    fig.legend(handles=handles, loc="upper right", ncol=5, fontsize=8)
    fig.suptitle("Trial-level response metrics, Pilot 03 + 04 primary recordings (exploratory; line = median)",
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out / "response_comparison.png", dpi=130)
    plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for i, (c, d) in enumerate([(c, d) for c in ("OKN", "FIXMOVE") for d in ("LEFT", "RIGHT")] + [("FIXSTILL", "NONE")]):
        sel = [r for r in rows if r["condition"] == c and r["direction"] == d and r["slow_median"] is not None]
        for r in sel:
            a1.scatter(i + rng.uniform(-0.18, 0.18), r["slow_median"], s=16, color=colors[r["participant"]],
                       marker=markers[r["pilot"]], alpha=0.75, lw=0)
        if sel:
            a1.hlines(np.median([r["slow_median"] for r in sel]), i - 0.3, i + 0.3, color="k", lw=2)
    a1.set_xticks(range(5), ["OKN\n← left", "OKN\nright →", "Dot+moving\n← left", "Dot+moving\nright →", "Dot + still"],
                  fontsize=8)
    a1.axhline(0, color="0.5", ls=":", lw=1)
    a1.set(ylabel="median slow-phase velocity, eye-angle sign (deg/s)",
           title="Slow-phase drift reverses with stimulus direction")
    for j, p in enumerate(PARTICIPANTS):
        for k, c in enumerate(("OKN", "FIXMOVE", "FIXSTILL")):
            vals = [r["slow_consistency"] for r in rows if r["participant"] == p and r["condition"] == c
                    and r["slow_consistency"] is not None]
            a2.scatter(np.full(len(vals), j * 4 + k) + rng.uniform(-0.15, 0.15, len(vals)), vals, s=14,
                       color=["#2F5D8A", "#E1A140", "#9AA5B1"][k], lw=0, alpha=0.8,
                       label=["OKN", "Dot + moving", "Dot + still (best case)"][k] if j == 0 else None)
    a2.axhline(0.5, color="0.5", ls=":", lw=1)
    a2.set_xticks([1, 5, 9], PARTICIPANTS)
    a2.set(ylabel="share of slow-phase samples with the stimulus", title="Slow-phase direction consistency")
    a2.legend(fontsize=8)
    for ax in (a1, a2):
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "direction_consistency.png", dpi=130)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--output-dir", type=Path, default=HERE)
    args = ap.parse_args(argv)
    out = args.output_dir
    rows = load(args.trials_dir)
    fields = list(rows[0])
    with open(out / "trial_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows({k: fmt(v) if isinstance(v, float) else v for k, v in r.items()} for r in rows)
    write_summary(out / "condition_summary.csv", rows, ("pilot", "condition"))
    write_summary(out / "participant_summary.csv", rows, ("participant", "condition"))

    moving = [r for r in rows if r["condition"] != "FIXSTILL" and r["slow_median"] is not None]
    sign_ok = lambda c: np.mean([np.sign(r["slow_median"]) == -r["stimulus_direction"] for r in moving
                                 if r["condition"] == c])
    print(f"sign check: slow drift opposite to the reset sign in {sign_ok('OKN'):.0%} of OKN, "
          f"{sign_ok('FIXMOVE'):.0%} of Dot + moving trials")

    pos = [r for r in rows if r["condition"] == "OKN"]
    neg = [r for r in rows if r["condition"] == "FIXSTILL"]
    lines = []
    for k, (col, label) in SCORES.items():
        a = auc([r[col] for r in pos], [r[col] for r in neg])
        lo, hi = bootstrap_auc([r[col] for r in pos], [r[col] for r in neg])
        per_p = {p: auc([r[col] for r in pos if r["participant"] == p], [r[col] for r in neg if r["participant"] == p])
                 for p in PARTICIPANTS}
        per_pilot = {s: auc([r[col] for r in pos if r["pilot"] == s], [r[col] for r in neg if r["pilot"] == s])
                     for s in MANIFESTS}
        lines.append(dict(kind="auc", rule=k, score=label, value=a, ci_low=lo, ci_high=hi,
                          **{f"auc_{p}": v for p, v in per_p.items()}, **{f"auc_pilot_{s}": v for s, v in per_pilot.items()}))
    for col, label in (("robust_aligned_slow_median", "B with resets from a 40 deg/s detector"),
                       ("robust_slow_consistency", "C with resets from a 40 deg/s detector")):
        lines.append(dict(kind="auc", rule="robustness", score=label, value=auc([r[col] for r in pos], [r[col] for r in neg])))
    good = lambda rs: [r for r in rs if r["valid_fraction"] >= 0.95]
    for k, (col, label) in SCORES.items():
        lines.append(dict(kind="auc", rule="tracking >= 95 %", score=label,
                          value=auc([r[col] for r in good(pos)], [r[col] for r in good(neg)])))

    fold_thr = {p: thresholds([r for r in rows if r["participant"] != p]) for p in PARTICIPANTS}
    all_thr = thresholds(rows)
    for rule in ("A", "B", "C", "D"):
        cv = confusion(rows, rule, lambda r: fold_thr[r["participant"]])
        groups = {f"cv_{p}": confusion([r for r in rows if r["participant"] == p], rule, lambda r: fold_thr[r["participant"]])
                  for p in PARTICIPANTS}
        groups.update({f"cv_pilot_{s}": confusion([r for r in rows if r["pilot"] == s], rule,
                                                  lambda r: fold_thr[r["participant"]]) for s in MANIFESTS})
        fixmove_cv = np.mean([predict(rule, r, fold_thr[r["participant"]]) for r in rows if r["condition"] == "FIXMOVE"])
        fixmove_all = np.mean([predict(rule, r, all_thr) for r in rows if r["condition"] == "FIXMOVE"])
        p01_still = [r for r in rows if r["participant"] == "P01" and r["condition"] == "FIXSTILL"]
        lines.append(dict(kind="rule", rule=rule, **{k: v for k, v in cv.items()},
                          fixmove_positive_rate_cv=float(fixmove_cv), fixmove_positive_rate_all=float(fixmove_all),
                          p01_still_false_positives_cv=sum(predict(rule, r, fold_thr["P01"]) for r in p01_still),
                          p01_still_n=len(p01_still),
                          thresholds_cv=json.dumps({p: {k: round(v, 3) for k, v in t.items()} for p, t in fold_thr.items()}),
                          thresholds_all=json.dumps({k: round(v, 3) for k, v in all_thr.items()}),
                          **{f"{g}_{m}": c[m] for g, c in groups.items() for m in ("sensitivity", "specificity")}))
    keys = sorted({k for l in lines for k in l}, key=lambda k: (k not in ("kind", "rule", "score"), k))
    with open(out / "classification.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows({k: fmt(v) if isinstance(v, float) else v for k, v in l.items()} for l in lines)
    plots(rows, out)
    for l in lines:
        if l["kind"] == "auc":
            print(f"AUC {l['rule']:<16} {l['score']:<45} {fmt(l['value'])}"
                  + (f" ({fmt(l['ci_low'])}-{fmt(l['ci_high'])})" if "ci_low" in l else ""))
        else:
            print(f"rule {l['rule']}: sens {fmt(l['sensitivity'])} spec {fmt(l['specificity'])} "
                  f"bal {fmt(l['balanced_accuracy'])}  TP {l['tp']} FN {l['fn']} TN {l['tn']} FP {l['fp']}  "
                  f"Dot+moving positive {l['fixmove_positive_rate_cv']:.2f}  P01 still FP {l['p01_still_false_positives_cv']}/{l['p01_still_n']}")
    print(f"outputs: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
