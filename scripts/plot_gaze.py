#!/usr/bin/env python3
"""Plot raw NystagmuSense schema-v1 JSON; never smooth or interpolate."""
import argparse
import json
import math
from pathlib import Path
import statistics


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_recording(path):
    with Path(path).open() as stream:
        recording = json.load(stream)
    if not isinstance(recording, dict) or recording.get("schemaVersion") != 1:
        raise ValueError("Expected a NystagmuSense schemaVersion 1 recording.")
    if recording.get("units") != "meters":
        raise ValueError("Expected face-local estimates in meters.")
    samples = recording.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Recording contains no gaze samples.")
    times, xs, ys = [], [], []
    invalid = 0
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or not number(sample.get("timestamp")):
            raise ValueError(f"Frame {index} has no finite timestamp.")
        timestamp = sample["timestamp"]
        if times and timestamp < times[-1]:
            raise ValueError(f"Timestamps decrease at frame {index}; refusing to reorder data.")
        times.append(timestamp)
        valid = (sample.get("valid") is True and sample.get("faceTracked") is True
                 and all(number(sample.get(axis)) for axis in ("x", "y", "z")))
        invalid += not valid
        xs.append(sample["x"] if valid else math.nan)
        ys.append(sample["y"] if valid else math.nan)
    if invalid == len(samples):
        raise ValueError(f"No valid gaze samples ({invalid} invalid frames).")
    return recording, [t - times[0] for t in times], xs, ys, invalid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, help="PNG path; default: beside JSON")
    parser.add_argument("--show", action="store_true", help="Also open an interactive plot")
    args = parser.parse_args()
    try:
        recording, times, xs, ys, invalid = read_recording(args.session)
        import matplotlib
        if not args.show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        duration = times[-1]
        rate = (len(times) - 1) / duration if duration > 0 else 0
        deltas = [b - a for a, b in zip(times, times[1:]) if b > a]
        print(f"Frames: {len(times)}; valid: {len(times) - invalid}; invalid/missing gaze: {invalid}")
        print(f"Frame coverage: {duration:.3f} s; observed frame rate: {rate:.2f} Hz")
        if deltas:
            print(f"Median frame interval: {statistics.median(deltas):.4f} s; max: {max(deltas):.4f} s")
        print("Frames absent from the export cannot be counted as dropped without a reference rate.")
        print(f"Stop reason: {recording.get('stopReason', 'unspecified')}")
        fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6), layout="constrained")
        for ax, values, label in zip(axes, (xs, ys), ("Horizontal x", "Vertical y")):
            # Points only: do not connect across unobserved intervals.
            ax.plot(times, values, ".", markersize=2)
            ax.set_ylabel(f"{label} (m)")
            ax.grid(alpha=0.25)
        axes[-1].set_xlabel("Elapsed time from first recorded AR frame (s)")
        fig.suptitle("Raw ARKit estimated look-at point · face-local coordinates\n"
                     + str(recording.get("deviceModel", "Unknown device")))
        output = args.output or args.session.with_suffix(".png")
        fig.savefig(output, dpi=160)
        print(f"Saved {output}")
        if args.show:
            plt.show()
        plt.close(fig)
    except ImportError:
        parser.exit(1, "error: matplotlib is required. Install with: python3 -m pip install matplotlib\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
