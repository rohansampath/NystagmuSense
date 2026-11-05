"""Unit tests for annotate_okn.py (storage + GUI handlers) and evaluate_okn.py.

Run: python3 -m unittest discover scripts/tests   (needs numpy, scipy, matplotlib)

All recordings and labels here are SYNTHETIC fixtures, not experimental data.
"""

import json
import sys
import tempfile
import unittest
import unittest.mock
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

    def test_hiding_suggestions_before_save_keeps_assisted_method(self):
        path = self.recording("R1")
        a = self.open(path, assisted=True)
        a.on_key(FakeEvent(key="t"))
        self.assertTrue(a.dirty)
        a.on_key(FakeEvent(key="t"))
        self.assertFalse(a.suggestions_shown)
        self.assertEqual(a.method, "assisted")
        a.save()
        self.assertEqual(self.open(path).method, "assisted")


class QueueTests(TempLabels):
    def queue(self, *names):
        return [self.recording(n) for n in names]

    def open(self, trials, assisted=False, plan=None, start=None):
        a = annotate_okn.Annotator(trials, "AA", self.labels, assisted=assisted, show=False,
                                   plan=plan or {}, start=start)
        self.addCleanup(a.plt.close, a.fig)
        return a

    def test_next_and_previous_autosave_and_reload(self):
        a = self.open(self.queue("R1", "R2", "R3"))
        a.on_click(FakeEvent(a.ax_a, 2.3))
        a.on_key(FakeEvent(key="right"))                    # saves R1, opens R2
        self.assertEqual((a.index, a.trial_id, a.events, a.dirty), (1, "R2", [], False))
        saved, review = annotate_okn.load_annotations(self.labels, "R1", "AA")
        self.assertEqual(len(saved), 1)
        self.assertEqual(review["status"], "in_progress")   # navigating never marks reviewed
        a.on_key(FakeEvent(key="left"))                     # back to R1 with its label
        self.assertEqual((a.trial_id, len(a.events)), ("R1", 1))

    def test_ends_of_queue_do_not_wrap(self):
        a = self.open(self.queue("R1", "R2"))
        self.assertFalse(a.go(-1))
        self.assertEqual(a.index, 0)
        self.assertIn("first trial", a.message)
        a.go(1)
        self.assertFalse(a.go(1))
        self.assertEqual(a.index, 1)
        self.assertIn("last trial", a.message)

    def test_untouched_trials_are_not_written(self):
        a = self.open(self.queue("R1", "R2"))
        a.go(1)
        self.assertFalse((self.labels / "reviews.csv").exists())

    def test_save_failure_blocks_navigation_and_keeps_edits(self):
        a = self.open(self.queue("R1", "R2"))
        a.on_click(FakeEvent(a.ax_a, 2.3))
        with unittest.mock.patch.object(annotate_okn, "save_annotations", side_effect=OSError("disk full")):
            self.assertFalse(a.go(1))
        self.assertEqual((a.trial_id, len(a.events), a.dirty), ("R1", 1, True))
        self.assertIn("SAVE FAILED", a.message)
        self.assertTrue(a.go(1))                            # works once saving works again
        self.assertEqual(len(annotate_okn.load_annotations(self.labels, "R1", "AA")[0]), 1)

    def test_review_status_and_zero_event_trials_survive_navigation(self):
        a = self.open(self.queue("R1", "R2"))
        a.on_key(FakeEvent(key="x"))                        # reviewed, no events
        a.go(1)
        a.go(-1)
        self.assertTrue(a.complete)
        self.assertEqual(a.events, [])
        _, review = annotate_okn.load_annotations(self.labels, "R1", "AA")
        self.assertEqual((review["status"], review["n_fast_phase"]), ("complete", "0"))
        self.assertEqual(a.reviewed_count(), 1)
        a.go(1)
        self.assertFalse(a.complete)                        # R2 untouched: still unreviewed

    def test_resumes_at_first_unreviewed_trial_or_start(self):
        paths = self.queue("R1", "R2", "R3")
        annotate_okn.save_annotations(self.labels, "R1", "AA", [], "manual", complete=True)
        annotate_okn.save_annotations(self.labels, "R2", "AA", [(2.3, "fast_phase")], "manual", complete=False)
        annotate_okn.save_annotations(self.labels, "R2", "BB", [], "manual", complete=True)   # other annotator
        self.assertEqual(self.open(paths).trial_id, "R2")
        plan = {"R3": {"split": "development", "pilot_id": "A9"}}
        self.assertEqual(annotate_okn.resolve_start(paths, plan, "A9"), 2)
        self.assertEqual(annotate_okn.resolve_start(paths, plan, "1"), 0)
        self.assertEqual(annotate_okn.resolve_start(paths, plan, "R2"), 1)
        with self.assertRaises(ValueError):
            annotate_okn.resolve_start(paths, plan, "B7")
        self.assertEqual(self.open(paths, start=2).trial_id, "R3")

    def test_close_saves_unsaved_changes(self):
        a = self.open(self.queue("R1"))
        a.on_click(FakeEvent(a.ax_a, 2.3))
        a.on_close(None)
        self.assertEqual(len(annotate_okn.load_annotations(self.labels, "R1", "AA")[0]), 1)

    def test_other_annotators_labels_are_kept(self):
        annotate_okn.save_annotations(self.labels, "R1", "BB", [(5.0, "artifact")], "manual", complete=True)
        a = self.open(self.queue("R1", "R2"))
        self.assertEqual(a.events, [])                      # BB's labels are not shown as AA's
        a.on_click(FakeEvent(a.ax_a, 2.3))
        a.go(1)
        self.assertEqual(annotate_okn.load_annotations(self.labels, "R1", "BB")[0], [(5.0, "artifact")])

    def test_evaluation_trials_never_get_suggestions_in_a_mixed_queue(self):
        plan = {"R1": {"split": "evaluation", "pilot_id": "A3"}, "R2": {"split": "development", "pilot_id": "A1"}}
        real = annotate_okn.propose_candidates
        calls = []

        def spy(*args, **kwargs):
            calls.append(1)
            return real(*args, **kwargs)
        with unittest.mock.patch.object(annotate_okn, "propose_candidates", spy):
            a = self.open(self.queue("R1", "R2"), assisted=True, plan=plan)
            self.assertEqual((a.split, a.suggestions_allowed, a.suggestions, calls), ("evaluation", False, [], []))
            a.on_key(FakeEvent(key="t"))
            a.on_key(FakeEvent(key="y"))
            self.assertEqual((a.suggestions_shown, a.events, a.method), (False, [], "manual"))
            self.assertIn("held-out", a.message)
            a.go(1)
        self.assertTrue(a.suggestions_allowed)
        self.assertEqual(len(calls), 1)
        a.on_key(FakeEvent(key="t"))
        self.assertTrue(a.suggestions_shown)

    def test_split_queue_uses_plan_order_and_rejects_missing_files(self):
        for name in ("R1", "R2", "R3"):
            self.recording(name)
        plan_path = self.dir / "plan.csv"
        plan_path.write_text("split,order,pilot_id,trial_id,note\n"
                             "evaluation,2,A4,R1,\ndevelopment,1,A1,R2,\nevaluation,1,A3,R3,\n")
        plan = annotate_okn.load_plan(plan_path)
        queue = annotate_okn.split_queue("evaluation", self.dir / "trials", plan)
        self.assertEqual([p.stem for p in queue], ["R3", "R1"])
        self.assertEqual([p.stem for p in annotate_okn.split_queue("development", self.dir / "trials", plan)], ["R2"])
        plan["R9"] = {"split": "evaluation", "order": "3", "pilot_id": "A5", "trial_id": "R9"}
        with self.assertRaisesRegex(ValueError, "missing recordings"):
            annotate_okn.split_queue("evaluation", self.dir / "trials", plan)

    def test_navigation_labels_stay_readable_by_evaluate(self):
        a = self.open(self.queue("R1", "R2"))
        a.on_click(FakeEvent(a.ax_a, 2.3))
        a.on_key(FakeEvent(key="x"))
        a.go(1)
        with open(self.labels / "events.csv") as f:
            self.assertEqual(f.readline().strip().split(","), annotate_okn.EVENT_FIELDS)
        with open(self.labels / "reviews.csv") as f:
            self.assertEqual(f.readline().strip().split(","), annotate_okn.REVIEW_FIELDS)
        scored, skipped = evaluate_okn.evaluate(self.labels, self.dir / "trials")
        self.assertEqual(([s["trial_id"] for s in scored], skipped), (["R1"], []))

    def test_label_guide_follows_each_trials_stripe_direction(self):
        right, left = self.recording("R1"), self.recording("R2")
        still = self.recording("R3", mode="fixationStillStripes")
        for path, direction in ((right, "rightward"), (left, "leftward")):
            meta = json.loads(path.with_suffix(".json").read_text())
            meta["stimulus"]["direction"] = direction
            path.with_suffix(".json").write_text(json.dumps(meta))
        a = self.open([right, left, still])
        self.assertIn("UP", a.label_guide()[1][1])          # rightward: resets jump up
        a.go(1)
        self.assertIn("DOWN", a.label_guide()[1][1])        # leftward: resets jump down
        a.go(1)
        self.assertEqual(a.label_guide()[0], "stripes are STILL")

    def test_zoom_keys_stay_inside_the_recording(self):
        a = self.open(self.queue("R1"))
        full = a.ax_a.get_xlim()
        a.on_key(FakeEvent(key="+"))
        lo, hi = a.ax_a.get_xlim()
        self.assertAlmostEqual(hi - lo, (full[1] - full[0]) / 2)
        for _ in range(5):
            a.on_key(FakeEvent(key="shift+right"))
        self.assertAlmostEqual(a.ax_a.get_xlim()[1], full[1])
        a.on_key(FakeEvent(key="r"))
        self.assertEqual(a.ax_a.get_xlim(), full)


class PlanTests(unittest.TestCase):
    def test_pilot_01_plan_keeps_the_documented_split(self):
        plan = annotate_okn.load_plan()
        by_split = {s: sorted(r["pilot_id"] for r in plan.values() if r["split"] == s) for s in annotate_okn.SPLITS}
        self.assertEqual(by_split["evaluation"], ["A3", "A4", "A5", "B2", "B3", "C2", "C3"])
        self.assertEqual(by_split["development"], ["A1", "A2", "B1", "C1", "V5"])


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
        self.assertEqual(evaluate_okn.prf(0, 2, 0), (0.0, None, 0.0))   # fixation trial with false hits
        self.assertEqual(evaluate_okn.prf(0, 0, 4), (None, 0.0, 0.0))
        self.assertEqual(evaluate_okn.prf(0, 2, 4), (0.0, 0.0, 0.0))

    def test_all_predictions_near_uncertain_label_are_excluded(self):
        s = evaluate_okn.score_trial([(2.0, "uncertain")], [1.95, 2.0, 2.05, 3.0], 0.1)
        self.assertEqual((s["fp"], s["excluded_uncertain"]), (1, 3))

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
