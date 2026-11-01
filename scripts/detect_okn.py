#!/usr/bin/env python3
"""Detect candidate optokinetic nystagmus (OKN) in a NystagmuSense session CSV.

Usage:
    python3 scripts/detect_okn.py path/to/NS_....csv [--plot out.png]

Baseline, interpretable pipeline (no machine learning) on raw, uncalibrated
ARKit signals:

1. Horizontal eye angle = -mean over both eyes of degrees(atan2(dir_x, dir_z)).
   Negated so + = subject's right, because ARKit face-anchor +x is the subject's
   left. THIS SIGN CONVENTION IS UNVERIFIED ON DEVICE.
2. Invalid samples: tracked != 1, non-finite angle, or blink > threshold,
   padded in time on both sides.
3. Velocity: local polynomial first derivative using actual timestamps
   (Savitzky-Golay on uniform data), separately per contiguous valid run.
4. Fast phases: runs where |velocity| exceeds a threshold; nearby same-direction
   runs are merged.
5. Slow phases: fit inter-fast-phase segments; reject poor line fits and
   direction-inconsistent drift before pairing beats.
6. OKN beat: a slow phase followed shortly by an opposite-direction fast phase.
7. OKN windows: sliding windows with enough direction-consistent beats, merged
   into candidate onset/offset intervals.
8. Stimulus direction from the sign of change of stim_displacement_pt.

Thresholds were tuned on synthetic data only. Output is a candidate detection
for research, with no clinical or contrast-sensitivity meaning.
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter

REQUIRED = ["t_s", "tracked", "left_dir_x", "left_dir_z", "right_dir_x", "right_dir_z"]
OPTIONAL = ["blink_left", "blink_right", "stim_displacement_pt", "stim_bg_gray"]
SIGN_CAVEAT = "eye-angle sign convention (+ = subject's right) is UNVERIFIED on device"
GAP_FACTOR = 2.5  # same missing-frame boundary as plot_gaze.py


@dataclass
class Params:
    blink_threshold: float = 0.5     # max(blink_left, blink_right) above this → invalid
    pad_ms: float = 50               # invalid samples padded by this on each side
    sg_window: int = 5               # Savitzky-Golay window, samples (odd)
    sg_polyorder: int = 2
    fast_threshold: float = 40       # deg/s
    merge_gap_ms: float = 50         # merge same-direction fast runs closer than this
    min_slow_s: float = 0.15         # minimum slow-phase duration of valid data
    min_slow_velocity: float = 1     # deg/s, for a slow phase to count in a beat
    min_slow_r2: float = 0.8         # provisional fit-quality gate, not validated
    min_slow_direction_agreement: float = 0.8  # time fraction of velocity with fit's sign
    beat_max_gap_s: float = 0.1      # slow-phase end → opposite fast-phase start
    window_s: float = 2.0
    step_s: float = 0.5
    min_beats: int = 2               # per window
    min_agreement: float = 0.75      # fraction of window beats sharing a direction


class SessionError(Exception):
    pass


def validate_params(p):
    for f in fields(p):
        value = getattr(p, f.name)
        if not math.isfinite(value):
            raise SessionError(f"{f.name} must be finite")
    if not (isinstance(p.sg_window, int) and isinstance(p.sg_polyorder, int)
            and p.sg_polyorder >= 1 and p.sg_window > p.sg_polyorder and p.sg_window % 2 == 1):
        raise SessionError("sg_window must be odd and greater than sg_polyorder >= 1")
    for name in ("fast_threshold", "min_slow_s", "min_slow_velocity", "window_s", "step_s"):
        if getattr(p, name) <= 0:
            raise SessionError(f"{name} must be positive")
    for name in ("pad_ms", "merge_gap_ms", "beat_max_gap_s"):
        if getattr(p, name) < 0:
            raise SessionError(f"{name} must be nonnegative")
    if not isinstance(p.min_beats, int) or p.min_beats < 1:
        raise SessionError("min_beats must be a positive integer")
    if not 0 <= p.blink_threshold <= 1 or not 0.5 < p.min_agreement <= 1:
        raise SessionError("blink_threshold must be in [0, 1] and min_agreement in (0.5, 1]")
    if not 0 <= p.min_slow_r2 <= 1 or not 0 <= p.min_slow_direction_agreement <= 1:
        raise SessionError("slow-phase quality thresholds must be in [0, 1]")


# ---------------------------------------------------------------- loading

def load_session(path):
    """Return {column: np.ndarray} for the required and available optional columns."""
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            if len(header) != len(set(header)):
                raise SessionError("duplicate CSV column names")
            missing = [c for c in REQUIRED if c not in header]
            if missing:
                raise SessionError(f"missing required column(s): {', '.join(missing)}")
            cols = REQUIRED + [c for c in OPTIONAL if c in header]
            rows = {c: [] for c in cols}
            for line_no, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise SessionError(f"line {line_no}: wrong number of CSV fields")
                for c in cols:
                    value = (row[c] or "").strip()
                    try:
                        rows[c].append(float(value) if value else math.nan)
                    except ValueError:
                        raise SessionError(f"line {line_no}: malformed {c} value {value!r}") from None
    except OSError as e:
        raise SessionError(str(e)) from None
    data = {c: np.asarray(v, dtype=float) for c, v in rows.items()}
    if len(data["t_s"]) < 2:
        raise SessionError("need at least 2 samples")
    if not np.all(np.isfinite(data["t_s"])) or np.any(np.diff(data["t_s"]) <= 0):
        raise SessionError("t_s must be finite and strictly increasing")
    return data


# ---------------------------------------------------------------- 1–3: signal

def eye_angle(data):
    """Horizontal eye angle in degrees, + = subject's right (sign UNVERIFIED)."""
    with np.errstate(invalid="ignore"):
        left = np.degrees(np.arctan2(data["left_dir_x"], data["left_dir_z"]))
        right = np.degrees(np.arctan2(data["right_dir_x"], data["right_dir_z"]))
    return -(left + right) / 2


def valid_mask(t, angle, data, p):
    bad = (data["tracked"] != 1) | ~np.isfinite(angle)
    # atan2(inf, z) and atan2(0, 0) are finite, but neither is usable gaze.
    for eye in ("left", "right"):
        x, z = data[f"{eye}_dir_x"], data[f"{eye}_dir_z"]
        bad |= ~np.isfinite(x) | ~np.isfinite(z) | (np.hypot(x, z) < 1e-8)
        blink = data.get(f"blink_{eye}")
        if blink is not None:
            bad |= ~np.isfinite(blink) | (blink < 0) | (blink > p.blink_threshold)
    # Pad each invalid sample by pad_ms on both sides.
    pad = p.pad_ms / 1000
    padded = bad.copy()
    for i in np.flatnonzero(bad):
        lo = np.searchsorted(t, t[i] - pad, side="left")
        hi = np.searchsorted(t, t[i] + pad, side="right")
        padded[lo:hi] = True
    return ~padded


def runs(mask):
    """[(start, end_exclusive), ...] of contiguous True stretches."""
    m = np.concatenate([[False], mask, [False]]).astype(int)
    edges = np.flatnonzero(np.diff(m))
    return list(zip(edges[::2], edges[1::2]))


def continuous_runs(t, valid, dt):
    """Split on invalid rows AND absent frames; no event may cross a split."""
    gaps = np.flatnonzero(np.diff(t) > GAP_FACTOR * dt) + 1
    for a, b in runs(valid):
        cuts = [a, *gaps[(gaps > a) & (gaps < b)], b]
        yield from zip(cuts, cuts[1:])


def sg_velocity(angle, valid, dt, p, t=None):
    """Local polynomial derivative; actual times handle camera sampling jitter.

    Uniformly spaced samples use SciPy's equivalent SG filter. On irregular
    samples, fit the same polynomial/window at the measured timestamps instead
    of assigning every interval the median dt. Never interpolate across gaps.
    """
    vel = np.full_like(angle, np.nan)
    if t is None:
        t = np.arange(len(angle)) * dt
    for a, b in continuous_runs(t, valid, dt):
        if b - a >= p.sg_window:
            intervals = np.diff(t[a:b])
            if np.allclose(intervals, intervals[0], rtol=1e-6, atol=1e-10):
                vel[a:b] = savgol_filter(angle[a:b], p.sg_window, p.sg_polyorder,
                                        deriv=1, delta=float(intervals[0]))
            else:
                half = p.sg_window // 2
                for i in range(a, b):
                    start = min(max(a, i - half), b - p.sg_window)
                    end = start + p.sg_window
                    # Scale to nominal frame units to condition the fit; the
                    # linear coefficient / dt is the derivative in deg/s.
                    x = (t[start:end] - t[i]) / dt
                    coef = np.polynomial.polynomial.polyfit(x, angle[start:end], p.sg_polyorder)
                    vel[i] = coef[1] / dt
    return vel


# ---------------------------------------------------------------- 4–6: events

def detect_fast_phases(t, angle, vel, valid, p):
    phases = []
    with np.errstate(invalid="ignore"):
        fast = np.abs(vel) > p.fast_threshold
    for ra, rb in runs(valid):
        candidates = []
        for a, b in runs(fast[ra:rb]):
            a, b = a + ra, b + ra
            for sa, sb in runs(np.sign(vel[a:b]) > 0) + runs(np.sign(vel[a:b]) < 0):
                candidates.append((a + sa, a + sb, int(np.sign(vel[a + sa]))))
        candidates.sort()
        merged = []
        for a, b, d in candidates:   # merge within the same valid run only
            if merged and merged[-1][2] == d and t[a] - t[merged[-1][1] - 1] < p.merge_gap_ms / 1000:
                merged[-1] = (merged[-1][0], b, d)
            else:
                merged.append((a, b, d))
        for a, b, d in merged:
            pre, post = max(a - 1, ra), min(b, rb - 1)
            peak = vel[a:b][np.argmax(np.abs(vel[a:b]))]
            phases.append(dict(start=t[a], end=t[b - 1], i0=a, i1=b, direction=d,
                               peak_velocity=float(peak),
                               amplitude=float(angle[post] - angle[pre])))
    return sorted(phases, key=lambda f: f["start"])


def detect_slow_phases(t, angle, valid, fast_phases, p, velocity=None):
    """Keep fit diagnostics for all candidates; only qualified fits can form beats.

    A slope alone can hide several reversals or subthreshold saccades. R² checks
    how well a line describes the segment, and velocity sign agreement checks
    whether it actually drifts in that direction. These provisional gates need
    labelled data: curved/noisy true slow phases may also be rejected.
    """
    if velocity is None:
        velocity = sg_velocity(angle, valid, float(np.median(np.diff(t))), p, t=t)
    in_fast = np.zeros(len(t), dtype=bool)
    for f in fast_phases:
        in_fast[f["i0"]:f["i1"]] = True
    phases = []
    for a, b in runs(valid & ~in_fast):
        if t[b - 1] - t[a] < p.min_slow_s or b - a < 3:
            continue
        slope, intercept = np.polyfit(t[a:b], angle[a:b], 1)
        fitted = slope * t[a:b] + intercept
        residual = float(np.sum((angle[a:b] - fitted)**2))
        total = float(np.sum((angle[a:b] - np.mean(angle[a:b]))**2))
        r2 = max(0.0, 1 - residual / total) if total > 1e-12 else 0.0
        # Trapezoidal sample support weights avoid overweighting densely
        # sampled portions when camera timestamps jitter.
        weights = np.r_[np.diff(t[a:b]), 0] + np.r_[0, np.diff(t[a:b])]
        finite = np.isfinite(velocity[a:b])
        agreement = float(np.sum(weights * finite * (velocity[a:b] * slope > 0)) / weights.sum())
        reasons = []
        if abs(slope) < p.min_slow_velocity:
            reasons.append("too_slow")
        if r2 < p.min_slow_r2:
            reasons.append("poor_line_fit")
        if agreement < p.min_slow_direction_agreement:
            reasons.append("inconsistent_direction")
        if not np.all(finite):
            reasons.append("missing_velocity")
        phases.append(dict(start=t[a], end=t[b - 1], velocity=float(slope),
                           intercept=float(intercept), r2=r2, direction_agreement=agreement,
                           accepted=not reasons, rejection_reasons=reasons))
    return phases


def detect_beats(slow_phases, fast_phases, p):
    beats = []
    for s in slow_phases:
        if not s.get("accepted", True) or abs(s["velocity"]) < p.min_slow_velocity:
            continue
        direction = int(np.sign(s["velocity"]))
        for f in fast_phases:
            gap = f["start"] - s["end"]
            if gap < 0:
                continue
            if gap > p.beat_max_gap_s:
                break
            if f["direction"] == -direction:
                beats.append(dict(time=f["start"], direction=direction,
                                  slow_velocity=s["velocity"], slow=s, fast=f))
            # Only the immediately following fast phase can reset this slow
            # phase; do not skip an intervening same-direction movement.
            break
    return beats


# ---------------------------------------------------------------- 7–8: windows

def okn_windows(t, beats, p):
    """Window support for direction-consistent beats, not physiological onset/offset."""
    positive = []
    last_start = max(t[0], t[-1] - p.window_s)   # one window if the recording is short
    starts = list(np.arange(t[0], last_start + 1e-9, p.step_s))
    if last_start - starts[-1] > 1e-9:
        starts.append(last_start)  # cover a tail not aligned to step_s
    for start in starts:
        end = min(start + p.window_s, t[-1])
        dirs = [b["direction"] for b in beats if start <= b["time"] <= end]
        if len(dirs) >= p.min_beats:
            agree = max(dirs.count(1), dirs.count(-1)) / len(dirs)
            if agree >= p.min_agreement:
                direction = 1 if dirs.count(1) > dirs.count(-1) else -1
                positive.append((float(start), float(end), direction))
    return positive


def merge_windows(windows, beats):
    intervals = []
    for a, b, direction in windows:
        if intervals and direction == intervals[-1][2] and a <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], b)
        else:
            intervals.append([a, b, direction])
    out = []
    for a, b, direction in intervals:
        inside = [x for x in beats if a <= x["time"] <= b and x["direction"] == direction]
        out.append(dict(onset=a, offset=b, beats=len(inside), direction=direction,
                        median_slow_velocity=float(np.median([x["slow_velocity"] for x in inside]))))
    return out


def load_trial_mode(csv_path):
    """Trial mode from the JSON sidecar next to the CSV; okn if absent (pre-schema-3)."""
    meta_path = Path(csv_path).with_suffix(".json")
    if not meta_path.exists():
        return "okn"
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: could not read {meta_path.name}: {e}", file=sys.stderr)
        return "okn"
    return ((meta or {}).get("stimulus") or {}).get("trialMode") or "okn"


def stimulus_direction(data):
    d = data.get("stim_displacement_pt")
    if d is None or np.sum(np.isfinite(d)) < 2:
        return 0
    d = d[np.isfinite(d)]
    signs = set(np.sign(np.diff(d))) - {0}
    # A net displacement is misleading for a reversing stimulus. Do not claim
    # direction agreement without a time-resolved comparison in that case.
    return int(signs.pop()) if len(signs) == 1 else 0


# ---------------------------------------------------------------- driver

def analyse(data, p):
    validate_params(p)
    t = data["t_s"]
    if len(t) < 2 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise SessionError("need at least 2 finite, strictly increasing timestamps")
    dt = float(np.median(np.diff(t)))
    angle = eye_angle(data)
    valid = valid_mask(t, angle, data, p)
    vel = sg_velocity(angle, valid, dt, p, t=t)
    fast, slow, beats, windows, intervals = [], [], [], [], []
    # Segment the ENTIRE pipeline, not just filtering. A blink or missing frame
    # must also break slow/fast pairing, beat counts, and candidate intervals.
    for a, b in continuous_runs(t, valid, dt):
        if b - a < p.sg_window:
            continue
        ts, angles, velocities = t[a:b], angle[a:b], vel[a:b]
        mask = np.ones(b - a, dtype=bool)
        fs = detect_fast_phases(ts, angles, velocities, mask, p)
        ss = detect_slow_phases(ts, angles, mask, fs, p, velocity=velocities)
        bs = detect_beats(ss, fs, p)
        ws = okn_windows(ts, bs, p)
        intervals.extend(merge_windows(ws, bs))
        # Exposed indices continue to refer to the original recording.
        for f in fs:
            f["i0"] += a
            f["i1"] += a
        fast.extend(fs)
        slow.extend(ss)
        beats.extend(bs)
        windows.extend(ws)
    return dict(t=t, dt=dt, angle=angle, valid=valid, velocity=vel, fast=fast, slow=slow,
                beats=beats, windows=windows, intervals=intervals,
                stimulus=stimulus_direction(data), background=data.get("stim_bg_gray"))


def direction_name(d):
    return {1: "rightward", -1: "leftward"}.get(d, "unknown/static/reversing")


def print_report(r, p):
    t, valid = r["t"], r["valid"]
    span = t[-1] - t[0]
    right = sum(f["direction"] > 0 for f in r["fast"])
    print(f"samples:           {len(t)}")
    print(f"valid:             {100 * valid.mean():.1f}%")
    print(f"dt (median):       {1000 * r['dt']:.2f} ms")
    print(f"SG window:         {p.sg_window} samples (~{1000 * (p.sg_window - 1) * r['dt']:.0f} ms span), polyorder {p.sg_polyorder}")
    print(f"fast phases:       {len(r['fast'])} ({right} rightward, {len(r['fast']) - right} leftward)")
    accepted = sum(s["accepted"] for s in r["slow"])
    print(f"slow-phase fits:   {len(r['slow'])} ({accepted} accepted, {len(r['slow']) - accepted} rejected)")
    print(f"quality gates:     R² >= {p.min_slow_r2:g}, direction fraction >= {p.min_slow_direction_agreement:g} (provisional)")
    print(f"beats:             {len(r['beats'])}")
    if r["beats"]:
        v = np.median([b["slow_velocity"] for b in r["beats"]])
        print(f"median beat SPV:   {v:+.2f} deg/s")
        print(f"beat rate:         {len(r['beats']) / span:.2f} /s over {span:.2f} s")
    print(f"stimulus:          {direction_name(r['stimulus'])} (stim_displacement_pt)")
    print(f"note:              {SIGN_CAVEAT}")
    print("note:              candidate windows are not validated OKN onset/offset or a score")
    for s in r["slow"]:
        if not s["accepted"]:
            print(f"rejected slow fit: {s['start']:.3f}–{s['end']:.3f} s, "
                  f"R² {s['r2']:.2f}, direction fraction {s['direction_agreement']:.2f}: "
                  + ", ".join(s["rejection_reasons"]))
    for i, beat in enumerate(r["beats"], 1):
        s = beat["slow"]
        print(f"beat {i}:            slow {s['start']:.3f}–{s['end']:.3f} s, "
              f"reset {beat['fast']['start']:.3f}–{beat['fast']['end']:.3f} s, "
              f"SPV {s['velocity']:+.2f} deg/s, R² {s['r2']:.2f}, "
              f"direction fraction {s['direction_agreement']:.2f}")
    if not np.any(np.isfinite(r["velocity"])):
        print("note:              insufficient usable data for velocity estimation")
    if not r["intervals"]:
        print("no candidate OKN windows")
        return
    for k, iv in enumerate(r["intervals"], 1):
        if r["stimulus"] == 0:
            match = "stimulus direction unknown"
        elif iv["direction"] == r["stimulus"]:
            match = "matches stimulus"
        else:
            match = "OPPOSITE to stimulus"
        print(f"candidate window {k}: {iv['onset']:.2f}–{iv['offset']:.2f} s, {iv['beats']} beats, "
              f"slow phase {direction_name(iv['direction'])} "
              f"(median {iv['median_slow_velocity']:+.1f} deg/s), {match} [sign unverified]")


def plot(r, p, out_path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = r["t"]
    angle = np.where(r["valid"], r["angle"], np.nan)
    has_background = r.get("background") is not None
    fig, axes = plt.subplots(3 if has_background else 2, 1, sharex=True,
                             figsize=(11, 8 if has_background else 6.5),
                             gridspec_kw={"height_ratios": [2, 2, 1] if has_background else [1, 1]})
    ax1, ax2 = axes[:2]
    gaps = np.flatnonzero(np.diff(t) > GAP_FACTOR * r["dt"]) + 1
    plot_t = np.insert(t, gaps, np.nan)
    ax1.plot(plot_t, np.insert(angle, gaps, np.nan), color="0.3", linewidth=0.9, label="eye angle")
    seen = set()
    for s in r["slow"]:
        ts = np.array([s["start"], s["end"]])
        label = "accepted slow fit" if s["accepted"] else "rejected slow fit"
        ax1.plot(ts, s["velocity"] * ts + s["intercept"],
                 color="tab:blue" if s["accepted"] else "0.6",
                 linestyle="-" if s["accepted"] else "--",
                 linewidth=2 if s["accepted"] else 1,
                 label=label if label not in seen else None)
        seen.add(label)
    for i, beat in enumerate(r["beats"]):
        at = int(np.searchsorted(t, beat["time"]))
        ax1.scatter(t[at], angle[at], color="tab:green", marker="o", s=25, zorder=5,
                    label="accepted beat (reset start)" if i == 0 else None)
        ax1.annotate(str(i + 1), (t[at], angle[at]), xytext=(4, 6),
                     textcoords="offset points", color="tab:green", fontsize=7)
    for ax in (ax1, ax2):
        for i, f in enumerate(r["fast"]):
            ax.axvspan(f["start"], f["end"] + r["dt"], color="tab:red", alpha=0.25, linewidth=0,
                       label="fast phase" if i == 0 and ax is ax1 else None)
    for i, iv in enumerate(r["intervals"]):
        ax1.axvspan(iv["onset"], iv["offset"], ymin=0.95, ymax=1.0, color="tab:green",
                    label="candidate window support" if i == 0 else None)
    ax1.set_ylabel("horizontal eye angle (deg)\n+ = right, UNVERIFIED")
    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", fontsize="small", ncol=3)
    ax1.set_title(f"{title}\nprovisional OKN candidates; sign unverified, no score")
    ax2.plot(plot_t, np.insert(r["velocity"], gaps, np.nan), color="0.3", linewidth=0.9)
    for y in (p.fast_threshold, -p.fast_threshold):
        ax2.axhline(y, color="tab:red", linestyle="--", linewidth=0.8)
    ax2.set_ylabel("SG velocity (deg/s)")
    if has_background:
        axes[2].plot(plot_t, np.insert(r["background"], gaps, np.nan), color="tab:purple")
        axes[2].set_ylabel("scheduled background\nsRGB value")
        axes[2].set_ylim(-0.05, 1.05)
    axes[-1].set_xlabel("time since session start (s)")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="session CSV exported from the app")
    ap.add_argument("--plot", metavar="PNG", help="save a diagnostic plot")
    for f in fields(Params):
        ap.add_argument("--" + f.name.replace("_", "-"), type=type(f.default), default=f.default,
                        help=f"default: {f.default}")
    args = ap.parse_args(argv)
    p = Params(**{f.name: getattr(args, f.name) for f in fields(Params)})
    try:
        r = analyse(load_session(args.csv), p)
    except SessionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    mode = load_trial_mode(args.csv)
    print(f"session:           {args.csv}")
    print(f"mode:              {mode}")
    print_report(r, p)
    if args.plot:
        plot(r, p, args.plot, f"{Path(args.csv).name} · mode: {mode}")
        print(f"plot saved:        {args.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
