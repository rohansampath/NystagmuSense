"""Tests for the Pilot 03 manifest, split-filtered evaluation and the threshold sweep.

Run: python3 -m unittest discover scripts/tests   (needs numpy, scipy, matplotlib)

All recordings and labels here are SYNTHETIC fixtures, not experimental data.
"""

import contextlib
import csv
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
import sweep_okn_threshold  # noqa: E402
from test_detect_okn import okn_angle, synthetic_csv  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_manifest", Path(__file__).resolve().parents[2] / "analysis/pilot_03/build_manifest.py")
build_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_manifest)

PLAN = [("OKN", "RIGHT", 4), ("OKN", "LEFT", 4), ("FIXMOVE", "RIGHT", 3), ("FIXMOVE", "LEFT", 3), ("FIXSTILL", "NONE", 6)]
MODE = {"OKN": "okn", "FIXMOVE": "fixationMovingStripes", "FIXSTILL": "fixationStillStripes"}


def write_recording(folder_parent, participant, trial, condition, direction, angle_fn=okn_angle, **meta_overrides):
    name = f"P03-{participant}_T{trial:03d}_{condition}_{direction}_20261105_02{trial % 60:02d}00"
    folder = Path(folder_parent) / name
    folder.mkdir(parents=True)
    (folder / f"{name}.csv").write_text(synthetic_csv(angle_fn if condition != "FIXSTILL" else (lambda t: 0.0)))
    meta = dict(schemaVersion=6, recordingName=name, participantID=participant, trialNumber=trial,
                directionCode=direction, issues=[], faceDistance={"check": "passed", "fractionOutsideRange": 0},
                stimulus=dict(trialMode=MODE[condition], direction="leftward" if direction == "LEFT" else "rightward",
                              fixedBackgroundGray=1, speedPointsPerSecond=0 if condition == "FIXSTILL" else 126))
    meta.update(meta_overrides)
    (folder / f"{name}.json").write_text(json.dumps(meta))
    return name


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trials = Path(self.tmp.name) / "trials"
        self.labels = Path(self.tmp.name) / "labels"

    def full_cohort(self, extras=()):
        trial = 1
        for participant in ("P01", "P02"):
            for condition, direction, n in PLAN:
                for _ in range(n + extras.count((participant, condition, direction))):
                    write_recording(self.trials, participant, trial, condition, direction)
                    trial += 1


class ManifestTests(Fixture):
    def test_balanced_cohort_gives_28_development_and_12_evaluation(self):
        self.full_cohort()
        rows, _ = build_manifest.build(self.trials)
        primary = [r for r in rows if r["eligibility"] == "primary"]
        self.assertEqual(len(primary), 40)
        self.assertEqual(sum(r["split"] == "evaluation" for r in primary), 12)
        for participant in ("P01", "P02"):
            held = [(r["condition"], r["direction"]) for r in primary
                    if r["participant"] == participant and r["split"] == "evaluation"]
            self.assertEqual(sorted(held), [("FIXMOVE", "LEFT"), ("FIXMOVE", "RIGHT"), ("FIXSTILL", "NONE"),
                                            ("FIXSTILL", "NONE"), ("OKN", "LEFT"), ("OKN", "RIGHT")])

    def test_split_is_reproducible_and_seed_dependent(self):
        self.full_cohort()
        first = build_manifest.render(build_manifest.build(self.trials)[0])
        self.assertEqual(first, build_manifest.render(build_manifest.build(self.trials)[0]))
        other = build_manifest.render(build_manifest.build(self.trials, seed=1)[0])
        self.assertNotEqual(first, other)

    def test_later_recordings_beyond_the_plan_are_extra_and_excluded_folder_is_kept(self):
        self.full_cohort(extras=[("P01", "FIXMOVE", "RIGHT")])
        write_recording(self.trials / "_excluded_P03", "P01", 99, "OKN", "LEFT")
        rows, _ = build_manifest.build(self.trials)
        cell = [r for r in rows if (r["participant"], r["condition"], r["direction"]) == ("P01", "FIXMOVE", "RIGHT")]
        self.assertEqual([r["eligibility"] for r in sorted(cell, key=lambda r: r["trial_number"])],
                         ["primary", "primary", "primary", "extra"])
        self.assertEqual(cell[-1]["split"], "")
        excluded = next(r for r in rows if r["trial_number"] == 99)
        self.assertEqual((excluded["eligibility"], excluded["split"]), ("excluded", ""))

    def test_technical_failures_are_excluded_but_irregular_traces_are_not(self):
        bad = write_recording(self.trials, "P01", 1, "OKN", "RIGHT", issues=["App left the foreground"])
        odd = write_recording(self.trials, "P01", 2, "OKN", "RIGHT", angle_fn=lambda t: 5.0 * (t % 3 > 1.5))
        wrong = write_recording(self.trials, "P01", 3, "OKN", "RIGHT", directionCode="LEFT")
        rows = {r["trial_id"]: r for r in build_manifest.build(self.trials)[0]}
        self.assertEqual((rows[bad]["eligibility"], rows[bad]["exclusion_reason"]), ("excluded", "technical failure"))
        self.assertEqual(rows[wrong]["technical_status"], "fail")
        self.assertEqual(rows[odd]["eligibility"], "primary")

    def test_check_mode_refuses_a_changed_cohort(self):
        self.full_cohort()
        out = Path(self.tmp.name) / "manifest.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build_manifest.main(["--trials-dir", str(self.trials), "--output", str(out)]), 0)
            write_recording(self.trials, "P02", 200, "OKN", "LEFT")         # changes nothing primary
            self.assertEqual(build_manifest.main(["--trials-dir", str(self.trials), "--output", str(out), "--check"]), 1)


class EvaluationTests(Fixture):
    def manifest(self):
        self.full_cohort()
        rows, _ = build_manifest.build(self.trials)
        path = Path(self.tmp.name) / "manifest.csv"
        path.write_text(build_manifest.render(rows))
        return path, rows

    def test_split_filter_scores_only_that_split_and_lists_unopened_trials(self):
        path, rows = self.manifest()
        dev = [r["trial_id"] for r in rows if r["split"] == "development"]
        ev = [r["trial_id"] for r in rows if r["split"] == "evaluation"]
        for tid in dev[:3] + ev[:2]:
            annotate_okn.save_annotations(self.labels, tid, "AA", [(2.3, "fast_phase")], "manual", complete=True)
        include = evaluate_okn.load_manifest(path, "development")
        scored, skipped = evaluate_okn.evaluate(self.labels, self.trials, predict=lambda p: [2.32], include=include)
        self.assertEqual(sorted(s["trial_id"] for s in scored), sorted(dev[:3]))
        self.assertTrue(all(s["participant"] and s["split"] == "development" for s in scored))
        self.assertEqual(len(skipped), 28 - 3)
        self.assertFalse(set(ev) & {t for t, _, _ in skipped})

    def test_evaluation_split_needs_explicit_permission(self):
        path, _ = self.manifest()
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            evaluate_okn.main(["--manifest", str(path), "--split", "evaluation", "--labels-dir", str(self.labels)])
        self.assertIn("held out", err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            evaluate_okn.main(["--manifest", str(path), "--labels-dir", str(self.labels)])

    def test_zero_event_trial_counts_false_positives_per_10_seconds(self):
        s = evaluate_okn.score_trial([], [1.0, 5.0], 0.1)
        self.assertEqual((s["tp"], s["fp"], s["fn"]), (0, 2, 0))
        self.assertEqual(evaluate_okn.prf(0, 2, 0)[1], None)                     # recall undefined
        s.update(duration_s=9.95, mean_abs_offset_s=None)
        self.assertAlmostEqual(evaluate_okn.summarize([s])["fp_per_10s"], 20 / 9.95)
        quiet = evaluate_okn.score_trial([], [], 0.1)
        quiet.update(duration_s=10, mean_abs_offset_s=None)
        g = evaluate_okn.summarize([quiet])
        self.assertEqual((g["precision"], g["recall"], g["f1"], g["fp_per_10s"]), (None, None, None, 0))

    def test_pooled_f1_is_never_raised_by_control_trials(self):
        okn = evaluate_okn.score_trial([(1.0, "fast_phase"), (2.0, "fast_phase")], [1.02, 3.0], 0.1)
        noisy = evaluate_okn.score_trial([], [4.0, 6.0], 0.1)
        quiet = evaluate_okn.score_trial([], [], 0.1)
        for s in (okn, noisy, quiet):
            s.update(duration_s=10, mean_abs_offset_s=None)
        alone = evaluate_okn.summarize([okn])["f1"]
        self.assertAlmostEqual(evaluate_okn.summarize([okn, quiet])["f1"], alone)       # a silent control adds nothing
        self.assertLess(evaluate_okn.summarize([okn, noisy])["f1"], alone)              # its false alarms only lower F1

    def test_artifact_policy_is_explicit(self):
        events = [(1.0, "fast_phase"), (3.0, "artifact"), (5.0, "uncertain")]
        preds = [1.02, 3.04, 5.01, 7.0]
        kept = evaluate_okn.score_trial(events, preds, 0.1)
        dropped = evaluate_okn.score_trial(events, preds, 0.1, artifacts="exclude")
        self.assertEqual((kept["tp"], kept["fp"], kept["excluded_artifact"]), (1, 2, 0))
        self.assertEqual((dropped["tp"], dropped["fp"], dropped["excluded_artifact"], dropped["excluded_uncertain"]),
                         (1, 1, 1, 1))

    def test_csv_export_has_one_row_per_scored_trial(self):
        path, rows = self.manifest()
        dev = [r["trial_id"] for r in rows if r["split"] == "development"][:2]
        for tid in dev:
            annotate_okn.save_annotations(self.labels, tid, "AA", [], "manual", complete=True)
        out = Path(self.tmp.name) / "out.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            evaluate_okn.main(["--manifest", str(path), "--split", "development", "--labels-dir", str(self.labels),
                               "--trials-dir", str(self.trials), "--artifacts", "exclude", "--output-csv", str(out)])
        got = list(csv.DictReader(open(out)))
        self.assertEqual([r["trial_id"] for r in got], sorted(dev))
        self.assertEqual(list(got[0]), evaluate_okn.TRIAL_FIELDS)


class SweepTests(Fixture):
    def test_choice_prefers_f1_then_fewer_false_positives(self):
        def res(f1, fp):
            return [("all", "all", dict(f1=f1, fp_per_10s=fp))]
        self.assertEqual(sweep_okn_threshold.choose({20: res(0.80, 2.0), 30: res(0.795, 0.5), 40: res(0.6, 0.1)}), 30)
        self.assertEqual(sweep_okn_threshold.choose({20: res(0.80, 0.5), 30: res(0.70, 0.1)}), 20)

    def test_sweep_refuses_unreviewed_development_trials_and_never_scores_evaluation(self):
        self.full_cohort()
        rows, _ = build_manifest.build(self.trials)
        path = Path(self.tmp.name) / "manifest.csv"
        path.write_text(build_manifest.render(rows))
        for r in rows:              # every trial reviewed with labels at the synthetic resets' starts
            annotate_okn.save_annotations(self.labels, r["trial_id"], "AA", [], "manual", complete=True)
        dev = rows[0]["trial_id"] if rows[0]["split"] == "development" else rows[1]["trial_id"]
        annotate_okn.save_annotations(self.labels, dev, "AA", [], "manual", complete=False)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sweep_okn_threshold.main(["--manifest", str(path), "--labels-dir", str(self.labels),
                                                       "--trials-dir", str(self.trials)]), 1)
        include = evaluate_okn.load_manifest(path, "development")
        results, _ = sweep_okn_threshold.sweep(self.labels, self.trials, include, thresholds=[20, 40])
        self.assertEqual(sweep_okn_threshold.overall(results[40])["n_trials"], 27)    # 28 minus the in-progress one


if __name__ == "__main__":
    unittest.main()
