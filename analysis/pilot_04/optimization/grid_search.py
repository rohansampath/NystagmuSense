#!/usr/bin/env python3
"""Pilot 04 SG hyperparameter study (development only, after external validation).

    python3 analysis/pilot_04/optimization/grid_search.py --labels-dir analysis/annotations_p04 --annotator AA

Pilot 04 was first used, untouched, for the external validation in
../validation/ (commit c4389e3). This study reuses it as development data:
development_manifest.csv gives every primary recording the role
p04_development_after_validation (original_role external_validation). Nothing
here is independent test performance.

Detector: the frozen SG + direction detector with only three settings varied:
  fast-phase threshold 18, 20, 22, 24, 26, 28 deg/s
  SG window 5, 7 samples;  SG polynomial order 2, 3     (24 valid configs)
Direction check always on; every other detect_okn.Params value at its default.
Reference: threshold 22, window 5, order 2 (the frozen detector).

Scoring: evaluate_okn.score_manifest_trial, ±100 ms one-to-one,
--artifacts exclude, still stripes count false positives only. Pooled counts.

Selection rule (fixed before any grid result was seen), applied to a set of
"training" participants:
  1. eligible: still-stripe FP per 10 s no higher than the reference's on the
     same participants, OKN recall at least the reference's minus 0.02, and the
     worst participant's F1 at least the reference's worst minus 0.01;
  2. among eligible configs, highest pooled F1; ties within 0.01 → fewer
     still-stripe FP per 10 s → simpler (window 5 before 7, order 2 before 3)
     → threshold closest to 22;
  3. keep the reference unless the chosen config's F1 is more than 0.01 higher.
Grouped cross-validation: leave one participant out (3 folds). The rule picks a
config on two participants and both it and the reference are scored on the
third; outer results pool the three held-out participants. P01 and P02 are also
Pilot 03 participants, on whom the reference was developed, so only the P03 fold
is an unseen person for the reference. The final development configuration
applies the same rule to all 60 recordings.

Writes grid_search.csv, cross_validation.csv, best_configuration.json and
parameter_comparison.png in this folder.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import annotate_okn  # noqa: E402
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402
import okn_variants  # noqa: E402

THRESHOLDS = [18, 20, 22, 24, 26, 28]
WINDOWS = [5, 7]
ORDERS = [2, 3]
REFERENCE = (22, 5, 2)
TIE = 0.01
TOL = evaluate_okn.DEFAULT_TOLERANCE_S
PARTICIPANTS = ("P01", "P02", "P03")


def grid():
    return [(t, w, o) for w in WINDOWS for o in ORDERS for t in THRESHOLDS if o < w]


def development_manifest(validation_manifest, out):
    """New manifest: same recordings, role changed, history kept. The original is not touched."""
    rows = annotate_okn._read_rows(validation_manifest)
    fields = list(rows[0]) + ["original_role"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            primary = r["eligibility"] == "primary"
            w.writerow({**r, "original_role": r["role"],
                        "role": "p04_development_after_validation" if primary else r["role"],
                        "split": "development" if primary else r["split"]})


def predict(data, config):
    """Fast-phase starts of the SG + direction detector, as evaluate_okn's sg-direction, with SG settings."""
    threshold, window, order = config
    r = detect_okn.analyse(data, detect_okn.Params(fast_threshold=threshold, sg_window=window, sg_polyorder=order))
    displacement = data.get("stim_displacement_pt")
    if displacement is None or not all(math.isfinite(x) for x in displacement):
        raise ValueError("requires finite recorded stimulus displacement")
    direction = detect_okn.stimulus_direction(data)
    if direction == 0 and any(x != displacement[0] for x in displacement):
        raise ValueError("cannot score a reversing stimulus")
    return [f["start"] for f in okn_variants.direction_filter(r["fast"], okn_variants.expected_reset_direction(direction))]


def load_trials(manifest, labels_dir, trials_dir, annotator):
    include = evaluate_okn.load_manifest(manifest, "development")
    reviews = evaluate_okn.development_reviews(labels_dir, include, annotator)
    events = annotate_okn._read_rows(Path(labels_dir) / "events.csv")
    trials = []
    for tid, row in sorted(include.items()):
        review = reviews.get(tid)
        if review is None or review["status"] != "complete":
            raise SystemExit(f"{tid}: no complete {annotator} review")
        path = evaluate_okn.find_recording(tid, trials_dir, review)
        if path is None:
            raise SystemExit(f"{tid}: recording not found")
        data = detect_okn.load_session(path)
        trials.append(dict(trial_id=tid, row=row, data=data, duration=float(data["t_s"][-1] - data["t_s"][0]),
                           events=evaluate_okn.review_events(events, review)))
    return trials


def score(trials, config):
    out = []
    for tr in trials:
        s = evaluate_okn.score_manifest_trial(tr["events"], predict(tr["data"], config), tr["row"]["condition"],
                                              TOL, artifacts="exclude")
        s.update(trial_id=tr["trial_id"], participant=tr["row"]["participant"], condition=tr["row"]["condition"],
                 duration_s=tr["duration"])
        out.append(s)
    return out


def summary(scored):
    """Overall, OKN, still-stripe and per-participant numbers for one config."""
    sel = lambda f: [s for s in scored if f(s)]
    g = evaluate_okn.summarize(scored)
    okn = evaluate_okn.summarize(sel(lambda s: s["condition"] == "OKN"))
    still = evaluate_okn.summarize(sel(lambda s: s["condition"] == "FIXSTILL"))
    move = evaluate_okn.summarize(sel(lambda s: s["condition"] == "FIXMOVE"))
    parts = {p: evaluate_okn.summarize(sel(lambda s, p=p: s["participant"] == p))
             for p in sorted({s["participant"] for s in scored})}
    return dict(all=g, okn=okn, fixmove=move, still=still, participants=parts,
                worst_f1=min((v["f1"] or 0) for v in parts.values()))


def choose(summaries):
    """The documented rule on {config: summary}; returns (config, reason)."""
    ref = summaries[REFERENCE]
    eligible = {c: s for c, s in summaries.items()
                if s["still"]["fp_per_10s"] <= ref["still"]["fp_per_10s"] + 1e-9
                and (s["okn"]["recall"] or 0) >= (ref["okn"]["recall"] or 0) - 0.02
                and s["worst_f1"] >= ref["worst_f1"] - 0.01}
    best = max((s["all"]["f1"] or 0) for s in eligible.values())
    tied = [c for c, s in eligible.items() if (s["all"]["f1"] or 0) >= best - TIE]
    pick = min(tied, key=lambda c: (eligible[c]["still"]["fp_per_10s"], c[1], c[2], abs(c[0] - 22), c[0]))
    if (eligible[pick]["all"]["f1"] or 0) <= (ref["all"]["f1"] or 0) + TIE:
        return REFERENCE, "no eligible config beats the reference by more than 0.01 F1"
    return pick, "best eligible config"


def name(c):
    return f"{c[0]} deg/s, window {c[1]}, order {c[2]}"


def fmt(v, d=3):
    return "" if v is None else f"{v:.{d}f}"


def plot(summaries, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    for w, o in [(w, o) for w in WINDOWS for o in ORDERS if o < w]:
        cs = [(t, w, o) for t in THRESHOLDS]
        style = dict(marker="o", ms=4, lw=1.4 if (w, o) == (5, 2) else 1, ls="-" if o == 2 else "--")
        a1.plot(THRESHOLDS, [summaries[c]["all"]["f1"] for c in cs], label=f"window {w}, order {o}", **style)
        a2.plot(THRESHOLDS, [summaries[c]["still"]["fp_per_10s"] for c in cs], label=f"window {w}, order {o}", **style)
    for ax in (a1, a2):
        ax.axvline(22, color="0.5", lw=0.8, ls=":")
        ax.grid(alpha=0.3)
        ax.set_xlabel("fast-phase threshold (deg/s)")
        ax.legend(fontsize=8)
    a1.set(ylabel="pooled F1 (all 60, development)", title="Event F1")
    a2.set(ylabel="still-stripe false positives per 10 s", title="Still-stripe controls")
    fig.suptitle("Pilot 04 SG grid (development after validation; not independent test performance)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--annotator", required=True)
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--validation-manifest", type=Path, default=HERE.parent / "manifest.csv")
    args = ap.parse_args(argv)
    manifest = HERE / "development_manifest.csv"
    development_manifest(args.validation_manifest, manifest)
    trials = load_trials(manifest, args.labels_dir, args.trials_dir, args.annotator)
    scored = {c: score(trials, c) for c in grid()}
    full = {c: summary(s) for c, s in scored.items()}

    with open(HERE / "grid_search.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["threshold", "sg_window", "sg_polyorder", "tp", "fp", "fn", "precision", "recall", "f1",
                    "fp_per_10s", "okn_recall", "okn_f1", "fixmove_f1", "still_fp_per_10s",
                    "f1_P01", "f1_P02", "f1_P03", "mean_abs_timing_ms"])
        for c, s in full.items():
            g = s["all"]
            w.writerow([*c, g["tp"], g["fp"], g["fn"], fmt(g["precision"]), fmt(g["recall"]), fmt(g["f1"]),
                        fmt(g["fp_per_10s"]), fmt(s["okn"]["recall"]), fmt(s["okn"]["f1"]), fmt(s["fixmove"]["f1"]),
                        fmt(s["still"]["fp_per_10s"]), *(fmt(s["participants"][p]["f1"]) for p in PARTICIPANTS),
                        fmt(g["mean_abs_offset_ms"], 1)])

    folds, outer_ref, outer_pick = [], [], []
    for held in PARTICIPANTS:
        train = {c: summary([x for x in s if x["participant"] != held]) for c, s in scored.items()}
        pick, reason = choose(train)
        test = lambda c: [x for x in scored[c] if x["participant"] == held]
        outer_ref += test(REFERENCE)
        outer_pick += test(pick)
        r, p = evaluate_okn.summarize(test(REFERENCE)), evaluate_okn.summarize(test(pick))
        folds.append((held, pick, reason, r, p))
    with open(HERE / "cross_validation.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["held_out", "chosen_on_other_two", "reason", "detector", "tp", "fp", "fn", "precision", "recall",
                    "f1", "fp_per_10s"])
        for held, pick, reason, r, p in folds:
            for label, c, g in (("reference", REFERENCE, r), ("chosen", pick, p)):
                w.writerow([held, name(pick), reason, f"{label}: {name(c)}", g["tp"], g["fp"], g["fn"],
                            fmt(g["precision"]), fmt(g["recall"]), fmt(g["f1"]), fmt(g["fp_per_10s"])])
        for label, rows in (("reference", outer_ref), ("chosen", outer_pick)):
            g = evaluate_okn.summarize(rows)
            w.writerow(["pooled", "", "", label, g["tp"], g["fp"], g["fn"], fmt(g["precision"]), fmt(g["recall"]),
                        fmt(g["f1"]), fmt(g["fp_per_10s"])])

    best, reason = choose(full)
    b, r = full[best], full[REFERENCE]
    pack = lambda s: dict(precision=s["all"]["precision"], recall=s["all"]["recall"], f1=s["all"]["f1"],
                          tp=s["all"]["tp"], fp=s["all"]["fp"], fn=s["all"]["fn"], fp_per_10s=s["all"]["fp_per_10s"],
                          okn_recall=s["okn"]["recall"], still_fp_per_10s=s["still"]["fp_per_10s"],
                          f1_by_participant={p: s["participants"][p]["f1"] for p in PARTICIPANTS})
    (HERE / "best_configuration.json").write_text(json.dumps(dict(
        status="development only (Pilot 04 reused after its external validation); not independent test performance",
        selection_reason=reason,
        configuration=dict(fast_threshold_deg_s=best[0], sg_window=best[1], sg_polyorder=best[2],
                           direction_check=True, other_params="detect_okn.Params defaults"),
        reference=dict(fast_threshold_deg_s=REFERENCE[0], sg_window=REFERENCE[1], sg_polyorder=REFERENCE[2]),
        development_all_60=dict(chosen=pack(b), reference=pack(r)),
        cross_validation=[dict(held_out=h, chosen=name(p)) for h, p, *_ in folds],
    ), indent=2) + "\n")
    plot(full, HERE / "parameter_comparison.png")
    print(f"reference {name(REFERENCE)}: F1 {fmt(r['all']['f1'])} (should equal the validation run)")
    print(f"development choice on all 60: {name(best)} — {reason}")
    for held, pick, reason, rr, pp in folds:
        print(f"  hold out {held}: chosen {name(pick)}; held-out F1 reference {fmt(rr['f1'])}, chosen {fmt(pp['f1'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
