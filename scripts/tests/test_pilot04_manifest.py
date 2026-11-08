"""Tests for the Pilot 04 manifest and how it plugs into annotation and evaluation.

Run: python3 -m unittest discover scripts/tests

All recordings here are SYNTHETIC fixtures, not experimental data.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import annotate_okn  # noqa: E402
import evaluate_okn  # noqa: E402
from test_detect_okn import okn_angle, synthetic_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("p04_manifest", ROOT / "analysis/pilot_04/build_manifest.py")
p04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p04)

PLAN = [("OKN", "RIGHT", 4), ("OKN", "LEFT", 4), ("FIXMOVE", "RIGHT", 3), ("FIXMOVE", "LEFT", 3), ("FIXSTILL", "NONE", 6)]
MODE = {"OKN": "okn", "FIXMOVE": "fixationMovingStripes", "FIXSTILL": "fixationStillStripes"}


def write_recording(parent, participant, trial, condition, direction, csv_text=None, **meta_overrides):
    name = f"P04-{participant}_T{trial:03d}_{condition}_{direction}_20261110_{10 + trial // 60:02d}{trial % 60:02d}00"
    folder = Path(parent) / name
    folder.mkdir(parents=True)
    (folder / f"{name}.csv").write_text(csv_text or synthetic_csv(okn_angle if condition != "FIXSTILL" else (lambda t: 0.0)))
    meta = dict(schemaVersion=6, experimentID="P04", recordingName=name, participantID=participant, trialNumber=trial,
                directionCode=direction, issues=[], faceDistance={"check": "passed", "fractionOutsideRange": 0},
                stimulus=dict(trialMode=MODE[condition], direction="leftward" if direction == "LEFT" else "rightward",
                              fixedBackgroundGray=1, speedPointsPerSecond=0 if condition == "FIXSTILL" else 126))
    meta.update(meta_overrides)
    (folder / f"{name}.json").write_text(json.dumps(meta))
    return name


class Pilot04Manifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trials = Path(self.tmp.name) / "trials"
        self.trials.mkdir()

    def cohort(self, start=57):
        trial = start
        for participant in ("P01", "P02", "P03"):
            for condition, direction, n in PLAN:
                for _ in range(n):
                    write_recording(self.trials, participant, trial, condition, direction)
                    trial += 1
        return trial

    def test_sixty_planned_recordings_are_external_validation_only(self):
        self.cohort()
        rows, cells = p04.build(self.trials)
        primary = [r for r in rows if r["eligibility"] == "primary"]
        self.assertEqual(len(primary), 60)
        self.assertTrue(all(r["role"] == "external_validation" and r["split"] == "evaluation" for r in primary))
        self.assertEqual(p04.shortfalls(cells), [])
        status = {r["participant"]: r["participant_status"] for r in primary}
        self.assertEqual(status, {"P01": "returning", "P02": "returning", "P03": "new"})

    def test_technical_failures_extras_and_experimenter_exclusions(self):
        trial = self.cohort()
        dup = synthetic_csv(okn_angle).splitlines(keepends=True)
        dup.insert(3, dup[2])                                           # a repeated timestamp
        bad = [write_recording(self.trials, "P01", trial, "OKN", "RIGHT", csv_text="".join(dup)),
               write_recording(self.trials, "P02", trial + 1, "OKN", "LEFT",
                               stimulus=dict(trialMode="okn", direction="leftward", speedPointsPerSecond=126)),
               write_recording(self.trials, "P03", trial + 2, "OKN", "LEFT", participantID="P01")]
        extra = write_recording(self.trials, "P03", trial + 3, "FIXSTILL", "NONE")
        moved = write_recording(self.trials / "_excluded_P04", "P01", trial + 4, "OKN", "LEFT")
        by_id = {r["trial_id"]: r for r in p04.build(self.trials)[0]}
        self.assertIn("duplicate", by_id[bad[0]]["technical_notes"])
        self.assertIn("background", by_id[bad[1]]["technical_notes"])
        self.assertIn("participantID", by_id[bad[2]]["technical_notes"])
        for name in bad:
            self.assertEqual((by_id[name]["eligibility"], by_id[name]["role"]), ("excluded", ""))
        self.assertEqual((by_id[extra]["eligibility"], by_id[extra]["split"]), ("extra", ""))
        self.assertEqual(by_id[moved]["eligibility"], "excluded")
        self.assertEqual(sum(r["eligibility"] == "primary" for r in by_id.values()), 60)

    def test_missing_cells_and_absent_distance_data_are_reported(self):
        write_recording(self.trials, "P03", 1, "OKN", "RIGHT", faceDistance=None)
        rows, cells = p04.build(self.trials)
        self.assertIn("no distance data", rows[0]["technical_notes"])
        self.assertEqual(rows[0]["technical_status"], "pass")
        self.assertIn("P03 OKN RIGHT: 1/4", p04.shortfalls(cells))
        self.assertIn("P01 FIXSTILL NONE: 0/6", p04.shortfalls(cells))

    def test_pilot_03_recordings_are_ignored(self):
        (self.trials / "P03-P01_T011_OKN_LEFT_20261105_024418").mkdir()
        self.assertEqual(p04.build(self.trials)[0], [])

    def test_check_refuses_a_changed_manifest(self):
        self.cohort()
        out = Path(self.tmp.name) / "manifest.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p04.main(["--trials-dir", str(self.trials), "--output", str(out)]), 0)
            self.assertEqual(p04.main(["--trials-dir", str(self.trials), "--output", str(out), "--check"]), 0)
        write_recording(self.trials, "P03", 999, "OKN", "LEFT")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(p04.main(["--trials-dir", str(self.trials), "--output", str(out), "--check"]), 1)

    def test_annotation_and_evaluation_treat_pilot_04_as_held_out(self):
        self.cohort()
        out = Path(self.tmp.name) / "manifest.csv"
        out.write_text(p04.render(p04.build(self.trials)[0]))
        plan = annotate_okn.load_plan(out)
        self.assertEqual(len(plan), 60)
        self.assertTrue(all(r["split"] == "evaluation" for r in plan.values()))   # suggestions never shown
        queue = annotate_okn.split_queue("evaluation", self.trials, plan)
        self.assertEqual(len(queue), 60)
        self.assertEqual(len(evaluate_okn.load_manifest(out, "evaluation")), 60)
        with self.assertRaises(ValueError):
            evaluate_okn.load_manifest(out, "development")                  # nothing to tune on yet
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            evaluate_okn.main(["--manifest", str(out), "--split", "evaluation", "--labels-dir", self.tmp.name])
        self.assertIn("held out", err.getvalue())

    def test_review_status_lists_every_primary_recording(self):
        self.cohort()
        out = Path(self.tmp.name) / "manifest.csv"
        out.write_text(p04.render(p04.build(self.trials)[0]))
        labels = Path(self.tmp.name) / "labels"
        first = next(iter(annotate_okn.load_plan(out)))
        annotate_okn.save_annotations(labels, first, "AA", [], "manual", complete=True)
        status = p04.review_status(out, labels)
        self.assertEqual(len(status), 60)
        self.assertEqual(status[first], ("complete", "manual"))
        self.assertEqual(sum(s == "not opened" for s, _ in status.values()), 59)


if __name__ == "__main__":
    unittest.main()
