#!/usr/bin/env python3
"""Development-only comparison: SG vs Butterworth vs Butterworth + SG velocity.

    python3 analysis/pilot_03/compare_filters.py --labels-dir analysis/annotations_p03 --annotator AA \\
        [--trials-dir trials] [--output-dir analysis/pilot_03/filter_comparison]

Only the velocity estimate differs between methods (scripts/okn_filters.py).
Fast-phase detection, merging, the direction check, matching (±100 ms
one-to-one), artifact handling and metrics are shared. Scores the 28 primary
development recordings of analysis/pilot_03/manifest.csv for ONE independent
annotator; the evaluation split is never loaded. A missing recording or an
incomplete review is an error.

Grid (fixed before results):
  sg      SG 5/2 (unchanged)        thresholds 10, 12, ..., 40 deg/s
  bw      order 2, 5/8/12/15 Hz      same thresholds
  bw+sg   order 2, 5/8/12/15 Hz      same thresholds, SG 5/2 derivative

Selection within a method (the benchmark's rule): highest pooled F1; ties
within 0.01 → fewer FP per 10 s → higher threshold → higher cutoff (less
smoothing). Overfitting check: choose on one participant, score on the
other, both ways ("cross-participant F1").

Across methods (fixed before results): replace direction-aware SG only if
another method's pooled F1 is more than 0.01 higher AND it is at least as good
for both participants AND its cross-participant F1 is also higher.

Still stripes: no expected direction, so every fast phase is kept and scored.
No still-stripe recording has a fast_phase label, so every detection there is a
false positive; recall and F1 are not reported for them.
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
import okn_filters  # noqa: E402

TOL = evaluate_okn.DEFAULT_TOLERANCE_S
THRESHOLDS = list(range(10, 41, 2))
CUTOFFS = [5, 8, 12, 15]
TIE = 0.01
REFERENCE = ("sg", None, 22)          # the frozen direction-aware SG candidate


def grid():
    return [("sg", None, thr) for thr in THRESHOLDS] + \
        [(m, c, thr) for m in ("bw", "bw+sg") for c in CUTOFFS for thr in THRESHOLDS]


def load_trials(labels_dir, trials_dir, manifest, annotator):
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
            raise SystemExit(f"{tid}: recording not found in {trials_dir}")
        data = detect_okn.load_session(path)
        t, angle, valid, dt = okn_filters.signal(data)
        trials.append(dict(trial_id=tid, row=row, data=data, t=t, angle=angle, valid=valid, dt=dt,
                           duration=float(t[-1] - t[0]), events=evaluate_okn.review_events(events, review)))
    return trials


class Velocities:
    """Velocity per (trial, method, cutoff), computed once."""

    def __init__(self):
        self.cache = {}

    def get(self, tr, method, cutoff):
        key = (tr["trial_id"], method, cutoff)
        if key not in self.cache:
            self.cache[key] = okn_filters.velocity(tr["t"], tr["angle"], tr["valid"], tr["dt"], method, cutoff)
        return self.cache[key]


def predictions(trials, vel, config):
    method, cutoff, thr = config
    out = {}
    for tr in trials:
        fast = okn_filters.fast_phases_from(tr["t"], tr["angle"], tr["valid"], tr["dt"], vel.get(tr, method, cutoff), thr)
        out[tr["trial_id"]] = okn_filters.reset_starts(tr["data"], fast)
    return out


def score(trials, preds):
    out = []
    for tr in trials:
        s = evaluate_okn.score_trial(tr["events"], preds[tr["trial_id"]], TOL, artifacts="exclude")
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        pairs, _, _ = evaluate_okn.match_events(refs, preds[tr["trial_id"]], TOL)
        s.update(trial_id=tr["trial_id"], duration_s=tr["duration"], participant=tr["row"]["participant"],
                 condition=tr["row"]["condition"], direction=tr["row"]["direction"],
                 signed_offsets=[p - r for r, p in pairs])
        out.append(s)
    return out


def pooled(scored):
    g = evaluate_okn.summarize(scored)
    offsets = [x for s in scored for x in s["signed_offsets"]]
    g["mean_signed_offset_ms"] = 1000 * float(np.mean(offsets)) if offsets else None
    return g


def groups(scored):
    out = [("all", "all", pooled(scored))]
    for key in ("participant", "condition", "direction"):
        for value in sorted({s[key] for s in scored}):
            out.append((key, value, pooled([s for s in scored if s[key] == value])))
    for p, c in sorted({(s["participant"], s["condition"]) for s in scored}):
        out.append(("participant x condition", f"{p} {c}",
                    pooled([s for s in scored if (s["participant"], s["condition"]) == (p, c)])))
    return out


def choose(summaries):
    """{config: summary} → best config under the documented rule."""
    best = max(g["f1"] or 0 for g in summaries.values())
    tied = [c for c, g in summaries.items() if (g["f1"] or 0) >= best - TIE]
    return min(tied, key=lambda c: (summaries[c]["fp_per_10s"] or 0, -c[2], -(c[1] or np.inf)))


def run_sweep(trials, configs=None):
    """{config: per-trial scores} for every grid configuration (deterministic)."""
    vel = Velocities()
    return {c: score(trials, predictions(trials, vel, c)) for c in (configs or grid())}, vel


def name(config):
    method, cutoff, thr = config
    return f"{method} {thr} deg/s" if cutoff is None else f"{method} {cutoff} Hz {thr} deg/s"


def fmt(v, d=3):
    return "" if v is None else f"{v:.{d}f}"


# --------------------------------------------------------------- peak analysis

def label_peaks(trials, vel, chosen):
    """Per fast_phase label and method: peak |velocity| within ±100 ms, its time shift, threshold crossing."""
    rows = []
    for tr in trials:
        t = tr["t"]
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        for method, config in chosen.items():
            v = vel.get(tr, config[0], config[1])
            preds = okn_filters.reset_starts(tr["data"], okn_filters.fast_phases_from(
                t, tr["angle"], tr["valid"], tr["dt"], v, config[2]))
            pairs, _, _ = evaluate_okn.match_events(refs, preds, TOL)
            hit = {r for r, _ in pairs}
            for x in refs:
                w = (t >= x - TOL) & (t <= x + TOL) & np.isfinite(v)
                if not w.any():
                    rows.append(dict(trial_id=tr["trial_id"], condition=tr["row"]["condition"], method=method,
                                     label_s=x, peak=None, shift_ms=None, crosses=False, detected=x in hit))
                    continue
                i = np.flatnonzero(w)[np.argmax(np.abs(v[w]))]
                rows.append(dict(trial_id=tr["trial_id"], condition=tr["row"]["condition"], method=method, label_s=x,
                                 peak=float(abs(v[i])), shift_ms=1000 * float(t[i] - x),
                                 crosses=bool(abs(v[i]) > config[2]), detected=x in hit))
    return rows


def edge_detections(trials, vel, config, margin=TOL):
    """Detections within `margin` of a continuous-run boundary (where filter transients would show)."""
    n = 0
    for tr in trials:
        t = tr["t"]
        edges = [x for a, b in detect_okn.continuous_runs(t, tr["valid"], tr["dt"]) for x in (t[a], t[b - 1])]
        fast = okn_filters.fast_phases_from(t, tr["angle"], tr["valid"], tr["dt"], vel.get(tr, config[0], config[1]), config[2])
        n += sum(any(abs(s - e) <= margin for e in edges) for s in okn_filters.reset_starts(tr["data"], fast))
    return n


def frequency_response(fs=60.01):
    """Gain relative to an ideal differentiator at a few frequencies, per velocity estimator."""
    from scipy.signal import freqz, savgol_coeffs, sosfreqz, butter
    freqs = np.array([1, 2, 5, 8, 10, 12, 15, 20, 25])
    w = 2 * np.pi * freqs / fs
    sg = savgol_coeffs(5, 2, deriv=1, delta=1 / fs, use="dot")      # y'[n] = sum c[k] x[n-2+k]
    _, h_sg = freqz(sg[::-1], worN=w)
    sg_gain = np.abs(h_sg) / (2 * np.pi * freqs)
    cd_gain = np.abs(np.sin(w)) / w                                  # np.gradient interior
    rows = [("SG 5/2 derivative", sg_gain), ("central difference", cd_gain)]
    for c in CUTOFFS:
        _, h = sosfreqz(butter(okn_filters.BW_ORDER, c, fs=fs, output="sos"), worN=w)
        zero_phase = np.abs(h) ** 2                                      # forward-backward squares the gain
        rows.append((f"BW {c} Hz + central difference", zero_phase * cd_gain))
        rows.append((f"BW {c} Hz + SG 5/2", zero_phase * sg_gain))
    return freqs, rows


# --------------------------------------------------------------- figures

def plot_comparison(chosen, final, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [f"{m}\n{name(c)}" for m, c in chosen.items()]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(len(chosen))
    for i, (key, color) in enumerate((("precision", "#4C72B0"), ("recall", "#DD8452"), ("f1", "#333333"))):
        vals = [final[m]["all"][key] or 0 for m in chosen]
        bars = ax.bar(x + (i - 1) * 0.26, vals, 0.26, color=color, label=key)
        ax.bar_label(bars, fmt="%.2f", fontsize=7, padding=2)
    ax.set_xticks(x, labels, fontsize=8)
    ax.set(ylim=(0, 1), ylabel="pooled score, 28 development recordings")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("Each velocity estimator at its development-selected setting (with direction check)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "filter_comparison.png", dpi=130)
    plt.close(fig)


def plot_curves(summaries, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    ref = [summaries[("sg", None, t)]["f1"] for t in THRESHOLDS]
    for ax, method in zip(axes, ("bw", "bw+sg")):
        ax.plot(THRESHOLDS, ref, "k-o", ms=3, lw=1.6, label="SG (reference)")
        for c in CUTOFFS:
            ax.plot(THRESHOLDS, [summaries[(method, c, t)]["f1"] for t in THRESHOLDS], "-o", ms=3, lw=1,
                    label=f"{c} Hz")
        ax.set(title=method, xlabel="fast-phase threshold (deg/s)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("pooled F1 (development)")
    fig.tight_layout()
    fig.savefig(out / "f1_vs_threshold.png", dpi=130)
    plt.close(fig)


def plot_false_positives(chosen, final, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    conds = ["OKN", "FIXMOVE", "FIXSTILL"]
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(conds))
    for i, m in enumerate(chosen):
        vals = [final[m]["condition"][c]["fp_per_10s"] for c in conds]
        bars = ax.bar(x + (i - 1) * 0.26, vals, 0.26, label=f"{m} ({name(chosen[m])})")
        ax.bar_label(bars, fmt="%.2f", fontsize=7, padding=2)
    ax.set_xticks(x, ["OKN", "Dot + moving", "Dot + still"])
    ax.set(ylabel="false positives per 10 s (development)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "false_positives.png", dpi=130)
    plt.close(fig)


def pick_examples(trials, final_scores, peaks):
    by_id = {s["trial_id"]: s for s in final_scores["sg"]}
    okn = [tr for tr in trials if tr["row"]["condition"] == "OKN"]
    clean = max(okn, key=lambda tr: (by_id[tr["trial_id"]]["fn"] == 0 and by_id[tr["trial_id"]]["fp"] == 0,
                                     by_id[tr["trial_id"]]["tp"]))
    # OKN trial with the most labels SG misses because its peak stays under threshold.
    under = collections.Counter(r["trial_id"] for r in peaks if r["method"] == "sg" and r["condition"] == "OKN"
                                and not r["detected"] and r["peak"] is not None and not r["crosses"])
    short = next(tr for tr in okn if tr["trial_id"] == under.most_common(1)[0][0])
    fixmove = max((tr for tr in trials if tr["row"]["condition"] == "FIXMOVE"),
                  key=lambda tr: by_id[tr["trial_id"]]["fn"] + by_id[tr["trial_id"]]["fp"])
    still = max((tr for tr in trials if tr["row"]["condition"] == "FIXSTILL"),
                key=lambda tr: sum(s["fp"] for m in final_scores for s in final_scores[m] if s["trial_id"] == tr["trial_id"]))
    return [("Clean OKN", clean), ("OKN, short resets SG misses", short), ("Noisy Dot + moving", fixmove),
            ("Dot + still control", still)]


def plot_waveforms(examples, vel, chosen, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    colors = {"sg": "#333333", "bw": "#4C72B0", "bw+sg": "#C44E52"}
    styles = {"sg": "-", "bw": "-", "bw+sg": "--"}
    fig, axes = plt.subplots(2 * len(examples), 1, figsize=(12, 4.4 * len(examples)),
                             gridspec_kw=dict(height_ratios=[1.2, 1] * len(examples)))
    for k, (title, tr) in enumerate(examples):
        ax_p, ax_v = axes[2 * k], axes[2 * k + 1]
        t, valid = tr["t"], tr["valid"]
        raw = np.where(valid, tr["angle"], np.nan)
        ax_p.plot(t, raw, color="0.65", lw=1.4, label="raw")
        sg_pos = np.full_like(raw, np.nan)
        from scipy.signal import savgol_filter
        for a, b in detect_okn.continuous_runs(t, valid, tr["dt"]):
            if b - a >= 5:
                sg_pos[a:b] = savgol_filter(tr["angle"][a:b], 5, 2)
        ax_p.plot(t, sg_pos, color=colors["sg"], lw=0.9)
        bw_cut = chosen["bw"][1]
        ax_p.plot(t, okn_filters.smoothed_angle(t, tr["angle"], valid, tr["dt"], bw_cut), color=colors["bw"], lw=0.9)
        refs = [x for x, lab in tr["events"] if lab == "fast_phase"]
        for ax in (ax_p, ax_v):
            for x in refs:
                ax.axvline(x, color="#55A868", alpha=0.3, lw=3)
        lo, hi = np.nanmin(raw), np.nanmax(raw)
        span = (hi - lo) or 1
        for j, (m, c) in enumerate(chosen.items()):
            v = vel.get(tr, c[0], c[1])
            ax_v.plot(t, v, color=colors[m], lw=1.1, ls=styles[m])
            preds = okn_filters.reset_starts(tr["data"], okn_filters.fast_phases_from(
                t, tr["angle"], valid, tr["dt"], v, c[2]))
            ax_p.plot(preds, [hi + (0.08 + 0.1 * j) * span] * len(preds), "v", color=colors[m], ms=5)
            ax_v.axhline(c[2], color=colors[m], lw=0.6, ls="--")
            ax_v.axhline(-c[2], color=colors[m], lw=0.6, ls="--")
        ax_p.set_ylim(lo - 0.1 * span, hi + 0.42 * span)
        ax_p.set_ylabel("angle (deg)")
        ax_v.set_ylabel("velocity (deg/s)")
        peak = max(np.nanmax(np.abs(vel.get(tr, c[0], c[1]))) for c in chosen.values())
        ax_v.set_ylim(-min(peak * 1.1, 120), min(peak * 1.1, 120))
        row = tr["row"]
        ax_p.set_title(f"{title}: {row['participant']} T{int(row['trial_number']):03d} {row['condition']} "
                       f"{row['direction']}", fontsize=9, loc="left")
        for ax in (ax_p, ax_v):
            ax.grid(alpha=0.25)
            ax.set_xlim(t[0], t[-1])
    axes[-1].set_xlabel("time (s)")
    handles = [Line2D([], [], color="0.65", lw=1.4), Line2D([], [], color="#55A868", alpha=0.3, lw=3)] + \
        [Line2D([], [], color=colors[m], marker="v", lw=1.1, ls=styles[m]) for m in chosen]
    fig.legend(handles, ["raw angle", "human fast phase"] + [f"{m}: {name(c)} (position/velocity, ▼ detection, "
                                                              f"-- threshold)" for m, c in chosen.items()],
               loc="upper right", ncol=2, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(out / "waveform_examples.png", dpi=110)
    plt.close(fig)


# --------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, required=True)
    ap.add_argument("--annotator", required=True, help="the one independent annotator to score, e.g. AA")
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent / "manifest.csv")
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "filter_comparison")
    args = ap.parse_args(argv)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    trials = load_trials(args.labels_dir, args.trials_dir, args.manifest, args.annotator)
    ids = {p: {tr["trial_id"] for tr in trials if tr["row"]["participant"] == p} for p in ("P01", "P02")}
    scored, vel = run_sweep(trials)
    summaries = {c: pooled(s) for c, s in scored.items()}

    with open(out / "filter_sweep.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["method", "cutoff_hz", "threshold", "tp", "fp", "fn", "precision", "recall", "f1", "fp_per_10s",
                    "okn_fp_per_10s", "fixmove_fp_per_10s", "fixstill_fp_per_10s", "mean_abs_offset_ms"])
        for c, s in scored.items():
            g = summaries[c]
            cond = {v: x for k, v, x in groups(s) if k == "condition"}
            w.writerow([c[0], c[1] or "", c[2], g["tp"], g["fp"], g["fn"], fmt(g["precision"]), fmt(g["recall"]),
                        fmt(g["f1"]), fmt(g["fp_per_10s"]), fmt(cond["OKN"]["fp_per_10s"]),
                        fmt(cond["FIXMOVE"]["fp_per_10s"]), fmt(cond["FIXSTILL"]["fp_per_10s"]),
                        fmt(g["mean_abs_offset_ms"], 1)])

    chosen, cross, picks, final, final_scores = {}, {}, {}, {}, {}
    for method in ("sg", "bw", "bw+sg"):
        mine = {c: g for c, g in summaries.items() if c[0] == method}
        chosen[method] = choose(mine)
        held, picks[method] = [], {}
        for fit, test in (("P01", "P02"), ("P02", "P01")):
            sub = {c: pooled([s for s in scored[c] if s["trial_id"] in ids[fit]]) for c in mine}
            c = choose(sub)
            picks[method][fit] = name(c)
            held += [s for s in scored[c] if s["trial_id"] in ids[test]]
        cross[method] = pooled(held)
        final_scores[method] = scored[chosen[method]]
        gs = groups(scored[chosen[method]])
        final[method] = {"all": gs[0][2], "groups": gs, "condition": {v: g for k, v, g in gs if k == "condition"},
                         "participant": {v: g for k, v, g in gs if k == "participant"}}

    ref = summaries[REFERENCE]
    print(f"reference {name(REFERENCE)} + direction: TP {ref['tp']} FP {ref['fp']} FN {ref['fn']} F1 {fmt(ref['f1'])}")
    with open(out / "filter_comparison.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["method", "config", "group", "value", "n_trials", "tp", "fp", "fn", "precision", "recall", "f1",
                    "fp_per_10s", "mean_abs_offset_ms", "mean_signed_offset_ms", "cross_participant_f1",
                    "config_chosen_on_P01", "config_chosen_on_P02", "edge_detections"])
        for m, c in chosen.items():
            edges = edge_detections(trials, vel, c)
            for kind, value, g in final[m]["groups"]:
                w.writerow([m, name(c), kind, value, g["n_trials"], g["tp"], g["fp"], g["fn"], fmt(g["precision"]),
                            fmt(g["recall"]), fmt(g["f1"]), fmt(g["fp_per_10s"]), fmt(g["mean_abs_offset_ms"], 1),
                            fmt(g["mean_signed_offset_ms"], 1), fmt(cross[m]["f1"]) if kind == "all" else "",
                            picks[m]["P01"] if kind == "all" else "", picks[m]["P02"] if kind == "all" else "",
                            edges if kind == "all" else ""])
            g = final[m]["all"]
            print(f"{m:6} {name(c):22} P {fmt(g['precision'], 2)} R {fmt(g['recall'], 2)} F1 {fmt(g['f1'], 3)} "
                  f"FP/10s {fmt(g['fp_per_10s'], 2)} cross-participant {fmt(cross[m]['f1'], 3)} "
                  f"(P01→{picks[m]['P01']}, P02→{picks[m]['P02']}) edge detections {edges}")

    peaks = label_peaks(trials, vel, chosen)
    with open(out / "label_peaks.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["method", "config", "condition", "n_labels", "median_peak_deg_s", "median_peak_over_threshold",
                    "share_crossing_threshold", "share_detected", "median_peak_shift_ms",
                    "sg_missed_labels_detected"])
        sg_missed = {(r["trial_id"], r["label_s"]) for r in peaks if r["method"] == "sg" and not r["detected"]}
        for m, c in chosen.items():
            for cond in ("OKN", "FIXMOVE"):
                rs = [r for r in peaks if r["method"] == m and r["condition"] == cond]
                pk = [r["peak"] for r in rs if r["peak"] is not None]
                sh = [r["shift_ms"] for r in rs if r["shift_ms"] is not None]
                rec = sum(r["detected"] for r in rs if (r["trial_id"], r["label_s"]) in sg_missed)
                n_missed = sum((r["trial_id"], r["label_s"]) in sg_missed for r in rs)
                w.writerow([m, name(c), cond, len(rs), f"{np.median(pk):.1f}", f"{np.median(pk) / c[2]:.2f}",
                            f"{np.mean([r['crosses'] for r in rs]):.2f}", f"{np.mean([r['detected'] for r in rs]):.2f}",
                            f"{np.median(sh):.1f}", f"{rec} of {n_missed}"])

    freqs, response = frequency_response()
    with open(out / "frequency_response.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["estimator"] + [f"{x} Hz" for x in freqs])
        for label, gain in response:
            w.writerow([label] + [f"{g:.2f}" for g in gain])

    plot_comparison(chosen, final, out)
    plot_curves(summaries, out)
    plot_false_positives(chosen, final, out)
    examples = pick_examples(trials, final_scores, peaks)
    plot_waveforms(examples, vel, chosen, out)
    print("examples:", ", ".join(tr["trial_id"] for _, tr in examples))
    print(f"outputs: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
