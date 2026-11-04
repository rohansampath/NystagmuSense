#!/usr/bin/env python3
"""Pilot 01: the 21 recordings made on 2026-11-04 (one participant).

Reuses scripts/plot_gaze.py and scripts/detect_okn.py unchanged, with the
detector's default Params. Reads trials/ read-only; writes only under
analysis/pilot_01/.

    python3 analysis/pilot_01/run_pilot.py      # needs scripts/requirements.txt
"""

import contextlib
import csv
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import detect_okn  # noqa: E402
import plot_gaze  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SESSION_GLOB = "NS_20261104-*"
BATCH1_N = 5
BATCH1_TASKS = ["centre 10 s", "left 5 s → right 5 s", "right 5 s → left 5 s",
                "alternate L/R every ~2 s", "centre + deliberate blinks"]
EXPECTED_B2 = "ABC" "BCA" "CAB" "ACB" "BAC"
MODE_TO_COND = {"okn": "A", "fixationMovingStripes": "B", "fixationStillStripes": "C"}
COND_NAME = {"A": "A: OKN (watch stripes)", "B": "B: dot + moving stripes",
             "C": "C: dot + still stripes"}
COND_COLOR = {"A": "tab:blue", "B": "tab:orange", "C": "tab:gray"}
EXPLORATORY_FAST = 20.0   # deg/s; sensitivity check only, NOT a detector change
PEAK_MIN, PEAK_SEP = 10.0, 9   # exploratory |velocity| peaks: deg/s, samples (~150 ms)
P = detect_okn.Params()
SIGN_NOTE = "detector angle (deg)\n[documented + = right; see report]"


# ---------------------------------------------------------------- manifest

def build_manifest():
    rows = []
    for d in sorted((ROOT / "trials").glob(SESSION_GLOB)):
        stem = d.name
        meta = json.loads((d / f"{stem}.json").read_text())
        with open(d / f"{stem}.csv", newline="") as f:
            first = next(csv.DictReader(f))
        rows.append(dict(stem=stem, csv=d / f"{stem}.csv", meta=meta,
                         started=meta["startedAt"], host0=float(first["host_time_s"]),
                         mode=meta["stimulus"].get("trialMode", "okn")))
    by_clock = sorted(rows, key=lambda r: r["started"])
    by_uptime = sorted(rows, key=lambda r: r["host0"])
    assert [r["stem"] for r in by_clock] == [r["stem"] for r in by_uptime], \
        "wall-clock and monotonic orders disagree"
    for i, r in enumerate(by_clock):
        r["id"] = f"T{i + 1:02d}"
        r["gap_s"] = None if i == 0 else round(r["host0"] - by_clock[i - 1]["host0"], 1)
        if i < BATCH1_N:
            r.update(batch=1, expected=BATCH1_TASKS[i], expected_cond="C", label=f"V{i + 1}")
        else:
            k = i - BATCH1_N
            exp = EXPECTED_B2[k] if k < len(EXPECTED_B2) else "—"
            r.update(batch=2, expected=COND_NAME.get(exp, "none (extra recording)"),
                     expected_cond=exp, label=None)
        r["cond"] = MODE_TO_COND[r["mode"]]
        r["matches"] = r["cond"] == r["expected_cond"]
        if r["batch"] == 2:
            r["label"] = f"{r['cond']}{sum(x.get('cond') == r['cond'] and x['batch'] == 2 for x in by_clock[:i + 1])}"
    return by_clock


# ---------------------------------------------------------------- metrics

def union_length(intervals):
    total, end = 0.0, -math.inf
    for a, b in sorted((iv["onset"], iv["offset"]) for iv in intervals):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def windows_evaluated(t, valid, dt):
    """Number of sliding windows analyse() evaluates (same segmentation)."""
    n = 0
    for a, b in detect_okn.continuous_runs(t, valid, dt):
        if b - a < P.sg_window:
            continue
        ts = t[a:b]
        last = max(ts[0], ts[-1] - P.window_s)
        starts = list(np.arange(ts[0], last + 1e-9, P.step_s))
        n += len(starts) + (1 if last - starts[-1] > 1e-9 else 0)
    return n


def trial_metrics(row):
    data = detect_okn.load_session(row["csv"])
    r = detect_okn.analyse(data, P)
    t, dt, valid, angle, vel = r["t"], r["dt"], r["valid"], r["angle"], r["velocity"]
    span = t[-1] - t[0]
    dts = np.diff(t)
    blink = np.fmax(data["blink_left"], data["blink_right"])
    blink_runs = detect_okn.runs(blink > P.blink_threshold)
    invalid_t = t[~valid]
    blink_adjacent = sum(
        1 for f in r["fast"]
        if invalid_t.size and np.min(np.abs(invalid_t - np.clip(invalid_t, f["start"], f["end"]))) <= 0.15)
    d_angle = np.abs(np.diff(angle))
    pair_valid = valid[1:] & valid[:-1]
    beats = r["beats"]
    stim = r["stimulus"]
    explore = detect_okn.analyse(data, detect_okn.Params(fast_threshold=EXPLORATORY_FAST))
    with np.errstate(invalid="ignore"):
        absvel = np.abs(vel[np.isfinite(vel)])
    # Exploratory, detector-independent: local |SG velocity| peaks, to see how
    # many candidate resets exist relative to the 40 deg/s fast-phase threshold.
    pk, _ = find_peaks(np.nan_to_num(np.abs(vel)), height=PEAK_MIN, distance=PEAK_SEP)
    peaks = np.abs(vel[pk])
    left = -np.degrees(np.arctan2(data["left_dir_x"], data["left_dir_z"]))
    right = -np.degrees(np.arctan2(data["right_dir_x"], data["right_dir_z"]))
    both = np.isfinite(left) & np.isfinite(right)
    return dict(
        r=r, data=data,
        samples=len(t), span_s=span, rate_hz=(len(t) - 1) / span,
        dt_median_ms=1000 * float(np.median(dts)), dt_sd_ms=1000 * float(np.std(dts)),
        dt_max_ms=1000 * float(np.max(dts)),
        gaps=int(np.sum(dts > detect_okn.GAP_FACTOR * dt)),
        tracked_pct=100 * float(np.mean(data["tracked"] == 1)),
        valid_pct=100 * float(valid.mean()),
        blink_events=len(blink_runs),
        fast=len(r["fast"]), fast_right=sum(f["direction"] > 0 for f in r["fast"]),
        fast_blink_adjacent=blink_adjacent,
        slow_total=len(r["slow"]), slow_accepted=sum(s["accepted"] for s in r["slow"]),
        beats=len(beats),
        beats_slow_with_stim_documented=sum(b["direction"] == stim for b in beats) if stim else None,
        median_beat_spv=float(np.median([b["slow_velocity"] for b in beats])) if beats else None,
        windows_pos=len(r["windows"]), windows_total=windows_evaluated(t, valid, dt),
        intervals=len(r["intervals"]), okn_fraction=union_length(r["intervals"]) / span,
        jumps_gt3deg=int(np.sum((d_angle > 3) & pair_valid)),
        vel_p99=float(np.percentile(absvel, 99)) if absvel.size else None,
        vel_max=float(np.max(absvel)) if absvel.size else None,
        angle_sd=float(np.nanstd(np.where(valid, angle, np.nan))),
        lr_corr=float(np.corrcoef(left[both], right[both])[0, 1]),
        lr_offset_mean=float(np.mean(left[both] - right[both])),
        lr_offset_sd=float(np.std(left[both] - right[both])),
        explore_fast=len(explore["fast"]), explore_beats=len(explore["beats"]),
        explore_okn_fraction=union_length(explore["intervals"]) / span,
        peaks_gt10=len(peaks), peaks_gt20=int(np.sum(peaks > 20)), peaks_gt40=int(np.sum(peaks > 40)),
        peak_heights=peaks, stimulus=stim, left=left, right=right,
    )


def fmt(v, digits=2):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "n/a"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


# ---------------------------------------------------------------- batch 1

def segment_mean(t, a, lo, hi):
    m = (t >= lo) & (t < hi) & np.isfinite(a)
    return float(np.mean(a[m]))


def batch1_analysis(rows, metrics):
    out = {}
    for row in rows:
        m = metrics[row["id"]]
        t, a = m["r"]["t"], np.where(m["r"]["valid"], m["r"]["angle"], np.nan)
        res = {}
        if row["label"] in ("V1", "V5"):
            fit = np.isfinite(a)
            slope = np.polyfit(t[fit], a[fit], 1)[0]
            sec_sd = [np.nanstd(a[(t >= s) & (t < s + 1)]) for s in range(10)]
            res.update(mean=float(np.nanmean(a)), sd=float(np.nanstd(a)),
                       range=float(np.nanmax(a) - np.nanmin(a)), drift_deg_per_s=float(slope),
                       median_1s_sd=float(np.nanmedian(sec_sd)))
        if row["label"] in ("V2", "V3"):
            first, second = segment_mean(t, a, 0.5, 4.0), segment_mean(t, a, 6.0, 9.5)
            l1, l2 = segment_mean(t, m["left"], 0.5, 4.0), segment_mean(t, m["left"], 6.0, 9.5)
            r1, r2 = segment_mean(t, m["right"], 0.5, 4.0), segment_mean(t, m["right"], 6.0, 9.5)
            mid = (first + second) / 2
            cross = t[np.flatnonzero(np.diff(np.sign(np.nan_to_num(a - mid))) != 0)]
            res.update(first=first, second=second, step=second - first,
                       left_eye_step=l2 - l1, right_eye_step=r2 - r1,
                       crossing_s=[float(c) for c in cross])
        if row["label"] == "V4":
            med = np.nanmedian(a)
            # Hysteresis (±2 deg around the median) so noise isn't counted as switches.
            state, switches = 0, []
            for ti, ai in zip(t, a):
                if not np.isfinite(ai):
                    continue
                s = 1 if ai > med + 2 else -1 if ai < med - 2 else state
                if state and s != state:
                    switches.append(float(ti))
                state = s
            res.update(median=float(med), switches=switches)
        out[row["id"]] = res
    return out


def plot_batch1(rows, metrics, path):
    fig, axes = plt.subplots(len(rows), 1, figsize=(11, 2.3 * len(rows)), sharex=True)
    for ax, row in zip(axes, rows):
        m = metrics[row["id"]]
        t = m["r"]["t"]
        ax.plot(t, m["left"], color="tab:blue", lw=0.9, label="left eye")
        ax.plot(t, m["right"], color="tab:red", lw=0.9, label="right eye")
        ax.plot(t, m["r"]["angle"], color="k", lw=1.2, label="mean (detector input)")
        for a, b in detect_okn.runs(~m["r"]["valid"]):
            ax.axvspan(t[a], t[min(b, len(t) - 1)], color="0.85", zorder=0)
        if row["label"] in ("V2", "V3", "V4"):
            ax.axvline(5, color="0.5", ls=":", lw=1)
        ax.set_title(f"{row['id']} / {row['label']}: instructed {row['expected']}", fontsize=9, loc="left")
        ax.set_ylabel("deg", fontsize=8)
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper right", fontsize=7, ncol=3)
    axes[-1].set_xlabel("time since session start (s)")
    fig.suptitle("Batch 1 validation: horizontal eye angle, -atan2(dir_x, dir_z) as in detect_okn.py\n"
                 "grey = detector-invalid (blink-masked); documented sign + = subject's right", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_blinks(row, m, path):
    r, d = m["r"], m["data"]
    t = r["t"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(t, r["angle"], color="0.6", lw=0.8, label="all samples")
    axes[0].plot(t, np.where(r["valid"], r["angle"], np.nan), color="k", lw=1, label="detector-valid")
    axes[0].set_ylabel(SIGN_NOTE, fontsize=8)
    axes[1].plot(t, d["blink_left"], color="tab:blue", lw=0.9, label="eyeBlinkLeft")
    axes[1].plot(t, d["blink_right"], color="tab:red", lw=0.9, label="eyeBlinkRight")
    axes[1].axhline(P.blink_threshold, color="k", ls="--", lw=0.8, label="mask threshold")
    axes[1].set_ylabel("blink coefficient (0–1)")
    axes[2].plot(t, r["velocity"], color="k", lw=0.9)
    for y in (P.fast_threshold, -P.fast_threshold):
        axes[2].axhline(y, color="tab:red", ls="--", lw=0.8)
    axes[2].set_ylabel("SG velocity (deg/s)")
    for ax in axes:
        for f in r["fast"]:
            ax.axvspan(f["start"], f["end"] + r["dt"], color="tab:red", alpha=0.25, lw=0)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right", fontsize=7) if ax is not axes[2] else None
    axes[-1].set_xlabel("time since session start (s)")
    axes[0].set_title(f"{row['id']} / {row['label']}: centre + deliberate blinks "
                      f"({m['blink_events']} blink events > {P.blink_threshold}; "
                      f"{m['fast']} detector fast phases, red)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------- batch 2 plots

def strip(ax, rows, metrics, key, ylabel, title, note=None):
    for i, c in enumerate("ABC"):
        vals = [(row["id"], metrics[row["id"]][key]) for row in rows if row["cond"] == c]
        have = [(tid, v) for tid, v in vals if v is not None]
        xs = i + np.linspace(-0.12, 0.12, max(len(have), 1))[:len(have)]
        identical = len({v for _, v in have}) == 1
        for x, (tid, v) in zip(xs, have):
            ax.scatter(x, v, color=COND_COLOR[c], s=30, zorder=3)
            if not identical:
                ax.annotate(tid, (x, v), xytext=(4, 2), textcoords="offset points", fontsize=6)
        if have and identical:
            ax.annotate(f"all {len(have)} = {fmt(have[0][1], 2)}", (i, have[0][1]), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontsize=7)
        if have:
            v = np.array([h[1] for h in have], dtype=float)
            ax.errorbar(i + 0.3, v.mean(), yerr=v.std(ddof=1) if len(v) > 1 else 0,
                        fmt="_", color="k", capsize=4, markersize=14)
        missing = len(vals) - len(have)
        if missing:
            ax.text(i, ax.get_ylim()[0], f"{missing} trial(s) n/a", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(range(3), [f"{c}\n(n={sum(r['cond'] == c for r in rows)})" for c in "ABC"])
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title + (f"\n{note}" if note else ""), fontsize=9)
    ax.grid(alpha=0.3, axis="y")


def plot_comparison(rows, metrics, path):
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.5))
    strip(axes[0, 0], rows, metrics, "beats", "beats per trial", "Candidate OKN beats (default params)")
    strip(axes[0, 1], rows, metrics, "median_beat_spv", "deg/s (detector sign)",
          "Median beat slow-phase velocity", "only trials with ≥1 beat")
    strip(axes[0, 2], rows, metrics, "okn_fraction", "fraction of trial", "OKN-positive fraction",
          "union of merged candidate windows / span")
    strip(axes[1, 0], rows, metrics, "valid_pct", "% samples", "Detector-valid samples",
          "tracked, finite, blink ≤ 0.5, ±50 ms pad")
    strip(axes[1, 1], rows, metrics, "fast", "fast phases per trial", "Fast phases (|v| > 40 deg/s)")
    strip(axes[1, 2], rows, metrics, "explore_beats", "beats per trial",
          f"EXPLORATORY: beats at fast threshold {EXPLORATORY_FAST:g} deg/s",
          "sensitivity check only; not the detector's result")
    fig.suptitle("Batch 2 by condition: individual trials (labelled) with mean ± SD (black)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_velocity_peaks(rows, metrics, path):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, c in enumerate("ABC"):
        h = np.concatenate([metrics[r["id"]]["peak_heights"] for r in rows if r["cond"] == c])
        ax.scatter(i + np.random.default_rng(0).uniform(-0.18, 0.18, len(h)), h, s=14,
                   color=COND_COLOR[c], alpha=0.8)
        ax.text(i, 3, f"{len(h)} peaks\n{int(np.sum(h > 40))} > 40", ha="center", fontsize=8)
    ax.axhline(P.fast_threshold, color="tab:red", ls="--", lw=1, label="detector fast threshold (40)")
    ax.axhline(EXPLORATORY_FAST, color="tab:red", ls=":", lw=1, label="exploratory 20 deg/s")
    ax.set_xticks(range(3), [COND_NAME[c] for c in "ABC"], fontsize=8)
    ax.set_yscale("log")
    ax.set_ylim(2, 300)
    ax.set_ylabel("|SG velocity| peak (deg/s, log)")
    ax.set_title("EXPLORATORY: local velocity peaks > 10 deg/s, ≥150 ms apart, pooled per condition\n"
                 "(candidate resets, not a detector output and not ground truth)", fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_traces_grid(rows, metrics, path):
    fig, axes = plt.subplots(len(rows), 1, figsize=(11, 1.35 * len(rows)), sharex=True)
    for ax, row in zip(axes, rows):
        r = metrics[row["id"]]["r"]
        a = np.where(r["valid"], r["angle"], np.nan)
        ax.plot(r["t"], a - np.nanmedian(a), color=COND_COLOR[row["cond"]], lw=0.9)
        for f in r["fast"]:
            ax.axvspan(f["start"], f["end"] + r["dt"], color="tab:red", alpha=0.3, lw=0)
        for b in r["beats"]:
            ax.axvline(b["time"], color="tab:green", lw=1)
        ax.set_ylim(-8, 8)
        ax.text(0.005, 0.8, f"{row['id']} {row['label']}  beats={len(r['beats'])}",
                transform=ax.transAxes, fontsize=7)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=6)
    axes[-1].set_xlabel("time since session start (s)")
    fig.suptitle("All Batch 2 trials in recording order: detector angle minus trial median (deg, ±8 shown)\n"
                 "red = fast phase, green = accepted beat; blue A, orange B, grey C", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_representative(picks, metrics, path):
    fig, axes = plt.subplots(2, 3, figsize=(15, 6.5), sharex=True, sharey="row")
    for j, row in enumerate(picks):
        m = metrics[row["id"]]
        r = m["r"]
        a = np.where(r["valid"], r["angle"], np.nan)
        axes[0, j].plot(r["t"], a - np.nanmedian(a), color=COND_COLOR[row["cond"]], lw=1)
        for s in r["slow"]:
            if s["accepted"]:
                ts = np.array([s["start"], s["end"]])
                axes[0, j].plot(ts, s["velocity"] * ts + s["intercept"] - np.nanmedian(a), color="tab:green", lw=2)
        axes[1, j].plot(r["t"], r["velocity"], color="k", lw=0.8)
        for y in (P.fast_threshold, -P.fast_threshold):
            axes[1, j].axhline(y, color="tab:red", ls="--", lw=0.8)
        for ax in axes[:, j]:
            for f in r["fast"]:
                ax.axvspan(f["start"], f["end"] + r["dt"], color="tab:red", alpha=0.25, lw=0)
            ax.grid(alpha=0.3)
        axes[0, j].set_title(f"{COND_NAME[row['cond']]}\n{row['id']} ({row['label']}): "
                             f"{m['beats']} beats, {m['fast']} fast phases", fontsize=9)
        axes[1, j].set_xlabel("time (s)")
    axes[0, 0].set_ylabel("angle − median (deg)\n[detector sign]")
    axes[1, 0].set_ylabel("SG velocity (deg/s)")
    fig.suptitle("Representative trials (median beat count within each condition); "
                 "green = accepted slow-phase fit, red = fast phase", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_beat_timing(rows, metrics, path):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    for i, c in enumerate("ABC"):
        times = [b["time"] for row in rows if row["cond"] == c for b in metrics[row["id"]]["r"]["beats"]]
        ex = [b["time"] for row in rows if row["cond"] == c
              for b in detect_okn.analyse(metrics[row["id"]]["data"],
                                          detect_okn.Params(fast_threshold=EXPLORATORY_FAST))["beats"]]
        ax.scatter(ex, np.full(len(ex), i + 0.15), marker="|", s=120, color=COND_COLOR[c], alpha=0.45,
                   label="exploratory 20 deg/s" if i == 0 else None)
        ax.scatter(times, np.full(len(times), i - 0.15), marker="|", s=160, color=COND_COLOR[c], lw=2.5,
                   label="default params" if i == 0 else None)
        if not times and not ex:
            ax.text(5, i, "no beats in any trial (default or exploratory)", ha="center", va="center", fontsize=8)
    ax2 = ax.twinx()
    t = np.linspace(0, 10, 200)
    ax2.plot(t, 1 - t / 10, color="tab:purple", lw=1, ls="--")
    ax2.set_ylabel("scheduled background\nsRGB value (bars = 0)", color="tab:purple", fontsize=8)
    ax.set_yticks(range(3), [COND_NAME[c] for c in "ABC"], fontsize=8)
    ax.set_xlabel("beat time (s since session start)")
    ax.set_title("When beats occur, pooled per condition (each tick = one beat)", fontsize=10)
    ax.legend(loc="upper right", fontsize=7)
    ax.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------- driver

def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    figs, per_trial, det_out = OUT / "figures", OUT / "figures" / "trials", OUT / "detector_output"
    for d in (figs, per_trial, det_out):
        d.mkdir(parents=True, exist_ok=True)

    rows = build_manifest()
    write_csv(OUT / "manifest.csv",
              ["trial", "label", "batch", "expected", "recorded_mode", "condition", "matches_expected",
               "filename", "startedAt_utc", "seconds_since_previous"],
              [[r["id"], r["label"], r["batch"], r["expected"], r["mode"], r["cond"], r["matches"],
                r["stem"], r["started"], r["gap_s"]] for r in rows])

    metrics = {}
    for r in rows:
        metrics[r["id"]] = trial_metrics(r)
        # Existing scripts, unchanged, via their CLIs.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            plot_gaze.main([str(r["csv"]), "--output", str(per_trial / f"{r['id']}_{r['label']}_gaze.png")])
            detect_okn.main([str(r["csv"]), "--plot", str(per_trial / f"{r['id']}_{r['label']}_okn.png")])
        (det_out / f"{r['id']}_{r['label']}.txt").write_text(buf.getvalue().replace(str(ROOT) + "/", ""))

    b1 = [r for r in rows if r["batch"] == 1]
    b2 = [r for r in rows if r["batch"] == 2]
    b1res = batch1_analysis(b1, metrics)
    plot_batch1(b1, metrics, figs / "batch1_validation_traces.png")
    plot_blinks(b1[4], metrics[b1[4]["id"]], figs / "batch1_V5_blinks.png")
    plot_comparison(b2, metrics, figs / "batch2_condition_comparison.png")
    plot_traces_grid(b2, metrics, figs / "batch2_all_traces.png")
    picks = []
    for c in "ABC":
        group = sorted((r for r in b2 if r["cond"] == c), key=lambda r: (metrics[r["id"]]["beats"], r["id"]))
        picks.append(group[(len(group) - 1) // 2])
    plot_representative(picks, metrics, figs / "batch2_representative_ABC.png")
    plot_beat_timing(b2, metrics, figs / "batch2_beat_timing.png")
    plot_velocity_peaks(b2, metrics, figs / "batch2_velocity_peaks.png")

    keys = ["samples", "rate_hz", "dt_sd_ms", "dt_max_ms", "gaps", "tracked_pct", "valid_pct",
            "blink_events", "fast", "fast_right", "fast_blink_adjacent", "slow_total", "slow_accepted",
            "beats", "beats_slow_with_stim_documented", "median_beat_spv", "windows_pos", "windows_total",
            "intervals", "okn_fraction", "jumps_gt3deg", "vel_p99", "vel_max", "angle_sd",
            "lr_corr", "lr_offset_mean", "lr_offset_sd", "explore_fast", "explore_beats", "explore_okn_fraction",
            "peaks_gt10", "peaks_gt20", "peaks_gt40"]
    write_csv(OUT / "metrics_per_trial.csv", ["trial", "label", "batch", "condition", "filename"] + keys,
              [[r["id"], r["label"], r["batch"], r["cond"], r["stem"]]
               + [fmt(metrics[r["id"]][k], 4) for k in keys] for r in rows])

    summary = []
    for c in "ABC":
        group = [r for r in b2 if r["cond"] == c]
        for k in ("beats", "median_beat_spv", "okn_fraction", "windows_pos", "fast", "valid_pct",
                  "explore_beats", "explore_okn_fraction", "angle_sd", "peaks_gt20", "vel_p99"):
            vals = [metrics[r["id"]][k] for r in group]
            have = np.array([v for v in vals if v is not None], dtype=float)
            summary.append([c, k, len(group), len(have),
                            fmt(float(have.mean()), 3) if have.size else "n/a",
                            fmt(float(have.std(ddof=1)), 3) if have.size > 1 else "n/a",
                            " ".join(f"{r['id']}={fmt(metrics[r['id']][k], 2)}" for r in group)])
    write_csv(OUT / "condition_summary.csv",
              ["condition", "metric", "n_trials", "n_with_value", "mean", "sd", "per_trial"], summary)

    (OUT / "batch1_results.json").write_text(json.dumps(
        {r["id"]: dict(label=r["label"], task=r["expected"], **b1res[r["id"]],
                       lr_corr=metrics[r["id"]]["lr_corr"], lr_offset_sd=metrics[r["id"]]["lr_offset_sd"],
                       blink_events=metrics[r["id"]]["blink_events"], fast=metrics[r["id"]]["fast"],
                       fast_blink_adjacent=metrics[r["id"]]["fast_blink_adjacent"],
                       beats=metrics[r["id"]]["beats"], valid_pct=metrics[r["id"]]["valid_pct"])
         for r in b1}, indent=1))
    print(f"{len(rows)} recordings → {OUT.relative_to(ROOT)}/")
    print("representative:", ", ".join(f"{p['cond']}={p['id']}" for p in picks))


if __name__ == "__main__":
    main()
