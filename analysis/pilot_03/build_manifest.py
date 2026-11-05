#!/usr/bin/env python3
"""Build the frozen Pilot 03 manifest: eligibility and development/evaluation split.

    python3 analysis/pilot_03/build_manifest.py [--trials-dir trials] [--check]

Uses only each recording's file name, JSON sidecar and CSV timing/tracking.
Labels and detector output are never read, so the split can't be tuned to
either.

Rules (documented in analysis/pilot_03/README.md):
- Technical failure: metadata disagrees with the file name, wrong stimulus for
  P03 (background not fixed at 1, stripes moving in a still trial or still in
  a moving one), fewer than 570 samples (95 % of 10 s at 60 Hz), under 90 %
  of samples face-tracked, non-increasing timestamps, or any sidecar issue.
  Distance drift and a bypassed distance check are recorded as notes.
- Primary dataset: per participant × condition × direction, the first N
  technically valid recordings in trial-number order (N = 4 OKN per
  direction, 3 FIXMOVE per direction, 6 FIXSTILL). Later valid recordings
  are "extra" (kept for exploratory use). Recordings the experimenter moved
  to trials/_excluded_P03/ are "excluded".
- Split: within each primary cell, a seeded random sample goes to evaluation
  (1 per OKN/FIXMOVE direction, 2 FIXSTILL; 6 per participant, 12 total);
  the rest is development (28). Whole recordings only.
"""

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).resolve().parent / "manifest.csv"
SEED = 20261105
NAME_RE = re.compile(r"P03-(P0\d)_T(\d+)_(OKN|FIXMOVE|FIXSTILL)_(RIGHT|LEFT|NONE)_(\d{8}_\d{6})")
MODES = {"okn": "OKN", "fixationMovingStripes": "FIXMOVE", "fixationStillStripes": "FIXSTILL"}
PER_CELL = {"OKN": 4, "FIXMOVE": 3, "FIXSTILL": 6}
EVAL_PER_CELL = {"OKN": 1, "FIXMOVE": 1, "FIXSTILL": 2}
MIN_SAMPLES, MIN_TRACKED = 570, 0.90
FIELDS = ["trial_id", "participant", "trial_number", "condition", "direction", "folder",
          "technical_status", "technical_notes", "eligibility", "exclusion_reason", "split"]


def recordings(trials_dir):
    """(folder, csv path) for every P03 recording, including experimenter exclusions."""
    trials_dir = Path(trials_dir)
    found = [(trials_dir, d) for d in trials_dir.glob("P03-*") if d.is_dir()]
    found += [(trials_dir / "_excluded_P03", d) for d in (trials_dir / "_excluded_P03").glob("P03-*") if d.is_dir()]
    return sorted(found, key=lambda fd: fd[1].name)


def technical_check(folder):
    """(problems, notes) for one recording folder."""
    name = folder.name
    m = NAME_RE.fullmatch(name)
    if not m:
        return ["name is not a P03 recording name"], []
    problems, notes = [], []
    try:
        meta = json.loads((folder / f"{name}.json").read_text())
        rows = list(csv.DictReader(open(folder / f"{name}.csv", newline="")))
    except (OSError, json.JSONDecodeError) as e:
        return [f"unreadable: {e}"], []
    stim = meta.get("stimulus") or {}
    condition, direction = m[3], m[4]
    expected = {"recordingName": name, "participantID": m[1], "trialNumber": int(m[2]), "directionCode": direction}
    for key, want in expected.items():
        if meta.get(key) != want:
            problems.append(f"metadata {key}={meta.get(key)!r} disagrees with name")
    if MODES.get(stim.get("trialMode")) != condition:
        problems.append(f"trialMode {stim.get('trialMode')!r} disagrees with name")
    if direction != "NONE" and {"rightward": "RIGHT", "leftward": "LEFT"}.get(stim.get("direction")) != direction:
        problems.append("stimulus.direction disagrees with name")
    if stim.get("fixedBackgroundGray") != 1:
        problems.append("background not fixed at 1 (not the P03 stimulus)")
    if (stim.get("speedPointsPerSecond") == 0) != (condition == "FIXSTILL"):
        problems.append("stripe speed doesn't match the condition")
    if len(rows) < MIN_SAMPLES:
        problems.append(f"only {len(rows)} samples")
    t = [float(r["t_s"]) for r in rows]
    if any(b <= a for a, b in zip(t, t[1:])):
        problems.append("timestamps not increasing")
    tracked = sum(r["tracked"] == "1" for r in rows) / max(len(rows), 1)
    if tracked < MIN_TRACKED:
        problems.append(f"only {tracked:.0%} face-tracked")
    if meta.get("issues"):
        problems.append("sidecar issues: " + "; ".join(meta["issues"]))
    fd = meta.get("faceDistance") or {}
    if fd.get("check") != "passed":
        notes.append(f"distance check {fd.get('check')}; measured {fd.get('minCm', 0):.1f}-{fd.get('maxCm', 0):.1f} cm")
    if fd.get("fractionOutsideRange", 0) > 0.05:
        notes.append(f"distance outside 25-30 cm for {fd['fractionOutsideRange']:.0%} of the trial "
                     f"(median {fd.get('medianCm', 0):.1f} cm)")
    return problems, notes


def build(trials_dir, seed=SEED):
    rows = []
    for parent, folder in recordings(trials_dir):
        m = NAME_RE.fullmatch(folder.name)
        problems, notes = technical_check(folder)
        rows.append(dict(trial_id=folder.name, participant=m[1] if m else "", trial_number=int(m[2]) if m else 0,
                         condition=m[3] if m else "", direction=m[4] if m else "",
                         folder=str(Path(parent).relative_to(trials_dir)) if parent != Path(trials_dir) else ".",
                         technical_status="fail" if problems else "pass",
                         technical_notes="; ".join(problems + notes), eligibility="", exclusion_reason="", split=""))
    cells = {}
    for r in sorted(rows, key=lambda r: r["trial_number"]):
        if r["folder"] != ".":
            r["eligibility"], r["exclusion_reason"] = "excluded", "moved to _excluded_P03 by the experimenter"
        elif r["technical_status"] == "fail":
            r["eligibility"], r["exclusion_reason"] = "excluded", "technical failure"
        else:
            cell = cells.setdefault((r["participant"], r["condition"], r["direction"]), [])
            if len(cell) < PER_CELL[r["condition"]]:
                cell.append(r)
                r["eligibility"] = "primary"
            else:
                r["eligibility"], r["exclusion_reason"] = "extra", "beyond the planned count for its cell (later recording)"
    rng = random.Random(seed)
    for key in sorted(cells):
        cell = sorted(cells[key], key=lambda r: r["trial_id"])
        held = {r["trial_id"] for r in rng.sample(cell, min(EVAL_PER_CELL[key[1]], len(cell)))}
        for r in cell:
            r["split"] = "evaluation" if r["trial_id"] in held else "development"
    return sorted(rows, key=lambda r: (r["participant"], r["trial_number"])), cells


def render(rows):
    import io
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
    ap.add_argument("--force", action="store_true", help="overwrite a different saved manifest (unfreezes the split)")
    args = ap.parse_args(argv)
    rows, cells = build(args.trials_dir)
    text = render(rows)
    if args.check or (args.output.exists() and not args.force):
        if not args.output.exists():
            print(f"error: {args.output} does not exist", file=sys.stderr)
            return 1
        if args.output.read_text() != text:
            print(f"error: {args.output} differs from what the recordings give now; the split is frozen. "
                  "Use --force only if you mean to change it.", file=sys.stderr)
            return 1
        print(f"{args.output} is reproduced exactly")
        return 0
    args.output.write_text(text)
    counts = {}
    for r in rows:
        counts[(r["eligibility"], r["split"])] = counts.get((r["eligibility"], r["split"]), 0) + 1
    print(f"wrote {args.output}: " + ", ".join(f"{e}{'/' + s if s else ''} {n}" for (e, s), n in sorted(counts.items())))
    short = [f"{p} {c} {d}: {len(v)}/{PER_CELL[c]}" for (p, c, d), v in sorted(cells.items()) if len(v) < PER_CELL[c]]
    if short:
        print("cells below the planned count: " + "; ".join(short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
