#!/usr/bin/env python3
"""Classify the SG detector's errors on Pilot 03 DEVELOPMENT trials.

    python3 analysis/pilot_03/failure_cases.py --labels-dir <labels> --trials-dir <trials> \\
        [--threshold 24] [--output-dir analysis/pilot_03]

Never reads evaluation trials. Scoring is evaluate_okn.score_trial with
--artifacts exclude. For each missed label and each false positive it records
what the signal looked like, so the cause can be attributed:

- misses: SG peak |velocity| within ±tolerance of the label, the raw
  central-difference peak (what SG smoothing removed), whether the window is
  masked (blink/tracking), whether a prediction landed just outside the
  tolerance, and whether the peak runs against the stripes;
- false positives: direction relative to the stripes, whether a qualified slow
  phase leads into it (an OKN beat), peak velocity and duration in samples.

The expected reset direction is measured, not assumed: it is the dominant
direction of matched fast phases in development OKN trials for each stripe
direction. Writes failure_cases.csv (one row per error), failure_summary.csv
(counts by condition × cause) and failure_examples.png.
"""

import argparse
import collections
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import annotate_okn  # noqa: E402
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402

TOL = evaluate_okn.DEFAULT_TOLERANCE_S


def raw_velocity(t, angle, valid):
    """Central difference, NaN where either neighbour is invalid."""
    v = np.full_like(angle, np.nan)
    ok = valid[2:] & valid[:-2]
    v[1:-1][ok] = ((angle[2:] - angle[:-2]) / (t[2:] - t[:-2]))[ok]
    return v


def peak_near(t, v, x, tol=TOL):
    w = (t >= x - tol) & (t <= x + tol) & np.isfinite(v)
    if not w.any():
        return None, None
    i = np.flatnonzero(w)[np.argmax(np.abs(v[w]))]
    return float(v[i]), int(np.sign(v[i]))


def load(labels_dir, trials_dir, manifest, threshold):
    include = evaluate_okn.load_manifest(manifest, "development")
    reviews = {r["trial_id"]: r for r in annotate_okn._read_rows(Path(labels_dir) / "reviews.csv")}
    events = annotate_okn._read_rows(Path(labels_dir) / "events.csv")
    out = []
    for tid, row in sorted(include.items()):
        if reviews.get(tid, {}).get("status") != "complete":
            continue
        path = evaluate_okn.find_recording(tid, trials_dir, reviews[tid])
        data = detect_okn.load_session(path)
        r = detect_okn.analyse(data, detect_okn.Params(fast_threshold=threshold))
        evs = [(float(e["event_time_s"]), e["label"]) for e in events if e["trial_id"] == tid]
        out.append(dict(trial_id=tid, row=row, r=r, events=evs,
                        raw=raw_velocity(r["t"], r["angle"], r["valid"])))
    return out


def expected_reset_directions(trials):
    """{stripe direction: reset sign} from matched fast phases in OKN trials."""
    votes = collections.defaultdict(collections.Counter)
    for tr in trials:
        if tr["row"]["condition"] != "OKN":
            continue
        refs = [t for t, lab in tr["events"] if lab == "fast_phase"]
        starts = {f["start"]: f for f in tr["r"]["fast"]}
        pairs, _, _ = evaluate_okn.match_events(refs, list(starts), TOL)
        for _, p in pairs:
            votes[tr["row"]["direction"]][starts[p]["direction"]] += 1
    return {d: c.most_common(1)[0][0] for d, c in votes.items()}, votes


def classify(trials, expected, threshold):
    rows = []
    for tr in trials:
        r, row = tr["r"], tr["row"]
        t, vel, valid = r["t"], r["velocity"], r["valid"]
        exp = expected.get(row["direction"])
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        masked_labels = [x for x, lab in tr["events"] if lab != "fast_phase"]
        fast = {f["start"]: f for f in r["fast"]}
        pairs, missed, extra = evaluate_okn.match_events(refs, list(fast), TOL)
        extra = [p for p in extra if not any(abs(p - m) <= TOL for m in masked_labels)]
        beat_starts = {b["fast"]["start"] for b in r["beats"]}
        base = dict(trial_id=tr["trial_id"], participant=row["participant"], condition=row["condition"],
                    direction=row["direction"])
        for x in missed:
            sg_peak, sg_dir = peak_near(t, vel, x)
            raw_peak, _ = peak_near(t, tr["raw"], x)
            w = (t >= x - TOL) & (t <= x + TOL)
            near = min((abs(p - x) for p in fast), default=None)
            if sg_peak is None or (~valid[w]).mean() > 0.5:
                cause = "masked (blink/tracking)"
            elif near is not None and near <= 2 * TOL:
                cause = "detected 100-200 ms away"
            elif abs(sg_peak) <= threshold and raw_peak is not None and abs(raw_peak) > threshold:
                cause = "below threshold after SG smoothing"
            elif abs(sg_peak) <= threshold:
                cause = "small movement (below threshold even unsmoothed)"
            elif exp is not None and sg_dir != exp:
                cause = "peak against expected reset direction"
            else:
                cause = "above threshold but merged/split"
            rows.append(dict(base, kind="FN", time_s=f"{x:.3f}", cause=cause,
                             sg_peak=f"{abs(sg_peak):.1f}" if sg_peak is not None else "",
                             raw_peak=f"{abs(raw_peak):.1f}" if raw_peak is not None else "",
                             reset_direction_ok="" if exp is None or sg_dir is None else int(sg_dir == exp),
                             in_beat="", n_samples=""))
        for p in extra:
            f = fast[p]
            n = f["i1"] - f["i0"]
            direction_ok = None if exp is None else f["direction"] == exp
            in_beat = p in beat_starts
            edge = (~valid[max(f["i0"] - 6, 0):f["i1"] + 6]).any()       # within ~100 ms of masked data
            if exp is None:
                cause = "still stripes: saccade/noise" if in_beat or n > 1 else "still stripes: 1-sample spike"
            elif not direction_ok:
                cause = "against expected reset direction"
            elif not in_beat:
                cause = "right direction, no slow phase before it"
            else:
                cause = "right direction with slow phase (possible unlabelled reset)"
            if edge:
                cause += " [next to masked data]"
            rows.append(dict(base, kind="FP", time_s=f"{p:.3f}", cause=cause, sg_peak=f"{abs(f['peak_velocity']):.1f}",
                             raw_peak="", reset_direction_ok="" if direction_ok is None else int(direction_ok),
                             in_beat=int(in_beat), n_samples=n))
    return rows


def what_if(trials, expected, threshold):
    """Pooled counts if predictions were limited to (a) expected direction, (b) beats, (c) both."""
    out = {}
    for name in ("as is", "reset direction only", "beats only", "beats + reset direction"):
        tp = fp = fn = 0
        for tr in trials:
            r, exp = tr["r"], expected.get(tr["row"]["direction"])
            preds = r["fast"]
            if "direction" in name and exp is not None:
                preds = [f for f in preds if f["direction"] == exp]
            if "beats" in name:
                bs = {b["fast"]["start"] for b in r["beats"]}
                preds = [f for f in preds if f["start"] in bs]
            s = evaluate_okn.score_trial(tr["events"], [f["start"] for f in preds], TOL, artifacts="exclude")
            tp, fp, fn = tp + s["tp"], fp + s["fp"], fn + s["fn"]
        out[name] = (tp, fp, fn, *evaluate_okn.prf(tp, fp, fn))
    return out


def plot_examples(trials, rows, threshold, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    by_trial = {tr["trial_id"]: tr for tr in trials}

    def pick(cond, kind=None, has_tp=False):
        best = None
        for tr in trials:
            if tr["row"]["condition"] != cond:
                continue
            errs = [r for r in rows if r["trial_id"] == tr["trial_id"] and (kind is None or r["kind"] == kind)]
            score = len(errs) if kind else -len(errs)
            if best is None or score > best[0]:
                best = (score, tr["trial_id"])
        return best[1]

    panels = [("OKN: correct detections", pick("OKN")), ("OKN: most misses", pick("OKN", "FN")),
              ("Dot + moving: most misses", pick("FIXMOVE", "FN")),
              ("Dot + moving: most false positives", pick("FIXMOVE", "FP")),
              ("Dot + still: most false positives", pick("FIXSTILL", "FP"))]
    fig, axes = plt.subplots(len(panels), 1, figsize=(11, 2.6 * len(panels)), sharex=True)
    for ax, (title, tid) in zip(axes, panels):
        tr = by_trial[tid]
        r = tr["r"]
        t, ang = r["t"], np.where(r["valid"], r["angle"], np.nan)
        ax.plot(t, ang, color="0.3", lw=0.9)
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        pairs, missed, extra = evaluate_okn.match_events(refs, [f["start"] for f in r["fast"]], TOL)
        for x, p in pairs:
            ax.axvline(p, color="tab:green", lw=1.2)
        for x in missed:
            ax.axvline(x, color="tab:orange", lw=1.2, ls="--")
        for p in extra:
            ax.axvline(p, color="tab:red", lw=1.2, ls=":")
        ax.set_title(f"{title} — {tr['row']['participant']} T{int(tr['row']['trial_number']):03d} "
                     f"{tr['row']['condition']} {tr['row']['direction']}  (TP {len(pairs)}, FN {len(missed)}, "
                     f"FP {len(extra)})", fontsize=9, loc="left")
        ax.set_ylabel("eye angle (deg)")
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("time (s)")
    from matplotlib.lines import Line2D
    fig.legend([Line2D([], [], color="tab:green"), Line2D([], [], color="tab:orange", ls="--"),
                Line2D([], [], color="tab:red", ls=":")], ["detected (TP)", "missed label (FN)", "false positive"],
               loc="upper right", ncol=3, fontsize=8)
    fig.suptitle(f"SG detector at {threshold} deg/s, development trials only", x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent / "manifest.csv")
    ap.add_argument("--threshold", type=float, default=24)
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args(argv)
    thr = int(args.threshold) if args.threshold == int(args.threshold) else args.threshold
    trials = load(args.labels_dir, args.trials_dir, args.manifest, args.threshold)
    expected, votes = expected_reset_directions(trials)
    print(f"development trials: {len(trials)}; expected reset sign by stripe direction: {dict(expected)} "
          f"(votes {dict((k, dict(v)) for k, v in votes.items())})")
    rows = classify(trials, expected, args.threshold)
    fields = ["trial_id", "participant", "condition", "direction", "kind", "time_s", "cause", "sg_peak", "raw_peak",
              "reset_direction_ok", "in_beat", "n_samples"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with open(args.output_dir / "failure_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = collections.Counter((r["condition"], r["kind"], r["cause"]) for r in rows)
    with open(args.output_dir / "failure_summary.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["condition", "kind", "cause", "count"])
        for (cond, kind, cause), n in sorted(summary.items()):
            w.writerow([cond, kind, cause, n])
    print(f"\n{'condition':9} {'kind':4} {'count':>5}  cause")
    for (cond, kind, cause), n in sorted(summary.items()):
        print(f"{cond:9} {kind:4} {n:5d}  {cause}")
    print("\nwhat-if (diagnostic only, not a tuned detector):")
    for name, (tp, fp, fn, p, r, f1) in what_if(trials, expected, args.threshold).items():
        print(f"  {name:26} TP {tp:3d} FP {fp:3d} FN {fn:3d}  P {evaluate_okn.fmt(p)} R {evaluate_okn.fmt(r)} "
              f"F1 {evaluate_okn.fmt(f1)}")
    plot_examples(trials, rows, thr, args.output_dir / "failure_examples.png")
    print(f"\noutputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
