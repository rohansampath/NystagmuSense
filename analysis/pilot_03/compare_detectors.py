#!/usr/bin/env python3
"""Development-only comparison of OKN reset detectors on Pilot 03.

    python3 analysis/pilot_03/compare_detectors.py --labels-dir <labels> --trials-dir <trials> \\
        [--output-dir analysis/pilot_03/comparison]

Every method is scored on the same 28 primary development recordings with
evaluate_okn.score_trial (±100 ms one-to-one, artifacts excluded). The held-out
evaluation split is never loaded.

Methods (scripts/okn_variants.py; detect_okn.py is unchanged):
  A  SG, 40 deg/s (original)
  B  SG, threshold tuned
  C  SG + direction check, threshold re-tuned
  D  standalone local piecewise-linear steps + direction check
  E  permissive SG + direction check + local linear validation
plus ablations (SG + linear without direction, D without direction) and the
existing global-segmentation detector (hybrid_okn.py) at its defaults.

Each tuned method has a small grid. Choice rule (same as the threshold sweep):
highest pooled F1, ties within 0.01 → fewer FP per 10 s → the more conservative
setting (higher threshold / amplitude). Overfitting check: choose on one
participant's development trials, score on the other's, both ways; the pooled
result is reported as "cross-participant".
"""

import argparse
import collections
import csv
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import annotate_okn  # noqa: E402
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402
import hybrid_okn  # noqa: E402
import okn_variants as ov  # noqa: E402

TOL = evaluate_okn.DEFAULT_TOLERANCE_S
SG_THRESHOLDS = list(range(10, 41, 2))
PERMISSIVE = list(range(10, 25, 2))
AMPLITUDES = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]
IMPROVEMENTS = [0.3, 0.5, 0.7, 0.85, 0.9, 0.95]
TIE = 0.01


def load_trials(labels_dir, trials_dir, manifest, annotator=None):
    include = evaluate_okn.load_manifest(manifest, "development")
    reviews = evaluate_okn.development_reviews(labels_dir, include, annotator)
    events = annotate_okn._read_rows(Path(labels_dir) / "events.csv")
    trials = []
    for tid, row in sorted(include.items()):
        if reviews.get(tid, {}).get("status") != "complete":
            raise SystemExit(f"{tid} is not completely reviewed")
        path = evaluate_okn.find_recording(tid, trials_dir, reviews[tid])
        if path is None:
            raise ValueError(f"{tid}: recording not found")
        data = detect_okn.load_session(path)
        t = data["t_s"]
        trials.append(dict(trial_id=tid, row=row, data=data, duration=float(t[-1] - t[0]),
                           events=evaluate_okn.review_events(events, reviews[tid]),
                           expected=ov.expected_reset_direction(detect_okn.stimulus_direction(data))))
    return trials


def score(trials, predictions):
    """predictions: {trial_id: [start times]} → per-trial score dicts with grouping keys."""
    out = []
    for tr in trials:
        s = evaluate_okn.score_trial(tr["events"], predictions[tr["trial_id"]], TOL, artifacts="exclude")
        s.update(trial_id=tr["trial_id"], duration_s=tr["duration"], participant=tr["row"]["participant"],
                 condition=tr["row"]["condition"], direction=tr["row"]["direction"], mode="")
        out.append(s)
    return out


def pooled(scored):
    return evaluate_okn.summarize(scored)


def choose(configs, key_conservative):
    """configs: {config: summary}. Best by F1, ties → fewer FP/10 s → more conservative."""
    best = max((g["f1"] or 0) for g in configs.values())
    tied = [c for c, g in configs.items() if (g["f1"] or 0) >= best - TIE]
    neg = lambda k: tuple(-x for x in k) if isinstance(k, tuple) else (-k,)
    return min(tied, key=lambda c: (configs[c]["fp_per_10s"] or 0, neg(key_conservative(c))))


# ------------------------------------------------------------------ methods

class Cache:
    """Detector outputs computed once per trial and setting."""

    def __init__(self, trials):
        self.trials = trials
        self.sg, self.steps, self.scan = {}, {}, {}

    def analyse(self, tr, thr):
        k = (tr["trial_id"], thr)
        if k not in self.sg:
            self.sg[k] = detect_okn.analyse(tr["data"], detect_okn.Params(fast_threshold=thr))
        return self.sg[k]

    def step_features(self, tr, thr):
        k = (tr["trial_id"], thr)
        if k not in self.steps:
            r = self.analyse(tr, thr)
            loose = ov.StepParams(min_amplitude_deg=0, min_improvement=-np.inf, max_side_rms=np.inf)
            self.steps[k] = list(zip(r["fast"], ov.step_features(r, r["fast"], loose)))
        return self.steps[k]

    def standalone(self, tr):
        """Per-sample best steps with gates off; gates and thinning are applied per config."""
        if tr["trial_id"] not in self.scan:
            r = self.analyse(tr, 40)
            loose = ov.StepParams(min_amplitude_deg=0, min_improvement=-np.inf, max_side_rms=np.inf,
                                  min_mean_speed=0, min_separation_s=0)
            self.scan[tr["trial_id"]] = ov.piecewise_resets(r, loose)
        return self.scan[tr["trial_id"]]


def sg_predict(cache, thr, direction):
    out = {}
    for tr in cache.trials:
        fast = cache.analyse(tr, thr)["fast"]
        out[tr["trial_id"]] = [f["start"] for f in (ov.direction_filter(fast, tr["expected"]) if direction else fast)]
    return out


def hybrid_predict(cache, thr, amp, direction, improvement=0.5):
    p = ov.StepParams(min_amplitude_deg=amp, min_improvement=improvement)
    out = {}
    for tr in cache.trials:
        keep = []
        for f, s in cache.step_features(tr, thr):
            if direction and tr["expected"] and f["direction"] != tr["expected"]:
                continue
            if ov.plausible(s, p) and s["direction"] == f["direction"]:
                keep.append(f["start"])
        out[tr["trial_id"]] = keep
    return out


def standalone_predict(cache, amp, improvement, direction):
    p = ov.StepParams(min_amplitude_deg=amp, min_improvement=improvement)
    out = {}
    for tr in cache.trials:
        cands = [c for c in cache.standalone(tr) if ov.plausible(c, p)
                 and abs(c["amplitude"]) / c["duration"] >= p.min_mean_speed
                 and not (direction and tr["expected"] and c["direction"] != tr["expected"])]
        kept = []
        for c in sorted(cands, key=lambda c: -c["score"]):
            if all(abs(c["start"] - k) >= p.min_separation_s for k in kept):
                kept.append(c["start"])
        out[tr["trial_id"]] = sorted(kept)
    return out


def global_segmentation_predict(cache, direction):
    out = {}
    for tr in cache.trials:
        fast = hybrid_okn.analyse(tr["data"], detect_okn.Params())["fast"]
        out[tr["trial_id"]] = [f["start"] for f in (ov.direction_filter(fast, tr["expected"]) if direction else fast)]
    return out


def methods(cache):
    """name → (description, {config: predict()}, conservative key, fixed?)"""
    sg = lambda d: {thr: (lambda thr=thr: sg_predict(cache, thr, d)) for thr in SG_THRESHOLDS}
    hyb = lambda d: {(thr, amp): (lambda thr=thr, amp=amp: hybrid_predict(cache, thr, amp, d))
                     for thr in PERMISSIVE for amp in AMPLITUDES}
    pl = lambda d: {(amp, imp): (lambda amp=amp, imp=imp: standalone_predict(cache, amp, imp, d))
                    for amp in AMPLITUDES for imp in IMPROVEMENTS}
    return {
        "A": ("SG 40 deg/s (original)", {40: lambda: sg_predict(cache, 40, False)}, lambda c: c),
        "B": ("SG tuned threshold", sg(False), lambda c: c),
        "C": ("SG + direction tuned threshold", sg(True), lambda c: c),
        "D": ("Piecewise-linear standalone + direction", pl(True), lambda c: (c[0], c[1])),
        "E": ("SG + direction + linear validation", hyb(True), lambda c: (c[1], c[0])),
        "SG+linear": ("SG + linear validation (no direction)", hyb(False), lambda c: (c[1], c[0])),
        "D-nodir": ("Piecewise-linear standalone no direction", pl(False), lambda c: (c[0], c[1])),
        "R": ("Global segmentation (hybrid_okn.py defaults)", {"default": lambda: global_segmentation_predict(cache, False)},
              lambda c: 0),
        "R+dir": ("Global segmentation + direction", {"default": lambda: global_segmentation_predict(cache, True)},
                  lambda c: 0),
    }


def config_name(c):
    if isinstance(c, tuple):
        return " ".join(str(x) for x in c)
    return str(c)


# ------------------------------------------------------------------ reporting

def groups(scored):
    out = [("all", "all", pooled(scored))]
    for key in ("participant", "condition", "direction"):
        for value in sorted({s[key] for s in scored}):
            out.append((key, value, pooled([s for s in scored if s[key] == value])))
    for value in sorted({(s["participant"], s["condition"]) for s in scored}):
        out.append(("participant x condition", " ".join(value),
                    pooled([s for s in scored if (s["participant"], s["condition"]) == value])))
    return out


def fmt(v, d=3):
    return "" if v is None else f"{v:.{d}f}"


def label_steps(trials, cache):
    """Two-line step size at each fast_phase label (best transition within ±100 ms), by condition."""
    by = collections.defaultdict(list)
    for tr in trials:
        steps = cache.standalone(tr)
        for x, lab in tr["events"]:
            if lab != "fast_phase":
                continue
            near = [c for c in steps if abs(c["start"] - x) <= TOL]
            by[tr["row"]["condition"]].append(max((abs(c["amplitude"]) for c in near), default=0.0))
    return by


def timing(cache, name, predict, trials):
    """Mean seconds per recording for the whole pipeline, from loaded data."""
    fresh = Cache(trials)
    predict = rebuild(fresh, name, predict)
    start = time.perf_counter()
    predict()
    return (time.perf_counter() - start) / len(trials)


def rebuild(cache, name, config):
    return methods(cache)[name][1][config]


def trial_level(trials, cache):
    """Existing window-level output (SG beats → OKN intervals): share of trials with any interval."""
    rows = []
    for name, get in (("SG 40", lambda tr: cache.analyse(tr, 40)["intervals"]),
                      ("SG 24", lambda tr: cache.analyse(tr, 24)["intervals"]),
                      ("global segmentation", lambda tr: hybrid_okn.analyse(tr["data"], detect_okn.Params())["intervals"])):
        for cond in ("OKN", "FIXMOVE", "FIXSTILL"):
            sel = [tr for tr in trials if tr["row"]["condition"] == cond]
            rows.append((name, cond, sum(bool(get(tr)) for tr in sel), len(sel)))
    return rows


def recovered(trials, cache, d_config):
    """Labels with no SG candidate within ±100 ms (any direction) that D's chosen setting matches."""
    pred_d = standalone_predict(cache, *d_config, True)
    rows = []
    for thr in (10, 20, 22, 24, 40):
        for cond in ("OKN", "FIXMOVE"):
            n = missed = found = 0
            for tr in trials:
                if tr["row"]["condition"] != cond:
                    continue
                refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
                _, unmatched, _ = evaluate_okn.match_events(refs, [f["start"] for f in cache.analyse(tr, thr)["fast"]], TOL)
                pairs, _, _ = evaluate_okn.match_events(refs, pred_d[tr["trial_id"]], TOL)
                hit = {r for r, _ in pairs}
                n, missed, found = n + len(refs), missed + len(unmatched), found + sum(x in hit for x in unmatched)
            rows.append((thr, cond, n, missed, found))
    return rows


def plot_summary(results, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(results)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))
    x = np.arange(len(names))
    for i, (key, color) in enumerate((("precision", "tab:blue"), ("recall", "tab:orange"), ("f1", "k"))):
        ax1.bar(x + (i - 1) * 0.27, [results[n]["all"][key] or 0 for n in names], 0.27, color=color, label=key)
    ax1.set_xticks(x, names, rotation=30, fontsize=8)
    ax1.set(ylim=(0, 1), ylabel="development score (pooled)")
    ax1.legend(fontsize=8)
    ax1.grid(axis="y", alpha=0.3)
    conds = ["OKN", "FIXMOVE", "FIXSTILL"]
    for i, cond in enumerate(conds):
        ax2.bar(x + (i - 1) * 0.27, [results[n]["condition"][cond]["fp_per_10s"] or 0 for n in names], 0.27,
                label=cond)
    ax2.set_xticks(x, names, rotation=30, fontsize=8)
    ax2.set(ylabel="false positives per 10 s")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3)
    fig.suptitle("Pilot 03 development recordings (28): each method at its chosen setting", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def plot_examples(trials, cache, chosen, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from scipy.signal import savgol_filter
    thr_e, amp_e = chosen["E"]
    amp_d, imp_d = chosen["D"]
    pred_e = hybrid_predict(cache, thr_e, amp_e, True)
    pred_d = standalone_predict(cache, amp_d, imp_d, True)
    pred_c = sg_predict(cache, chosen["C"], True)

    def errors(tr, preds):
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        pairs, missed, extra = evaluate_okn.match_events(refs, preds, TOL)
        return len(pairs), missed, extra

    def pick(cond, key):
        sel = [tr for tr in trials if tr["row"]["condition"] == cond]
        return max(sel, key=key)
    clean = pick("OKN", lambda tr: errors(tr, pred_c[tr["trial_id"]])[0] - len(errors(tr, pred_c[tr["trial_id"]])[1]) * 2)
    missy = pick("OKN", lambda tr: len(errors(tr, pred_c[tr["trial_id"]])[1]))
    fixmove = pick("FIXMOVE", lambda tr: len(errors(tr, pred_c[tr["trial_id"]])[1]) + len(errors(tr, pred_c[tr["trial_id"]])[2]))
    still = pick("FIXSTILL", lambda tr: len(cache.analyse(tr, thr_e)["fast"]))
    panels = [("Clean OKN", clean), ("OKN with short missed resets", missy), ("Noisy Dot + moving", fixmove),
              ("Dot + still with isolated saccades", still)]
    fig, axes = plt.subplots(len(panels), 1, figsize=(12, 3.1 * len(panels)))
    for ax, (title, tr) in zip(axes, panels):
        r = cache.analyse(tr, thr_e)
        t, valid = r["t"], r["valid"]
        raw = np.where(valid, r["angle"], np.nan)
        smooth = np.full_like(raw, np.nan)
        for a, b in detect_okn.continuous_runs(t, valid, r["dt"]):
            if b - a >= 5:
                smooth[a:b] = savgol_filter(r["angle"][a:b], 5, 2)
        ax.plot(t, raw, color="0.6", lw=0.8)
        ax.plot(t, smooth, color="0.15", lw=1.0)
        lo, hi = np.nanmin(raw), np.nanmax(raw)
        span = hi - lo or 1
        for x, lab in tr["events"]:
            if lab == "fast_phase":
                ax.axvline(x, color="tab:green", alpha=0.35, lw=3)
        accepted = set(pred_e[tr["trial_id"]])
        for f in r["fast"]:
            ok = f["start"] in accepted
            ax.plot(f["start"], hi + 0.08 * span, "v" if ok else "x", color="tab:blue" if ok else "tab:red", ms=6)
        for x in pred_d[tr["trial_id"]]:
            ax.plot(x, lo - 0.08 * span, "^", color="tab:purple", ms=6)
        tp_e, miss_e, fp_e = errors(tr, pred_e[tr["trial_id"]])
        tp_d, miss_d, fp_d = errors(tr, pred_d[tr["trial_id"]])
        ax.set_title(f"{title}: {tr['row']['participant']} T{int(tr['row']['trial_number']):03d} "
                     f"{tr['row']['condition']} {tr['row']['direction']} — "
                     f"E: TP {tp_e} FN {len(miss_e)} FP {len(fp_e)} · D: TP {tp_d} FN {len(miss_d)} FP {len(fp_d)}",
                     fontsize=9, loc="left")
        ax.set_ylim(lo - 0.18 * span, hi + 0.18 * span)
        ax.set_ylabel("eye angle (deg)")
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("time (s)")
    handles = [Line2D([], [], color="0.6"), Line2D([], [], color="0.15"), Line2D([], [], color="tab:green", lw=3, alpha=0.35),
               Line2D([], [], marker="v", color="tab:blue", ls=""), Line2D([], [], marker="x", color="tab:red", ls=""),
               Line2D([], [], marker="^", color="tab:purple", ls="")]
    fig.legend(handles, ["raw angle", "SG-smoothed (5 samples)", "human fast phase",
                         f"SG {thr_e} deg/s candidate accepted by E", "candidate rejected by E",
                         "piecewise-linear step (D)"], loc="upper right", ncol=3, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return [tr["trial_id"] for _, tr in panels]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--annotator", help="independent annotator to score (required if multiple are present)")
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent / "manifest.csv")
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "comparison")
    args = ap.parse_args(argv)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    trials = load_trials(args.labels_dir, args.trials_dir, args.manifest, args.annotator)
    cache = Cache(trials)
    by_part = {p: [tr for tr in trials if tr["row"]["participant"] == p] for p in ("P01", "P02")}
    ids = {p: {tr["trial_id"] for tr in v} for p, v in by_part.items()}

    grid_rows, results, chosen, cross, final, picks = [], {}, {}, {}, {}, {}
    for name, (desc, configs, conservative) in methods(cache).items():
        scored = {c: score(trials, predict()) for c, predict in configs.items()}
        summary = {c: pooled(s) for c, s in scored.items()}
        for c, g in summary.items():
            grid_rows.append(dict(method=name, config=config_name(c), **{k: fmt(g[k]) for k in
                                  ("precision", "recall", "f1", "fp_per_10s")}, tp=g["tp"], fp=g["fp"], fn=g["fn"]))
        best = choose(summary, conservative)
        chosen[name] = best
        # Overfitting check: choose on one participant, score on the other.
        held, picks[name] = [], {}
        for fit, test in (("P01", "P02"), ("P02", "P01")):
            sub = {c: pooled([s for s in sc if s["trial_id"] in ids[fit]]) for c, sc in scored.items()}
            c = choose(sub, conservative)
            picks[name][fit] = config_name(c)
            held += [s for s in scored[c] if s["trial_id"] in ids[test]]
        cross[name] = pooled(held)
        final[name] = scored[best]
        results[name] = {"desc": desc, "all": summary[best], "groups": groups(scored[best])}
        results[name]["condition"] = {v: g for k, v, g in results[name]["groups"] if k == "condition"}
        print(f"{name:10} {desc:46} config {config_name(best):10} F1 {fmt(summary[best]['f1'], 2)} "
              f"(cross-participant {fmt(cross[name]['f1'], 2)})")

    for name in results:
        results[name]["seconds"] = timing(cache, name, chosen[name], trials)

    with open(out / "grid.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(grid_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(grid_rows)
    fields = ["method", "description", "config", "group", "value", "n_trials", "tp", "fp", "fn", "precision",
              "recall", "f1", "fp_per_10s", "mean_abs_offset_ms"]
    with open(out / "comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for name, res in results.items():
            for kind, value, g in res["groups"]:
                w.writerow(dict(method=name, description=res["desc"], config=config_name(chosen[name]), group=kind,
                                value=value, n_trials=g["n_trials"], tp=g["tp"], fp=g["fp"], fn=g["fn"],
                                precision=fmt(g["precision"]), recall=fmt(g["recall"]), f1=fmt(g["f1"]),
                                fp_per_10s=fmt(g["fp_per_10s"]), mean_abs_offset_ms=fmt(g["mean_abs_offset_ms"], 1)))
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["method", "description", "config", "tp", "fp", "fn", "precision", "recall", "f1", "fp_per_10s",
                    "mean_abs_offset_ms", "cross_participant_f1", "config_chosen_on_P01", "config_chosen_on_P02",
                    "ms_per_recording"])
        for name, res in results.items():
            g = res["all"]
            w.writerow([name, res["desc"], config_name(chosen[name]), g["tp"], g["fp"], g["fn"], fmt(g["precision"]),
                        fmt(g["recall"]), fmt(g["f1"]), fmt(g["fp_per_10s"]), fmt(g["mean_abs_offset_ms"], 1),
                        fmt(cross[name]["f1"]), picks[name]["P01"], picks[name]["P02"], f"{1000 * res['seconds']:.1f}"])
    steps = label_steps(trials, cache)
    with open(out / "label_step_sizes.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["condition", "n_labels", "median_step_deg", "share_below_0.5_deg", "share_below_1_deg"])
        for cond, v in sorted(steps.items()):
            v = np.array(v)
            w.writerow([cond, len(v), f"{np.median(v):.2f}", f"{np.mean(v < 0.5):.2f}", f"{np.mean(v < 1):.2f}"])
    with open(out / "trial_level.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["detector", "condition", "trials_with_okn_interval", "n_trials"])
        w.writerows(trial_level(trials, cache))
    with open(out / "recovered.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sg_threshold", "condition", "labels", "missed_by_sg_candidates", "of_those_found_by_D"])
        w.writerows(recovered(trials, cache, chosen["D"]))
    plot_summary(results, out / "comparison.png")
    shown = plot_examples(trials, cache, chosen, out / "examples.png")
    print("example trials:", ", ".join(shown))
    print(f"outputs: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
