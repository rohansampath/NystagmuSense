#!/usr/bin/env python3
"""Plot a NystagmuSense gaze recording.

Usage:
    python3 scripts/plot_gaze.py path/to/NS_....csv [--out trace.png]

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
HORIZONTAL = {
    # column: (label, unit, panel)
    "left_dir_x": ("left eye direction x", "unitless", 0),
    "right_dir_x": ("right eye direction x", "unitless", 0),
    "lookat_x_m": ("lookAtPoint x", "m", 1),
}


class RecordingError(Exception):
    pass


def _num(value):
    """Empty field → NaN (missing data); anything else must parse as float."""
    value = value.strip()
    return math.nan if value == "" else float(value)


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
            cols = REQUIRED + gaze_cols
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


def plot(data, out_path, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise RecordingError("matplotlib is not installed (pip install matplotlib)") from None

    t = data["t_s"]
    panels = sorted({HORIZONTAL[c][2] for c in data if c in HORIZONTAL})
    fig, axes = plt.subplots(len(panels), 1, sharex=True, figsize=(11, 3.2 * len(panels)),
                             squeeze=False)
    spans = untracked_spans(t, data["tracked"])
    for ax, panel in zip(axes[:, 0], panels):
        units = set()
        for col, (label, unit, p) in HORIZONTAL.items():
            if p == panel and col in data:
                ax.plot(t, data[col], linewidth=1, label=label)
                units.add(unit)
        for i, (a, b) in enumerate(spans):
            ax.axvspan(a, b, color="0.85", zorder=0,
                       label="face not tracked" if i == 0 else None)
        ax.set_ylabel(f"x ({', '.join(sorted(units))})")
        ax.legend(loc="upper right", fontsize="small")
        ax.grid(alpha=0.3)
    axes[-1, 0].set_xlabel("time since session start (s)")
    axes[0, 0].set_title(f"{title}\nraw ARKit face-anchor coordinates, uncalibrated")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="session CSV exported from the app")
    ap.add_argument("--out", help="output PNG (default: next to the CSV)")
    args = ap.parse_args(argv)

    try:
        data = load_recording(args.csv)
        stats = compute_stats(data)
        print_stats(args.csv, stats, load_sidecar(args.csv))
        if stats["tracked"] == 0:
            print("warning: no samples have a tracked face; plot will be empty", file=sys.stderr)
        out = args.out or str(Path(args.csv).with_suffix(".png"))
        plot(data, out, Path(args.csv).name)
    except RecordingError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Saved plot: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
