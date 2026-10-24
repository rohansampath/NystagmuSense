#!/usr/bin/env python3
"""Plot a NystagmuSense gaze recording.

Usage:
    python3 scripts/plot_gaze.py path/to/NS_....csv [--output trace.png] [--show]

Reads the CSV exported by the app (and the .json sidecar next to it, if
present), prints basic session statistics, and saves a PNG of the raw
horizontal gaze signals versus time. Values are plotted exactly as recorded:
ARKit face-anchor coordinates, uncalibrated. This script does not detect OKN.
"""

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

REQUIRED = ["t_s", "tracked"]
SIGNALS = {
    # column: (label, unit, panel)
    "left_dir_x": ("left eye direction x", "unitless", 0),
    "right_dir_x": ("right eye direction x", "unitless", 0),
    "lookat_x_m": ("lookAtPoint x", "m", 1),
    "lookat_y_m": ("lookAtPoint y", "m", 2),
}
PANEL_TITLES = {0: "horizontal eye direction", 1: "horizontal lookAt", 2: "vertical lookAt"}
HORIZONTAL = [c for c, (_, _, panel) in SIGNALS.items() if panel in (0, 1)]
# Lines are broken where consecutive frames are further apart than this
# multiple of the median frame interval, so unobserved time is never drawn.
GAP_FACTOR = 2.5


class RecordingError(Exception):
    pass


def _num(value):
    """Empty or non-finite field → NaN (missing data); anything else must parse as float."""
    value = value.strip()
    if value == "":
        return math.nan
    number = float(value)
    return number if math.isfinite(number) else math.nan


def load_recording(path):
    """Return {column: [float, ...]} for the required and horizontal columns."""
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in REQUIRED if c not in header]
            if missing:
                raise RecordingError(f"missing required column(s): {', '.join(missing)}")
            gaze_cols = [c for c in HORIZONTAL if c in header]
            if not gaze_cols:
                raise RecordingError("no horizontal gaze columns found "
                                     f"(expected one of {', '.join(HORIZONTAL)})")
            cols = REQUIRED + gaze_cols + [c for c in SIGNALS if c in header and c not in gaze_cols]
            data = {c: [] for c in cols}
            for line_no, row in enumerate(reader, start=2):
                try:
                    for c in cols:
                        data[c].append(_num(row[c] or ""))
                except (ValueError, TypeError) as e:
                    raise RecordingError(f"line {line_no}: malformed value ({e})") from None
    except OSError as e:
        raise RecordingError(str(e)) from None
    if not data["t_s"]:
        raise RecordingError("recording contains no samples")
    t = data["t_s"]
    for i, value in enumerate(t):
        if math.isnan(value):
            raise RecordingError(f"t_s missing or non-finite at data row {i + 1}")
    for i in range(1, len(t)):
        if not t[i] >= t[i - 1]:
            raise RecordingError(f"t_s decreases at data row {i + 1}; refusing to reorder data")
    return data


def compute_stats(data):
    t = data["t_s"]
    tracked = [v == 1 for v in data["tracked"]]
    dts = [b - a for a, b in zip(t, t[1:])]
    span = t[-1] - t[0]
    return {
        "samples": len(t),
        "tracked": sum(tracked),
        "tracked_pct": 100 * sum(tracked) / len(t),
        "span_s": span,
        "mean_rate_hz": (len(t) - 1) / span if span > 0 else None,
        "median_dt_ms": 1000 * statistics.median(dts) if dts else None,
        "max_gap_ms": 1000 * max(dts) if dts else None,
    }


def untracked_spans(t, tracked):
    """[(start, end), ...] time ranges where tracked == 0."""
    spans, start = [], None
    for i, ok in enumerate(tracked):
        if ok != 1 and start is None:
            start = t[i]
        elif ok == 1 and start is not None:
            spans.append((start, t[i]))
            start = None
    if start is not None:
        spans.append((start, t[-1]))
    return spans


def break_gaps(t, values, max_dt):
    """Insert NaN between frames further apart than max_dt so lines don't bridge them."""
    out_t, out_v = [], []
    for i, (ti, vi) in enumerate(zip(t, values)):
        if i and ti - t[i - 1] > max_dt:
            out_t.append((ti + t[i - 1]) / 2)
            out_v.append(math.nan)
        out_t.append(ti)
        out_v.append(vi)
    return out_t, out_v


def load_sidecar(csv_path):
    meta = Path(csv_path).with_suffix(".json")
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: could not read {meta.name}: {e}", file=sys.stderr)
        return None


def print_stats(path, stats, meta):
    print(f"Recording: {path}")
    if meta:
        dev = meta.get("device", {})
        print(f"  device:        {dev.get('model', '?')} ({dev.get('systemName', '')} {dev.get('systemVersion', '')})")
        print(f"  session:       {meta.get('sessionID', '?')}")
        for issue in meta.get("issues", []):
            print(f"  issue:         {issue}")
    print(f"  samples:       {stats['samples']}")
    print(f"  face tracked:  {stats['tracked']} ({stats['tracked_pct']:.1f}%)")
    print(f"  span:          {stats['span_s']:.3f} s")
    if stats["mean_rate_hz"] is not None:
        print(f"  mean rate:     {stats['mean_rate_hz']:.1f} Hz")
        print(f"  median dt:     {stats['median_dt_ms']:.1f} ms")
        print(f"  max gap:       {stats['max_gap_ms']:.1f} ms")


def plot(data, out_path, title, show=False):
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise RecordingError("matplotlib is not installed (pip install matplotlib)") from None

    t = data["t_s"]
    dts = [b - a for a, b in zip(t, t[1:]) if b > a]
    max_dt = GAP_FACTOR * statistics.median(dts) if dts else math.inf
    panels = sorted({SIGNALS[c][2] for c in data if c in SIGNALS})
    fig, axes = plt.subplots(len(panels), 1, sharex=True, figsize=(11, 3.2 * len(panels)),
                             squeeze=False)
    spans = untracked_spans(t, data["tracked"])
    for ax, panel in zip(axes[:, 0], panels):
        units = set()
        for col, (label, unit, p) in SIGNALS.items():
            if p == panel and col in data:
                ax.plot(*break_gaps(t, data[col], max_dt), linewidth=1, label=label)
                units.add(unit)
        for i, (a, b) in enumerate(spans):
            ax.axvspan(a, b, color="0.85", zorder=0,
                       label="face not tracked" if i == 0 else None)
        ax.set_ylabel(f"{PANEL_TITLES[panel]}\n({', '.join(sorted(units))})")
        ax.legend(loc="upper right", fontsize="small")
        ax.grid(alpha=0.3)
    axes[-1, 0].set_xlabel("time since session start (s)")
    axes[0, 0].set_title(f"{title}\nraw ARKit face-anchor coordinates, uncalibrated")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="session CSV exported from the app")
    ap.add_argument("--output", "--out", dest="out", help="output PNG (default: next to the CSV)")
    ap.add_argument("--show", action="store_true", help="also open an interactive window")
    args = ap.parse_args(argv)

    try:
        data = load_recording(args.csv)
        stats = compute_stats(data)
        print_stats(args.csv, stats, load_sidecar(args.csv))
        if stats["tracked"] == 0:
            raise RecordingError("no samples have a tracked face; nothing to plot (failed capture)")
        out = args.out or str(Path(args.csv).with_suffix(".png"))
        plot(data, out, Path(args.csv).name, show=args.show)
    except RecordingError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Saved plot: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
