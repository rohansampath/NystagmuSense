"""Synthetic validation of the opt-in hybrid, independently of real trials."""

import contextlib
import hashlib
import io
import itertools
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import compare_okn
import detect_okn
import evaluate_okn
import hybrid_okn
import annotate_okn
from test_detect_okn import okn_angle, saccade_angle, synthetic_csv


def data_for(t, angle):
    a = np.radians(-np.asarray(angle))
    return dict(t_s=np.asarray(t), tracked=np.ones(len(t)),
                left_dir_x=np.sin(a), right_dir_x=np.sin(a),
                left_dir_z=np.cos(a), right_dir_z=np.cos(a))


def narrow_reset(t):
    """3 deg/s drift for 380 ms, then a 1.14 degree reset in 20 ms."""
    if not 2 <= t < 8:
        return 0.0
    phase = (t - 2) % 0.4
    return 3 * phase if phase < 0.38 else 1.14 * (1 - (phase - 0.38) / 0.02)


class SegmentationTests(unittest.TestCase):
    def test_dynamic_programming_matches_exhaustive_polyline_search(self):
        t = np.array([0, .013, .032, .05, .069, .084, .1, .12])
        y = np.array([0, .04, .1, 1.1, .9, .91, .95, 1.0])
        p = hybrid_okn.HybridParams()
        segments, sigma = hybrid_okn.segment_linear(t, y, p)
        penalty = p.penalty_scale * sigma**2 * math.log(len(t))

        def objective(knots):
            residual = sum(np.sum((y[a:b+1] - np.interp(t[a:b+1], t[[a, b]], y[[a, b]]))**2)
                           for a, b in zip(knots[:-1], knots[1:]))
            return residual + penalty * (len(knots) - 2)

        candidates = ([0, *[i + 1 for i, chosen in enumerate(mask) if chosen], len(t) - 1]
                      for mask in itertools.product([False, True], repeat=len(t) - 2))
        optimum = min(objective(knots) for knots in candidates)
        knots = [segments[0][0]] + [b for _, b in segments]
        self.assertAlmostEqual(objective(knots), optimum, places=10)

    def test_straight_drift_has_no_change_points_at_large_time_offset(self):
        t = 1e6 + np.arange(100) / 60
        angle = 80 + 4 * (t - t[0])
        segments, _ = hybrid_okn.segment_linear(t, angle, hybrid_okn.HybridParams())
        self.assertEqual(segments, [(0, 99)])

    def test_noise_estimate_on_irregular_samples(self):
        rng = np.random.default_rng(12)
        t = np.cumsum(rng.uniform(.01, .025, 4000))
        y = 4*t + rng.normal(0, .15, len(t))
        self.assertAlmostEqual(hybrid_okn.noise_sigma(t, y, .01), .15, delta=.015)


class HybridTests(unittest.TestCase):
    def run_method(self, fn, method="hybrid", noise=0, seed=0, t=None, p=None, direction=1):
        t = np.arange(600)/60 if t is None else t
        y = direction * np.array([fn(ti) for ti in t], dtype=float)
        y += np.random.default_rng(seed).normal(0, noise, len(t))
        return detect_okn.analyse(data_for(t, y), p or detect_okn.Params(), method=method)

    def test_narrow_resets_survive_when_sg_suppresses_them(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                sg = self.run_method(narrow_reset, method="sg", direction=direction)
                r = self.run_method(narrow_reset, direction=direction)
                self.assertEqual(sg["fast"], [])
                self.assertGreaterEqual(len(r["beats"]), 12)
                self.assertTrue(r["intervals"])
                self.assertTrue(all(f["direction"] == -direction for f in r["fast"]))
                self.assertAlmostEqual(np.median([b["slow_velocity"] for b in r["beats"]]),
                                       direction * 3, delta=.15)
                # Locate resets to within two frames, excluding the final return to fixation.
                expected = np.arange(2.38, 8, .4)
                for at in expected:
                    self.assertLess(min(abs(f["start"] - at) for f in r["fast"]), 2/60)

    def test_existing_three_frame_resets_work_across_noise_seeds(self):
        for direction in (-1, 1):
            for seed in range(4):
                with self.subTest(direction=direction, seed=seed):
                    r = self.run_method(okn_angle, noise=.15, seed=seed, direction=direction)
                    self.assertGreaterEqual(len(r["beats"]), 12)
                    self.assertAlmostEqual(np.median([b["slow_velocity"] for b in r["beats"]]),
                                           direction * 10, delta=1)

    def test_noisy_narrow_resets_recover_more_beats_than_baseline(self):
        for seed in range(4):
            fn = lambda t: 2 * narrow_reset(t)
            sg = self.run_method(fn, method="sg", noise=.15, seed=seed)
            r = self.run_method(fn, noise=.15, seed=seed)
            self.assertGreaterEqual(len(r["beats"]), 10)
            self.assertGreater(len(r["beats"]), len(sg["beats"]) + 6)

    def test_negative_controls_do_not_produce_okn_windows(self):
        for fn in (lambda t: 0, saccade_angle, lambda t: 2*np.sin(4*np.pi*t),
                   lambda t: 4 if 3 <= t < 3 + 1/60 else 0):
            for seed in range(3):
                with self.subTest(fn=fn, seed=seed):
                    r = self.run_method(fn, noise=.15, seed=seed)
                    self.assertEqual(r["windows"], [])
                    self.assertEqual(r["beats"], [])

    def test_reset_threshold_is_shared_with_baseline(self):
        r = self.run_method(narrow_reset, p=detect_okn.Params(fast_threshold=100))
        self.assertEqual(r["fast"], [])

    def test_long_fast_ramp_is_not_a_short_reset(self):
        r = self.run_method(lambda t: -60 * min(t, 1))
        self.assertEqual(r["fast"], [])
        self.assertEqual(r["beats"], [])

    def test_sg_slow_velocity_never_sees_reset_samples(self):
        r = self.run_method(narrow_reset)
        for s in r["slow"]:
            if s["accepted"]:
                mask = (r["t"] >= s["start"]) & (r["t"] <= s["end"])
                np.testing.assert_allclose(r["velocity"][mask], 3, atol=1e-7)

    def test_irregular_timestamps_keep_narrow_resets_and_drift(self):
        t = np.cumsum(np.tile([.013, .02], 300))
        # Keep observed reset slopes above the shared 40 deg/s gate even when
        # a 20 ms reset straddles two uneven camera intervals. Segmentation
        # cannot reconstruct motion that happened between missing samples.
        r = self.run_method(lambda ti: 2 * narrow_reset(ti), t=t)
        self.assertGreaterEqual(len(r["beats"]), 10)
        self.assertAlmostEqual(np.median([b["slow_velocity"] for b in r["beats"]]), 6, delta=.2)

    def test_untracked_and_absent_frames_break_entire_pipeline(self):
        t = np.arange(600)/60
        data = data_for(t, [okn_angle(ti) for ti in t])
        data["tracked"][(t > 4) & (t < 4.3)] = 0
        keep = (t < 6) | (t > 6.5)
        data = {k: v[keep] for k, v in data.items()}
        r = detect_okn.analyse(data, detect_okn.Params(), method="hybrid")
        self.assertTrue(r["beats"])
        for lo, hi in ((3.96, 4.34), (6, 6.5)):
            for item in r["fast"] + r["slow"] + r["segments"]:
                self.assertTrue(item["end"] < lo or item["start"] > hi, item)
            for iv in r["intervals"]:
                self.assertTrue(iv["offset"] < lo or iv["onset"] > hi, iv)
        for f in r["fast"]:
            self.assertEqual(f["start"], r["t"][f["i0"]])
            self.assertEqual(f["end"], r["t"][f["i1"] - 1])

    def test_blink_masks_false_reset(self):
        t = np.arange(120)/60
        y = np.zeros(len(t))
        y[60:63] = 10
        data = data_for(t, y)
        data["blink_left"] = np.zeros(len(t))
        data["blink_left"][60:63] = .9
        r = detect_okn.analyse(data, detect_okn.Params(), method="hybrid")
        self.assertEqual(r["fast"], [])
        self.assertTrue(np.all(np.isnan(r["velocity"][60:63])))

    def test_empty_tracking_and_short_runs(self):
        for count in (2, 4, 30):
            data = data_for(np.arange(count)/60, np.zeros(count))
            for tracked in (0, 1):
                data["tracked"][:] = tracked
                r = detect_okn.analyse(data, detect_okn.Params(), method="hybrid")
                self.assertEqual(r["fast"], [])
                self.assertEqual(r["beats"], [])
                self.assertEqual(r["windows"], [])

    def test_invalid_hybrid_parameters_and_unknown_method(self):
        data = data_for(np.arange(10)/60, np.zeros(10))
        for field in ("penalty_scale", "noise_floor_deg", "min_reset_amplitude_deg", "max_reset_s"):
            for bad in (0, -1, math.inf, math.nan):
                with self.subTest(field=field, bad=bad), self.assertRaises(detect_okn.SessionError):
                    detect_okn.analyse(data, detect_okn.Params(), method="hybrid",
                                       hybrid_params=hybrid_okn.HybridParams(**{field: bad}))
        with self.assertRaises(detect_okn.SessionError):
            detect_okn.analyse(data, detect_okn.Params(), method="unknown")


class ComparisonTests(unittest.TestCase):
    def test_output_summary_cannot_overwrite_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/"summary.csv"
            path.write_text(synthetic_csv(okn_angle))
            metadata = root/"summary.json"
            metadata.write_text('{"stimulus":{"trialMode":"okn"}}')
            original = metadata.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(compare_okn.main([str(path), "--output-dir", str(root)]), 1)
            self.assertEqual(metadata.read_bytes(), original)

    def test_cli_comparison_preserves_source_and_records_both_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"narrow.csv"
            path.write_text(synthetic_csv(narrow_reset))
            original = path.read_bytes()
            out = Path(tmp)/"out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(compare_okn.main([str(path), "--output-dir", str(out)]), 0)
            report = json.loads((out/"summary.json").read_text())
            self.assertEqual(path.read_bytes(), original)
            row = report["trials"][0]
            self.assertEqual(row["source_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(row["sg"]["fast_phases"], 0)
            self.assertGreater(row["hybrid"]["fast_phases"], 0)
            self.assertGreater((out/"narrow_comparison.png").stat().st_size, 1000)

    def test_cli_method_validation_and_baseline_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"okn.csv"
            path.write_text(synthetic_csv(okn_angle))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(detect_okn.main([str(path), "--method", "hybrid",
                                                "--cp-penalty-scale", "0"]), 1)
            data = detect_okn.load_session(path)
            default = detect_okn.analyse(data, detect_okn.Params())
            explicit = detect_okn.analyse(data, detect_okn.Params(), method="sg")
            self.assertEqual(default["fast"], explicit["fast"])
            self.assertEqual(default["beats"], explicit["beats"])
            np.testing.assert_array_equal(default["velocity"], explicit["velocity"])

    def test_evaluator_scores_both_on_identical_complete_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/"trials"/"R1"/"R1.csv"
            path.parent.mkdir(parents=True)
            path.write_text(synthetic_csv(narrow_reset))
            labels = root/"labels"
            annotate_okn.save_annotations(labels, "R1", "AA", [(2.38, "fast_phase")], "manual", True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = evaluate_okn.main(["--labels-dir", str(labels), "--trials-dir", str(root/"trials"),
                                            "--detector", "both"])
            self.assertEqual(result, 0)
            self.assertIn("Detector: sg (baseline)", output.getvalue())
            self.assertIn("Detector: hybrid (experimental)", output.getvalue())
            self.assertEqual(output.getvalue().count("PRIMARY (independent labels): 1 trials"), 2)


if __name__ == "__main__":
    unittest.main()
