#!/usr/bin/env python3
"""Build the Pilot 05 manifest: technical status and eligibility (no detector, no labels).

    python3 analysis/pilot_05/build_manifest.py [--trials-dir trials] [--check]

Rules (docs/PILOT_05.md):
- Technical failure: name/metadata disagreement; not a regular OKN trial;
  stripe speed not the protocol 126 pt/s; nominal contrast missing, not a
  Pilot 05 level, or disagreeing with the C### name field; background/bar code
  values not those of contrast_model.py for that level; mean relative
  luminance not 0.5; under 570 samples; under 90 % face-tracked; timestamps
  not finite and strictly increasing; any sidecar issue. Distance problems
  are notes.
- Primary: per participant × contrast × direction, the first 2 technically
  valid recordings in trial-number order. Later valid ones are "extra";
  recordings moved to trials/_excluded_P05/ are "excluded".
- Role: exploratory_contrast. Pilot 05 has no held-out split; it is a
  feasibility study.
"""

import argparse
import csv
import io
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contrast_model  # noqa: E402

ROOT = HERE.parents[1]
MANIFEST = HERE / "manifest.csv"
CODE = "P05"
PARTICIPANTS = ("P01", "P02", "P03")
NAME_RE = re.compile(r"P05-(P\d\d)_T(\d+)_OKN_(LEFT|RIGHT)_C(\d{3})_(\d{8}_\d{6})")
REPEATS = 2
SPEED = 126
MIN_SAMPLES, MIN_TRACKED = 570, 0.90
FIELDS = ["trial_id", "participant", "trial_number", "contrast_percent", "direction", "folder", "technical_status",
          "technical_notes", "eligibility", "exclusion_reason", "role"]


def recordings(trials_dir):
    trials_dir = Path(trials_dir)
    excluded = trials_dir / f"_excluded_{CODE}"
    found = [(trials_dir, d) for d in trials_dir.glob(f"{CODE}-*") if d.is_dir()]
    found += [(excluded, d) for d in excluded.glob(f"{CODE}-*") if d.is_dir()]
    return sorted(found, key=lambda fd: fd[1].name)


def technical_check(folder):
    """(problems, notes) for one recording folder."""
    name = folder.name
    m = NAME_RE.fullmatch(name)
    if not m:
        return ["name is not a P05 recording name"], []
    problems, notes = [], []
    try:
        meta = json.loads((folder / f"{name}.json").read_text())
        with open(folder / f"{name}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, json.JSONDecodeError) as e:
        return [f"unreadable: {e}"], []
    if not isinstance(meta, dict) or not isinstance(meta.get("stimulus"), dict):
        return ["metadata and stimulus must be JSON objects"], []
    stim = meta["stimulus"]
    participant, direction, percent = m[1], m[3], int(m[4])
    if participant not in PARTICIPANTS:
        problems.append("participant is not in the P05 protocol")
    expected = {"experimentID": CODE, "recordingName": name, "participantID": participant,
                "trialNumber": int(m[2]), "directionCode": direction}
    for key, want in expected.items():
        if meta.get(key) != want:
            problems.append(f"metadata {key}={meta.get(key)!r} disagrees with name")
    if stim.get("trialMode") != "okn":
        problems.append(f"trialMode {stim.get('trialMode')!r} is not regular OKN")
    if {"rightward": "RIGHT", "leftward": "LEFT"}.get(stim.get("direction")) != direction:
        problems.append("stimulus.direction disagrees with name")
    if stim.get("speedPointsPerSecond") != SPEED:
        problems.append(f"stripe speed {stim.get('speedPointsPerSecond')!r} is not {SPEED} pt/s")
    for key, want in (("stripeWidthRatio", 0.02), ("pitchToWidthRatio", 2.4)):
        if stim.get(key) != want:
            problems.append(f"stimulus {key} is not the protocol value {want}")
    c = stim.get("michelsonContrast")
    if type(c) not in (int, float) or not math.isfinite(c):
        problems.append("no nominal contrast in metadata")
    else:
        if not math.isclose(c, percent / 100, rel_tol=0, abs_tol=1e-9):
            problems.append(f"michelsonContrast {c!r} disagrees with name C{percent:03d}")
        if percent not in contrast_model.LEVELS:
            problems.append(f"contrast {percent} % is not a Pilot 05 level")
        else:
            bg, bar = contrast_model.codes(percent / 100)
            got = (stim.get("fixedBackgroundGray"), stim.get("stripeGray"))
            if not all(type(v) in (int, float) and math.isfinite(v) for v in got) or abs(got[0] - bg) > 1e-9 or abs(got[1] - bar) > 1e-9:
                problems.append("background/bar code values are not the contrast model's for this level")
    if stim.get("meanRelativeLuminance") != contrast_model.MEAN:
        problems.append(f"meanRelativeLuminance {stim.get('meanRelativeLuminance')!r} is not {contrast_model.MEAN}")
    if len(rows) < MIN_SAMPLES:
        problems.append(f"only {len(rows)} samples")
    try:
        t = [float(r["t_s"]) for r in rows]
        tracked = sum(r["tracked"] == "1" for r in rows) / max(len(rows), 1)
    except (KeyError, ValueError, TypeError):
        return problems + ["missing or malformed timing/tracking columns"], notes
    if any(not math.isfinite(x) for x in t) or any(b <= a for a, b in zip(t, t[1:])):
        problems.append("timestamps not finite and strictly increasing (duplicate or out of order)")
    if tracked < MIN_TRACKED:
        problems.append(f"only {tracked:.0%} face-tracked")
    if meta.get("issues"):
        problems.append("sidecar issues: " + "; ".join(map(str, meta["issues"])))
    fd = meta.get("faceDistance")
    if not isinstance(fd, dict):
        notes.append("no distance data")
    else:
        if fd.get("check") != "passed":
            notes.append(f"distance check {fd.get('check')}")
        if fd.get("fractionOutsideRange", 0) > 0.05:
            notes.append(f"distance outside 25-30 cm for {fd['fractionOutsideRange']:.0%} of the trial")
    return problems, notes


def build(trials_dir):
    rows = []
    for parent, folder in recordings(trials_dir):
        m = NAME_RE.fullmatch(folder.name)
        problems, notes = technical_check(folder)
        rows.append(dict(trial_id=folder.name, participant=m[1] if m else "", trial_number=int(m[2]) if m else 0,
                         contrast_percent=int(m[4]) if m else "", direction=m[3] if m else "",
                         folder=str(Path(parent).relative_to(trials_dir)) if parent != Path(trials_dir) else ".",
                         technical_status="fail" if problems else "pass", technical_notes="; ".join(problems + notes),
                         eligibility="", exclusion_reason="", role=""))
    cells = {}
    for r in sorted(rows, key=lambda r: r["trial_number"]):
        if r["folder"] != ".":
            r["eligibility"], r["exclusion_reason"] = "excluded", f"moved to _excluded_{CODE} by the experimenter"
        elif r["technical_status"] == "fail":
            r["eligibility"], r["exclusion_reason"] = "excluded", "technical failure"
        else:
            cell = cells.setdefault((r["participant"], r["contrast_percent"], r["direction"]), [])
            if len(cell) < REPEATS:
                cell.append(r)
                r["eligibility"], r["role"] = "primary", "exploratory_contrast"
            else:
                r["eligibility"], r["exclusion_reason"] = "extra", "beyond the planned repeats for its cell"
    return sorted(rows, key=lambda r: (r["participant"], r["trial_number"])), cells


def shortfalls(cells):
    """Planned cells below REPEATS, for every participant with any recording."""
    people = sorted({p for p, _, _ in cells})
    return [f"{p} C{c:03d} {d}: {len(cells.get((p, c, d), []))}/{REPEATS}"
            for p in people for c in contrast_model.LEVELS for d in ("LEFT", "RIGHT")
            if len(cells.get((p, c, d), [])) < REPEATS]


def render(rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--output", type=Path, default=MANIFEST)
    ap.add_argument("--check", action="store_true", help="only verify the saved manifest is reproduced exactly")
    ap.add_argument("--force", action="store_true", help="overwrite a different saved manifest")
    args = ap.parse_args(argv)
    rows, cells = build(args.trials_dir)
    if not rows:
        print(f"no Pilot 05 recordings in {args.trials_dir}; nothing written", file=sys.stderr)
        return 1
    text = render(rows)
    if args.check or (args.output.exists() and not args.force):
        if not args.output.exists():
            print(f"error: {args.output} does not exist", file=sys.stderr)
            return 1
        if args.output.read_text() != text:
            print(f"error: {args.output} differs from what the recordings give now. "
                  "Use --force only if you mean to change it.", file=sys.stderr)
            return 1
        print(f"{args.output} is reproduced exactly")
        return 0
    args.output.write_text(text)
    counts = {}
    for r in rows:
        counts[r["eligibility"]] = counts.get(r["eligibility"], 0) + 1
    print(f"wrote {args.output}: " + ", ".join(f"{e} {n}" for e, n in sorted(counts.items())))
    short = shortfalls(cells)
    if short:
        print("cells below the planned repeats: " + "; ".join(short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
