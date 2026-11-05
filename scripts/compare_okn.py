#!/usr/bin/env python3
"""Run the unchanged SG baseline and experimental hybrid on identical inputs.

    python3 scripts/compare_okn.py trials/*/*.csv --output-dir analysis/hybrid_comparison

Writes a side-by-side diagnostic PNG per CSV and summary.json with source
SHA-256, both parameter sets, reset times, counts, SPV, and candidate intervals.
Counts are detector outputs, NOT accuracy. For precision/recall, use completely
reviewed annotations with evaluate_okn.py --detector both. Raw files are read-only.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

import detect_okn
import hybrid_okn


def summary(result):
    return dict(fast_phases=len(result["fast"]), beats=len(result["beats"]),
                accepted_slow_phases=sum(s["accepted"] for s in result["slow"]),
                positive_windows=len(result["windows"]),
                reset_times_s=[float(f["start"]) for f in result["fast"]],
                reset_durations_s=[float(f["end"] - f["start"]) for f in result["fast"]],
                median_beat_spv_deg_s=(float(np.median([b["slow_velocity"] for b in result["beats"]]))
                                       if result["beats"] else None),
                intervals=result["intervals"])


def plot_comparison(results, p, output, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, sharex=True, sharey="row", figsize=(15, 8))
    for col, (method, r) in enumerate(results.items()):
        angle_ax, vel_ax = axes[:, col]
        t, angle = r["t"], np.where(r["valid"], r["angle"], np.nan)
        gaps = np.flatnonzero(np.diff(t) > detect_okn.GAP_FACTOR * r["dt"]) + 1
        times = np.insert(t, gaps, np.nan)
        angle_ax.plot(times, np.insert(angle, gaps, np.nan), color="0.3", lw=0.8, label="raw angle")
        for a, b in detect_okn.runs(~r["valid"]):
            for ax in (angle_ax, vel_ax):
                ax.axvspan(t[a], t[min(b, len(t) - 1)], color="0.85", zorder=0)
        for seg in r.get("segments", []):
            a, b = seg["i0"], seg["i1"] - 1
            angle_ax.plot(t[[a, b]], angle[[a, b]], color="tab:orange", lw=0.8, alpha=0.6)
        for s in r["slow"]:
            ts = np.array([s["start"], s["end"]])
            angle_ax.plot(ts, s["velocity"] * ts + s["intercept"],
                          color="tab:blue" if s["accepted"] else "0.6",
                          ls="-" if s["accepted"] else "--", lw=1.6)
        for f in r["fast"]:
            # A one-sample baseline event still needs visible sample support.
            end = max(f["end"], min(t[-1], f["start"] + r["dt"]))
            for ax in (angle_ax, vel_ax):
                ax.axvspan(f["start"], end, color="tab:red", alpha=0.2, lw=0)
        for beat in r["beats"]:
            i = np.searchsorted(t, beat["time"])
            angle_ax.scatter(t[i], angle[i], color="tab:green", s=18, zorder=5)
        vel_ax.plot(times, np.insert(r["velocity"], gaps, np.nan), color="0.3", lw=0.8)
        for threshold in (p.fast_threshold, -p.fast_threshold):
            vel_ax.axhline(threshold, color="tab:red", ls="--", lw=0.8)
        label = "SG baseline (unchanged)" if method == "sg" else "Hybrid (experimental)"
        angle_ax.set_title(f"{label}\n{len(r['fast'])} resets · {len(r['beats'])} beats · "
                           f"{len(r['windows'])} positive windows")
        angle_ax.set_ylabel("horizontal eye angle (deg; sign unverified)")
        vel_ax.set_ylabel("SG velocity (deg/s)" if method == "sg"
                          else "slow SG / reset raw velocity (deg/s)")
        vel_ax.set_xlabel("time since session start (s)")
        for ax in (angle_ax, vel_ax):
            ax.grid(alpha=0.25)
    fig.suptitle(title + "\nSame raw samples and shared thresholds; counts do not measure accuracy", fontsize=11)
    fig.text(0.5, 0.015, "grey shading: invalid · orange: raw-angle segmentation · red: resets · "
             "blue: accepted slow fits · dashed grey: rejected fits · green dots: paired beats", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(output, dpi=150)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--no-plots", action="store_true", help="write just summary.json")
    for cls, prefix in ((detect_okn.Params, ""), (hybrid_okn.HybridParams, "cp-")):
        for f in fields(cls):
            ap.add_argument("--" + prefix + f.name.replace("_", "-"),
                            type=type(f.default), default=f.default, help=f"default: {f.default}")
    args = ap.parse_args(argv)
    p = detect_okn.Params(**{f.name: getattr(args, f.name) for f in fields(detect_okn.Params)})
    hp = hybrid_okn.HybridParams(**{f.name: getattr(args, "cp_" + f.name)
                                   for f in fields(hybrid_okn.HybridParams)})
    try:
        detect_okn.validate_params(p)
        hybrid_okn.validate_params(hp)
        if len({path.stem for path in args.csv}) != len(args.csv):
            raise detect_okn.SessionError("recording stems must be unique (avoid overwriting comparison plots)")
        sources = {candidate.resolve() for path in args.csv for candidate in (path, path.with_suffix(".json"))}
        if (args.output_dir / "summary.json").resolve() in sources:
            raise detect_okn.SessionError("output summary would overwrite source metadata; choose another output directory")
        sessions = [(path, detect_okn.load_session(path)) for path in args.csv]
        args.output_dir.mkdir(parents=True, exist_ok=True)
        report = dict(schema_version=1, shared_params=asdict(p), hybrid_params=asdict(hp),
                      note="Experimental comparison; counts are not accuracy. Labels required for scoring. "
                           "merge_gap_ms applies only to SG; hybrid merges adjacent steep segments.", trials=[])
        for path, data in sessions:
            results = {method: detect_okn.analyse(data, p, method=method, hybrid_params=hp)
                       for method in ("sg", "hybrid")}
            mode = detect_okn.load_trial_mode(path)
            row = dict(recording=path.stem, mode=mode,
                       samples=len(data["t_s"]), valid_fraction=float(results["sg"]["valid"].mean()),
                       source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       **{method: summary(r) for method, r in results.items()})
            report["trials"].append(row)
            if not args.no_plots:
                plot_comparison(results, p, args.output_dir / f"{path.stem}_comparison.png",
                                f"{path.name} · mode: {mode}")
            print(f"{path.stem}: SG {row['sg']['fast_phases']} resets / {row['sg']['beats']} beats; "
                  f"hybrid {row['hybrid']['fast_phases']} resets / {row['hybrid']['beats']} beats")
        (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(f"comparison saved: {args.output_dir}")
    except (detect_okn.SessionError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
