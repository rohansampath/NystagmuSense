"""Synthetic regressions for annotation isolation and frozen detector selection."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import annotate_okn
import detect_okn
import evaluate_okn
from test_detect_okn import synthetic_csv, okn_angle


class EvaluationReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.csv = self.root / "trial.csv"
        self.csv.write_text(synthetic_csv(lambda t: -okn_angle(t)))

    def test_direction_candidate_uses_22_and_filters_the_actual_signal(self):
        data = detect_okn.load_session(self.csv)
        r = detect_okn.analyse(data, detect_okn.Params(fast_threshold=22))
        expected = [f["start"] for f in r["fast"] if f["direction"] == 1]
        self.assertTrue(expected)
        self.assertEqual(evaluate_okn.detector_predictions(self.csv, "sg-direction"), expected)
        self.assertEqual(evaluate_okn.detector_predictions(self.csv),
                         [f["start"] for f in detect_okn.analyse(data, detect_okn.Params())["fast"]])

    def test_unknown_or_reversing_stimulus_is_not_silently_accepted(self):
        data = detect_okn.load_session(self.csv)
        for displacement in (None, data["stim_displacement_pt"] * float("nan"),
                             abs(data["stim_displacement_pt"] - 450)):
            altered = dict(data)
            if displacement is None:
                del altered["stim_displacement_pt"]
            else:
                altered["stim_displacement_pt"] = displacement
            with patch.object(detect_okn, "load_session", return_value=altered), self.assertRaises(ValueError):
                evaluate_okn.detector_predictions(self.csv, "sg-direction")

    def test_p03_manifest_disables_suggestions_for_direct_csv_queues(self):
        manifest = self.root / "manifest.csv"
        manifest.write_text("trial_id,eligibility,split,trial_number\ntrial,primary,evaluation,1\n"
                            "extra,extra,,2\n")
        plan = annotate_okn.load_plan(manifest)
        self.assertEqual(set(plan), {"trial"})
        with patch.object(annotate_okn, "P03_MANIFEST", manifest), \
                patch.object(annotate_okn, "propose_candidates") as propose:
            a = annotate_okn.Annotator(self.csv, "AA", self.root / "labels", assisted=True, show=False, plan={})
            self.addCleanup(a.plt.close, a.fig)
            self.assertEqual(a.split, "evaluation")
            self.assertFalse(a.suggestions_allowed)
            propose.assert_not_called()

    def test_default_evaluation_cannot_bypass_the_p03_split_gate(self):
        manifest = self.root / "manifest.csv"
        manifest.write_text("trial_id,eligibility,split,trial_number\ntrial,primary,evaluation,1\n")
        labels = self.root / "labels"
        annotate_okn.save_annotations(labels, "trial", "AA", [], "manual", True)
        with patch.object(annotate_okn, "P03_MANIFEST", manifest), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            evaluate_okn.main(["--labels-dir", str(labels)])

    def test_selected_detector_and_annotator_are_exported(self):
        import csv
        labels = self.root / "labels"
        annotate_okn.save_annotations(labels, "trial", "AA", [], "manual", True, source_csv=self.csv)
        out = self.root / "scores.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evaluate_okn.main(["--labels-dir", str(labels), "--detector", "sg-direction",
                                               "--output-csv", str(out)]), 0)
        with out.open() as f:
            row = next(csv.DictReader(f))
        self.assertEqual((row["annotator"], row["detector"], row["fast_threshold"]), ("AA", "sg-direction", "22"))

    def test_still_stripe_labels_cannot_raise_benchmark_f1(self):
        score = evaluate_okn.score_manifest_trial([(1.0, "fast_phase")], [1.01], "FIXSTILL")
        self.assertEqual((score["tp"], score["fp"], score["fn"], score["n_ref"]), (0, 1, 0, 0))

    def test_report_cannot_overwrite_labels_or_raw_inputs(self):
        labels = self.root / "labels"
        annotate_okn.save_annotations(labels, "trial", "AA", [], "manual", True, source_csv=self.csv)
        for output in (labels / "events.csv", labels / "reviews.csv", self.csv):
            original = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                evaluate_okn.main(["--labels-dir", str(labels), "--output-csv", str(output)])
            self.assertEqual(output.read_bytes(), original)

    def test_label_checker_defaults_to_development_and_blocks_evaluation(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis/pilot_03"))
        import check_labels
        manifest = self.root / "manifest.csv"
        manifest.write_text("trial_id,eligibility,split,direction\n"
                            "trial,primary,development,RIGHT\nheld,primary,evaluation,LEFT\n")
        labels = self.root / "labels"
        annotate_okn.save_annotations(labels, "trial", "AA", [], "manual", True)
        annotate_okn.save_annotations(labels, "held", "AA", [(1.0, "fast_phase")], "manual", True)
        args = ["--manifest", str(manifest), "--labels-dir", str(labels), "--output", str(self.root / "flags.csv")]
        with patch.object(annotate_okn, "load_signal") as load, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_labels.main(args), 0)
            load.assert_not_called()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            check_labels.main(args + ["--split", "evaluation"])


if __name__ == "__main__":
    unittest.main()
