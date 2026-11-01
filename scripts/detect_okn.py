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
3. Velocity: Savitzky-Golay first derivative, applied separately to each
   contiguous valid run (never across gaps).
4. Fast phases: runs where |velocity| exceeds a threshold; nearby same-direction
   runs are merged.
5. Slow phases: valid segments between fast phases; velocity = slope of a
   straight-line fit of angle vs time.
6. OKN beat: a slow phase followed shortly by an opposite-direction fast phase.
7. OKN windows: sliding windows with enough direction-consistent beats, merged
   into candidate onset/offset intervals.
8. Stimulus direction from the sign of change of stim_displacement_pt.

Thresholds were tuned on synthetic data only. Output is a candidate detection
for research, with no clinical or contrast-sensitivity meaning.
"""

import argparse
import csv
import math
import sys
from dataclasses import dataclass, fields

import numpy as np
from scipy.signal import savgol_filter

REQUIRED = ["t_s", "tracked", "left_dir_x", "left_dir_z", "right_dir_x", "right_dir_z"]
OPTIONAL = ["blink_left", "blink_right", "stim_displacement_pt"]
SIGN_CAVEAT = "eye-angle sign convention (+ = subject's right) is UNVERIFIED on device"


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
    beat_max_gap_s: float = 0.1      # slow-phase end → opposite fast-phase start
    window_s: float = 2.0
    step_s: float = 0.5
    min_beats: int = 2               # per window
    min_agreement: float = 0.75      # fraction of window beats sharing a direction


class SessionError(Exception):
    pass


# ---------------------------------------------------------------- loading

def load_session(path):
    """Return {column: np.ndarray} for the required and available optional columns."""
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in REQUIRED if c not in header]
            if missing:
                raise SessionError(f"missing required column(s): {', '.join(missing)}")
            cols = REQUIRED + [c for c in OPTIONAL if c in header]
            rows = {c: [] for c in cols}
            for line_no, row in enumerate(reader, start=2):
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
    if "blink_left" in data and "blink_right" in data:
        with np.errstate(invalid="ignore"):
            bad |= np.fmax(data["blink_left"], data["blink_right"]) > p.blink_threshold
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


def sg_velocity(angle, valid, dt, p):
    """SG first derivative per valid run; NaN where invalid or a run is too short."""
    vel = np.full_like(angle, np.nan)
    for a, b in runs(valid):
        if b - a >= p.sg_window:
            vel[a:b] = savgol_filter(angle[a:b], p.sg_window, p.sg_polyorder, deriv=1, delta=dt)
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


def detect_slow_phases(t, angle, valid, fast_phases, p):
    in_fast = np.zeros(len(t), dtype=bool)
    for f in fast_phases:
        in_fast[f["i0"]:f["i1"]] = True
    phases = []
    for a, b in runs(valid & ~in_fast):
        if t[b - 1] - t[a] < p.min_slow_s or b - a < 3:
            continue
        slope, intercept = np.polyfit(t[a:b], angle[a:b], 1)
        phases.append(dict(start=t[a], end=t[b - 1], velocity=float(slope),
                           intercept=float(intercept)))
    return phases


def detect_beats(slow_phases, fast_phases, p):
    beats = []
    for s in slow_phases:
        if abs(s["velocity"]) < p.min_slow_velocity:
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
                break
    return beats


# ---------------------------------------------------------------- 7–8: windows

def okn_windows(t, beats, p):
    """Sliding windows with enough direction-consistent beats."""
    positive = []
    last_start = max(t[0], t[-1] - p.window_s)   # one window if the recording is short
    for start in np.arange(t[0], last_start + 1e-9, p.step_s):
        end = start + p.window_s
        dirs = [b["direction"] for b in beats if start <= b["time"] < end]
        if len(dirs) >= p.min_beats:
            agree = max(dirs.count(1), dirs.count(-1)) / len(dirs)
            if agree >= p.min_agreement:
                positive.append((float(start), float(end)))
    return positive


def merge_windows(windows, beats):
    intervals = []
    for a, b in windows:
        if intervals and a <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], b)
        else:
            intervals.append([a, b])
    out = []
    for a, b in intervals:
        inside = [x for x in beats if a <= x["time"] < b]
        dirs = [x["direction"] for x in inside]
        direction = 1 if dirs.count(1) >= dirs.count(-1) else -1
        out.append(dict(onset=a, offset=b, beats=len(inside), direction=direction,
                        median_slow_velocity=float(np.median([x["slow_velocity"] for x in inside]))))
    return out


def stimulus_direction(data):
    d = data.get("stim_displacement_pt")
    if d is None or np.sum(np.isfinite(d)) < 2:
        return 0
    d = d[np.isfinite(d)]
    return int(np.sign(d[-1] - d[0]))


# ---------------------------------------------------------------- driver

def analyse(data, p):
    t = data["t_s"]
    dt = float(np.median(np.diff(t)))
    angle = eye_angle(data)
    valid = valid_mask(t, angle, data, p)
    vel = sg_velocity(angle, valid, dt, p)
    fast = detect_fast_phases(t, angle, vel, valid, p)
    slow = detect_slow_phases(t, angle, valid, fast, p)
    beats = detect_beats(slow, fast, p)
    windows = okn_windows(t, beats, p)
    return dict(t=t, dt=dt, angle=angle, valid=valid, velocity=vel, fast=fast, slow=slow,
                beats=beats, windows=windows, intervals=merge_windows(windows, beats),
                stimulus=stimulus_direction(data))


def direction_name(d):
    return {1: "rightward", -1: "leftward"}.get(d, "unknown/static")


def print_report(r, p):
    t, valid = r["t"], r["valid"]
    span = t[-1] - t[0]
    right = sum(f["direction"] > 0 for f in r["fast"])
    print(f"samples:           {len(t)}")
    print(f"valid:             {100 * valid.mean():.1f}%")
    print(f"dt (median):       {1000 * r['dt']:.2f} ms")
    print(f"SG window:         {p.sg_window} samples ({1000 * p.sg_window * r['dt']:.0f} ms), polyorder {p.sg_polyorder}")
    print(f"fast phases:       {len(r['fast'])} ({right} rightward, {len(r['fast']) - right} leftward)")
    print(f"slow phases:       {len(r['slow'])}")
    print(f"beats:             {len(r['beats'])}")
    if r["beats"]:
        v = np.median([b["slow_velocity"] for b in r["beats"]])
        print(f"median beat SPV:   {v:+.2f} deg/s")
        print(f"beat rate:         {len(r['beats']) / span:.2f} /s over {span:.2f} s")
    print(f"stimulus:          {direction_name(r['stimulus'])} (stim_displacement_pt)")
    print(f"note:              {SIGN_CAVEAT}")
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
        print(f"candidate OKN {k}:   {iv['onset']:.2f}–{iv['offset']:.2f} s, {iv['beats']} beats, "
              f"slow phase {direction_name(iv['direction'])} "
              f"(median {iv['median_slow_velocity']:+.1f} deg/s), {match} [sign unverified]")


def plot(r, p, out_path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = r["t"]
    angle = np.where(r["valid"], r["angle"], np.nan)
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(11, 6.5))
    ax1.plot(t, angle, color="0.3", linewidth=0.9, label="eye angle")
    for i, s in enumerate(r["slow"]):
        ts = np.array([s["start"], s["end"]])
        ax1.plot(ts, s["velocity"] * ts + s["intercept"], color="tab:blue", linewidth=2,
                 label="slow-phase fit" if i == 0 else None)
    for ax in (ax1, ax2):
        for i, f in enumerate(r["fast"]):
            ax.axvspan(f["start"], f["end"] + r["dt"], color="tab:red", alpha=0.25, linewidth=0,
                       label="fast phase" if i == 0 and ax is ax1 else None)
    for i, iv in enumerate(r["intervals"]):
        ax1.axvspan(iv["onset"], iv["offset"], ymin=0.95, ymax=1.0, color="tab:green",
                    label="candidate OKN" if i == 0 else None)
    ax1.set_ylabel("horizontal eye angle (deg)\n+ = right, UNVERIFIED")
    ax1.legend(loc="upper right", fontsize="small")
    ax1.set_title(f"{title}\ncandidate OKN detection on raw, uncalibrated ARKit signals")
    ax2.plot(t, r["velocity"], color="0.3", linewidth=0.9)
    for y in (p.fast_threshold, -p.fast_threshold):
        ax2.axhline(y, color="tab:red", linestyle="--", linewidth=0.8)
    ax2.set_ylabel("SG velocity (deg/s)")
    ax2.set_xlabel("time since session start (s)")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
    fig.tight_layout()
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
    if p.sg_window % 2 == 0 or p.sg_window <= p.sg_polyorder:
        ap.error("--sg-window must be odd and greater than --sg-polyorder")

    try:
        r = analyse(load_session(args.csv), p)
    except SessionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"session:           {args.csv}")
    print_report(r, p)
    if args.plot:
        plot(r, p, args.plot, args.csv.rsplit("/", 1)[-1])
        print(f"plot saved:        {args.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
