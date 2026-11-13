#!/usr/bin/env python3
"""Build the Pilot 04 manifest: technical status, eligibility and dataset role.

    python3 analysis/pilot_04/build_manifest.py [--trials-dir trials] [--check]
    python3 analysis/pilot_04/build_manifest.py --review-status --labels-dir analysis/annotations_p04

Uses only each recording's file name, JSON sidecar and CSV timing/tracking;
labels and detector output are never read. The Pilot 03 manifest is not read
or changed.

Rules (docs/PILOT_04.md):
- Technical failure: the Pilot 03 checks (name/metadata agreement, constant
  white background, stripe speed matching the condition, at least 570 samples,
  at least 90 % face-tracked, finite strictly increasing timestamps (so no
  duplicates), no sidecar issues), plus a participant outside P01-P03.
  Missing distance data, a failed or bypassed distance check, and distance
  drift are notes.
- Primary: per participant × condition × direction, the first N technically
  valid recordings in trial-number order: 4 per cell (4 OKN and 4 FIXMOVE per
  direction, 4 FIXSTILL), the protocol as actually collected. The original
  plan was 4/3/6; see "Protocol deviation" in docs/PILOT_04.md. Later valid ones are "extra"; recordings the experimenter moved
  to trials/_excluded_P04/ are "excluded".
- Every primary recording has role external_validation and split
  "evaluation": the annotation tool never shows detector suggestions for it,
  and evaluate_okn.py refuses to score it without --allow-evaluation. There
  is no development part of Pilot 04 until its validation has been saved.
"""

import argparse
import csv
import io
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
MANIFEST = Path(__file__).resolve().parent / "manifest.csv"
CODE = "P04"
PARTICIPANTS = {"P01": "returning", "P02": "returning", "P03": "new"}
NAME_RE = re.compile(r"P04-(P\d\d)_T(\d+)_(OKN|FIXMOVE|FIXSTILL)_(RIGHT|LEFT|NONE)_(\d{8}_\d{6})")
MODES = {"okn": "OKN", "fixationMovingStripes": "FIXMOVE", "fixationStillStripes": "FIXSTILL"}
PER_CELL = {"OKN": 4, "FIXMOVE": 4, "FIXSTILL": 4}      # as collected (planned 4/3/6)
MIN_SAMPLES, MIN_TRACKED = 570, 0.90
FIELDS = ["trial_id", "participant", "participant_status", "trial_number", "condition", "direction", "folder",
          "technical_status", "technical_notes", "eligibility", "exclusion_reason", "role", "split"]


def recordings(trials_dir):
    """(parent, folder) for every P04 recording, including experimenter exclusions."""
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
        return ["name is not a P04 recording name"], []
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
    participant, condition, direction = m[1], m[3], m[4]
    if participant not in PARTICIPANTS or (direction == "NONE") != (condition == "FIXSTILL"):
        problems.append("participant or condition/direction combination is not in the P04 protocol")
    expected = {"experimentID": CODE, "recordingName": name, "participantID": participant,
                "trialNumber": int(m[2]), "directionCode": direction}
    for key, want in expected.items():
        if meta.get(key) != want:
            problems.append(f"metadata {key}={meta.get(key)!r} disagrees with name")
    if MODES.get(stim.get("trialMode")) != condition:
        problems.append(f"trialMode {stim.get('trialMode')!r} disagrees with name")
    if direction != "NONE" and {"rightward": "RIGHT", "leftward": "LEFT"}.get(stim.get("direction")) != direction:
        problems.append("stimulus.direction disagrees with name")
    if stim.get("fixedBackgroundGray") != 1:
        problems.append("background not fixed at 1 (not the P04 stimulus)")
    speed = stim.get("speedPointsPerSecond")
    if not isinstance(speed, (float, int)) or not math.isfinite(speed) or speed < 0 or \
            (speed == 0) != (condition == "FIXSTILL"):
        problems.append("stripe speed doesn't match the condition")
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
            notes.append(f"distance check {fd.get('check')}; measured {fd.get('minCm', 0):.1f}-{fd.get('maxCm', 0):.1f} cm")
        if fd.get("fractionOutsideRange", 0) > 0.05:
            notes.append(f"distance outside 25-30 cm for {fd['fractionOutsideRange']:.0%} of the trial "
                         f"(median {fd.get('medianCm', 0):.1f} cm)")
    return problems, notes


def build(trials_dir):
    rows = []
    for parent, folder in recordings(trials_dir):
        m = NAME_RE.fullmatch(folder.name)
        problems, notes = technical_check(folder)
        rows.append(dict(trial_id=folder.name, participant=m[1] if m else "",
                         participant_status=PARTICIPANTS.get(m[1], "") if m else "",
                         trial_number=int(m[2]) if m else 0, condition=m[3] if m else "",
                         direction=m[4] if m else "",
                         folder=str(Path(parent).relative_to(trials_dir)) if parent != Path(trials_dir) else ".",
                         technical_status="fail" if problems else "pass",
                         technical_notes="; ".join(problems + notes),
                         eligibility="", exclusion_reason="", role="", split=""))
    cells = {}
    for r in sorted(rows, key=lambda r: r["trial_number"]):
        if r["folder"] != ".":
            r["eligibility"], r["exclusion_reason"] = "excluded", f"moved to _excluded_{CODE} by the experimenter"
        elif r["technical_status"] == "fail":
            r["eligibility"], r["exclusion_reason"] = "excluded", "technical failure"
        else:
            cell = cells.setdefault((r["participant"], r["condition"], r["direction"]), [])
            if len(cell) < PER_CELL[r["condition"]]:
                cell.append(r)
                r["eligibility"], r["role"], r["split"] = "primary", "external_validation", "evaluation"
            else:
                r["eligibility"], r["exclusion_reason"] = "extra", "beyond the planned count for its cell (later recording)"
    return sorted(rows, key=lambda r: (r["participant"], r["trial_number"])), cells


def render(rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def shortfalls(cells):
    """Planned cells with fewer primary recordings than the protocol asks for."""
    out = []
    for p in PARTICIPANTS:
        for c, n in PER_CELL.items():
            for d in (("NONE",) if c == "FIXSTILL" else ("LEFT", "RIGHT")):
                have = len(cells.get((p, c, d), []))
                if have < n:
                    out.append(f"{p} {c} {d}: {have}/{n}")
    return out


def review_status(manifest, labels_dir, annotator=None):
    """trial_id → review status of the primary recordings ("not opened" when absent)."""
    import annotate_okn
    primary = [r for r in annotate_okn._read_rows(manifest) if r["eligibility"] == "primary"]
    trial_ids = {r["trial_id"] for r in primary}
    selected = [r for r in annotate_okn._read_rows(Path(labels_dir) / "reviews.csv")
                if r["trial_id"] in trial_ids and (annotator is None or r["annotator_id"] == annotator)]
    if len({r["annotator_id"] for r in selected}) > 1:
        raise ValueError("multiple annotators found; select one with --annotator")
    reviews = {r["trial_id"]: r for r in selected}
    return {r["trial_id"]: (reviews[r["trial_id"]]["status"], reviews[r["trial_id"]]["annotation_method"])
            if r["trial_id"] in reviews else ("not opened", "") for r in primary}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "trials")
    ap.add_argument("--output", type=Path, default=MANIFEST)
    ap.add_argument("--check", action="store_true", help="only verify the saved manifest is reproduced exactly")
    ap.add_argument("--force", action="store_true", help="overwrite a different saved manifest")
    ap.add_argument("--review-status", action="store_true", help="list each primary recording's review status")
    ap.add_argument("--labels-dir", type=Path, default=ROOT / "analysis" / "annotations_p04")
    ap.add_argument("--annotator", help="reviewer to check; inferred only when unambiguous")
    args = ap.parse_args(argv)
    if args.review_status:
        try:
            status = review_status(args.output, args.labels_dir, args.annotator)
        except ValueError as e:
            ap.error(str(e))
        for tid, (s, method) in sorted(status.items()):
            print(f"{tid:44} {s:12} {method}")
        done = sum(s == "complete" and m == "manual" for s, m in status.values())
        print(f"{done}/{len(status)} primary recordings completely reviewed (manual)")
        return 0
    rows, cells = build(args.trials_dir)
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
        print("cells below the planned count: " + "; ".join(short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
