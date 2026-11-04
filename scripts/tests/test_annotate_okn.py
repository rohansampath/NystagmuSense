"""Unit tests for annotate_okn.py (storage + GUI handlers) and evaluate_okn.py.

Run: python3 -m unittest discover scripts/tests   (needs numpy, scipy, matplotlib)

All recordings and labels here are SYNTHETIC fixtures, not experimental data.
"""

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


class TempLabels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.labels = self.dir / "labels"

    def recording(self, name, angle_fn=okn_angle, mode="okn"):
        folder = self.dir / "trials" / name
        folder.mkdir(parents=True)
        csv_path = folder / f"{name}.csv"
        csv_path.write_text(synthetic_csv(angle_fn))
        (folder / f"{name}.json").write_text(json.dumps({"stimulus": {"trialMode": mode}}))
        return csv_path


class StorageTests(TempLabels):
    def test_save_and_reload_round_trip(self):
        events = [(1.25, "fast_phase"), (2.5, "uncertain"), (3.0, "artifact")]
        annotate_okn.save_annotations(self.labels, "T1", "AA", events, "manual", complete=True)
        loaded, review = annotate_okn.load_annotations(self.labels, "T1", "AA")
        self.assertEqual(loaded, events)
        self.assertEqual(review["status"], "complete")
        self.assertEqual(review["annotation_method"], "manual")
        self.assertEqual((review["n_fast_phase"], review["n_uncertain"], review["n_artifact"]), ("1", "1", "1"))

    def test_saving_one_trial_keeps_other_trials_and_annotators(self):
        annotate_okn.save_annotations(self.labels, "T1", "AA", [(1.0, "fast_phase")], "manual", True)
        annotate_okn.save_annotations(self.labels, "T1", "BB", [(1.1, "fast_phase")], "manual", True)
        annotate_okn.save_annotations(self.labels, "T2", "AA", [(2.0, "fast_phase")], "manual", False)
        annotate_okn.save_annotations(self.labels, "T1", "AA", [(5.0, "fast_phase")], "manual", True)  # re-edit
        self.assertEqual(annotate_okn.load_annotations(self.labels, "T1", "AA")[0], [(5.0, "fast_phase")])
        self.assertEqual(annotate_okn.load_annotations(self.labels, "T1", "BB")[0], [(1.1, "fast_phase")])
        self.assertEqual(annotate_okn.load_annotations(self.labels, "T2", "AA")[0], [(2.0, "fast_phase")])
        self.assertEqual(len(annotate_okn._read_rows(self.labels / "reviews.csv")), 3)

    def test_duplicates_are_refused_and_collapsed(self):
        events = []
        self.assertTrue(annotate_okn.add_event(events, 1.000, "fast_phase"))
        self.assertFalse(annotate_okn.add_event(events, 1.030, "fast_phase"))   # within 50 ms
        self.assertTrue(annotate_okn.add_event(events, 1.060, "uncertain"))
        self.assertEqual(len(events), 2)
        self.assertEqual(annotate_okn.dedupe([(2.0, "fast_phase"), (2.0, "fast_phase"), (1.0, "artifact")]),
                         [(1.0, "artifact"), (2.0, "fast_phase")])

    def test_zero_event_reviewed_trial_differs_from_unannotated(self):
        annotate_okn.save_annotations(self.labels, "T_FIX", "AA", [], "manual", complete=True)
        events, review = annotate_okn.load_annotations(self.labels, "T_FIX", "AA")
        self.assertEqual(events, [])
        self.assertEqual(review["status"], "complete")
        self.assertIsNone(annotate_okn.load_annotations(self.labels, "T_NEVER", "AA")[1])

    def test_invalid_label_or_method_rejected(self):
        with self.assertRaises(ValueError):
            annotate_okn.save_annotations(self.labels, "T1", "AA", [(1.0, "saccade")], "manual", True)
        with self.assertRaises(ValueError):
            annotate_okn.save_annotations(self.labels, "T1", "AA", [], "auto", True)

    def test_suggestions_are_permissive_velocity_peaks(self):
        sig = annotate_okn.load_signal(self.recording("R1"))
        sug = annotate_okn.propose_candidates(sig["t"], sig["velocity"], sig["valid"])
        # Synthetic OKN has 15 resets between 2 and 8 s; nothing outside it.
        self.assertGreaterEqual(len(sug), 13)
        self.assertTrue(all(1.9 < t < 8.2 for t in sug))


class FakeEvent:
    def __init__(self, ax=None, x=None, button=1, key=None):
        self.inaxes, self.xdata, self.button, self.key = ax, x, button, key


class AnnotatorGUITests(TempLabels):
    def open(self, csv_path, assisted=False):
        a = annotate_okn.Annotator(csv_path, "AA", self.labels, assisted=assisted, show=False)
        self.addCleanup(a.plt.close, a.fig)
        return a

    def test_click_add_remove_undo_label_and_save(self):
        a = self.open(self.recording("R1"))
        a.on_click(FakeEvent(a.ax_a, 2.3001))
        a.on_key(FakeEvent(key="2"))
        a.on_click(FakeEvent(a.ax_v, 4.0))
        a.on_click(FakeEvent(a.ax_a, 4.01))                 # duplicate → ignored
        self.assertEqual([l for _, l in a.events], ["fast_phase", "uncertain"])
        self.assertAlmostEqual(a.events[0][0], round(2.3001 * 60) / 60, places=6)   # snapped to a sample
        a.on_click(FakeEvent(a.ax_a, 4.1, button=3))        # remove nearest
        self.assertEqual(len(a.events), 1)
        a.on_key(FakeEvent(key="z"))                        # undo the removal
        self.assertEqual(len(a.events), 2)
        a.on_key(FakeEvent(key="x"))
        a.on_key(FakeEvent(key="s"))
        events, review = annotate_okn.load_annotations(self.labels, "R1", "AA")
        self.assertEqual(len(events), 2)
        self.assertEqual((review["status"], review["annotation_method"]), ("complete", "manual"))

    def test_independent_mode_never_shows_suggestions(self):
        a = self.open(self.recording("R1"))
        a.on_key(FakeEvent(key="t"))
        self.assertFalse(a.suggestions_shown)
        self.assertEqual(a.suggestions, [])
        self.assertEqual(a.method, "manual")

    def test_assisted_accept_and_method_sticks(self):
        path = self.recording("R1")
        a = self.open(path, assisted=True)
        self.assertEqual(a.method, "manual")                # nothing shown yet
        a.on_key(FakeEvent(key="t"))
        a.on_key(FakeEvent(key="y"))                        # accept all visible suggestions
        self.assertEqual(len(a.events), len(a.suggestions))
        a.on_key(FakeEvent(key="s"))
        # Reopened without suggestions: still "assisted" (labels were influenced).
        b = self.open(path)
        self.assertEqual(b.method, "assisted")
        self.assertEqual(len(b.events), len(a.suggestions))

    def test_clicks_ignored_while_toolbar_tool_active(self):
        a = self.open(self.recording("R1"))

        class Toolbar:
            mode = "zoom rect"
        a.fig.canvas.toolbar = Toolbar()
        a.on_click(FakeEvent(a.ax_a, 3.0))
        self.assertEqual(a.events, [])


class MatchingTests(unittest.TestCase):
    def test_one_to_one_within_tolerance(self):
        pairs, missed, extra = evaluate_okn.match_events([1.0, 2.0, 3.0], [1.05, 1.08, 2.2, 3.0], 0.1)
        self.assertEqual(pairs, [(1.0, 1.05), (3.0, 3.0)])
        self.assertEqual(missed, [2.0])                     # 2.2 is outside ±100 ms
        self.assertEqual(extra, [1.08, 2.2])                # one prediction can't match twice

    def test_two_labels_compete_for_one_prediction(self):
        pairs, missed, extra = evaluate_okn.match_events([1.0, 1.15], [1.08], 0.1)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(len(missed), 1)
        self.assertEqual(extra, [])

    def test_maximum_matching_not_closest_greedy(self):
        # Closest-first would pair 1.09↔1.1 and leave 1.0 unmatched; order-greedy matches both.
        pairs, missed, _ = evaluate_okn.match_events([1.0, 1.1], [1.09, 1.19], 0.1)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(missed, [])

    def test_precision_recall_f1_and_undefined_cases(self):
        self.assertEqual(evaluate_okn.prf(3, 1, 1), (0.75, 0.75, 0.75))
        self.assertEqual(evaluate_okn.prf(0, 0, 0), (None, None, None))
        self.assertEqual(evaluate_okn.prf(0, 2, 0), (0.0, None, None))   # fixation trial with false hits
        self.assertEqual(evaluate_okn.prf(0, 0, 4), (None, 0.0, None))

    def test_uncertain_excluded_and_artifact_counts_as_false_positive(self):
        events = [(1.0, "fast_phase"), (2.0, "uncertain"), (3.0, "artifact")]
        s = evaluate_okn.score_trial(events, [1.02, 2.03, 3.01, 4.0], 0.1)
        self.assertEqual((s["tp"], s["fp"], s["fn"], s["excluded_uncertain"]), (1, 2, 0, 1))
        # An unmatched uncertain label is never a miss.
        s = evaluate_okn.score_trial([(2.0, "uncertain")], [], 0.1)
        self.assertEqual((s["tp"], s["fp"], s["fn"]), (0, 0, 0))


class EvaluateTests(TempLabels):
    def test_only_complete_reviews_scored_and_methods_kept_apart(self):
        okn = self.recording("OKN1")
        fix = self.recording("FIX1", angle_fn=lambda t: 0.0, mode="fixationStillStripes")
        self.recording("TODO1")
        truth = evaluate_okn.detector_predictions(okn)
        annotate_okn.save_annotations(self.labels, "OKN1", "AA", [(t, "fast_phase") for t in truth], "manual", True)
        annotate_okn.save_annotations(self.labels, "FIX1", "AA", [], "assisted", True)
        annotate_okn.save_annotations(self.labels, "TODO1", "AA", [(5.0, "fast_phase")], "manual", False)
        scored, skipped = evaluate_okn.evaluate(self.labels, self.dir / "trials")
        by_id = {s["trial_id"]: s for s in scored}
        self.assertEqual(set(by_id), {"OKN1", "FIX1"})
        self.assertEqual(skipped, [("TODO1", "AA", "in_progress")])
        self.assertEqual((by_id["OKN1"]["tp"], by_id["OKN1"]["fp"], by_id["OKN1"]["fn"]), (len(truth), 0, 0))
        self.assertEqual(by_id["OKN1"]["method"], "manual")
        self.assertEqual(by_id["FIX1"]["method"], "assisted")
        self.assertEqual(by_id["FIX1"]["mode"], "fixationStillStripes")
        self.assertEqual(by_id["FIX1"]["fp"], 0)


if __name__ == "__main__":
    unittest.main()
