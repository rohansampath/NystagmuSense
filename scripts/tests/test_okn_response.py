"""Tests for trial-level OKN response metrics. SYNTHETIC signals only."""

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analysis" / "okn_response"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_okn  # noqa: E402
import response_metrics as rm  # noqa: E402
from test_okn_filters import DT, session  # noqa: E402

_spec = importlib.util.spec_from_file_location("analyze_response", ROOT / "analysis/okn_response/analyze_response.py")
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)


def okn(stim, n=600, period=60, amplitude=4.0, noise=0.03, seed=0):
    """Sawtooth whose slow drift is opposite to the reset sign; resets have the stimulus sign."""
    k = np.arange(n) % period
    angle = -stim * amplitude * (k / (period - 1) - 0.5)
    return angle + noise * np.random.default_rng(seed).standard_normal(n)


class SlowPhase(unittest.TestCase):
    def test_clean_okn_has_the_right_drift_and_resets_are_excluded(self):
        for stim in (1, -1):
            m = rm.trial_metrics(session(okn(stim, noise=0), stim_direction=stim))
            drift = 4.0 / (59 * DT)                                   # deg/s of the slow ramp
            self.assertAlmostEqual(m["slow_median"], -stim * drift, delta=0.05 * drift)
            self.assertAlmostEqual(m["aligned_slow_median"], drift, delta=0.05 * drift)
            self.assertLess(m["slow_mean_abs"], 1.2 * drift)          # reset velocity never leaks in
            self.assertGreater(m["slow_consistency"], 0.95)
            self.assertEqual(m["reset_consistency"], 1.0)
            self.assertGreater(m["fast_rate_consistent"], 8)

    def test_direction_scores_reverse_when_the_stimulus_is_flipped(self):
        angle = okn(1)
        right = rm.trial_metrics(session(angle, stim_direction=1))
        wrong = rm.trial_metrics(session(angle, stim_direction=-1))
        self.assertGreater(right["aligned_slow_median"], 0)
        self.assertLess(wrong["aligned_slow_median"], 0)
        self.assertAlmostEqual(right["slow_consistency"] + wrong["slow_consistency"], 1, places=6)
        self.assertEqual(wrong["fast_rate_consistent"], 0)

    def test_flat_signal_is_near_zero_not_unavailable(self):
        m = rm.trial_metrics(session(np.zeros(600) + 0.02 * np.random.default_rng(1).standard_normal(600),
                                     stim_direction=1))
        self.assertTrue(m["slow_available"])
        self.assertLess(abs(m["aligned_slow_median"]), 0.5)
        self.assertEqual(m["fast_rate_consistent"], 0)

    def test_isolated_saccades_do_not_create_slow_phase_drift(self):
        angle = np.zeros(600)
        for start in (150, 400):
            angle[start:] += 3.0                                     # two step saccades, no drift
        m = rm.trial_metrics(session(angle, stim_direction=1))
        self.assertLess(abs(m["slow_median"]), 0.05)
        self.assertEqual(m["n_fast"], 2)

    def test_too_little_valid_data_is_unavailable_not_zero(self):
        data = session(okn(1), stim_direction=1)
        data["tracked"][45:] = 0                                     # under 1 s tracked
        m = rm.trial_metrics(data)
        self.assertFalse(m["slow_available"])
        for k in ("slow_median", "aligned_slow_median", "slow_consistency", "apparent_gain"):
            self.assertIsNone(m[k], k)

    def test_gaps_and_blinks_are_excluded(self):
        data = session(okn(1), stim_direction=1)
        data["blink_left"][200:230] = 1.0
        data["tracked"][400:420] = 0
        m = rm.trial_metrics(data)
        self.assertLess(m["valid_fraction"], 0.95)
        self.assertGreater(m["slow_consistency"], 0.9)

    def test_noisy_tracking_still_gives_a_positive_aligned_drift(self):
        m = rm.trial_metrics(session(okn(-1, noise=0.15, seed=3), stim_direction=-1))
        self.assertGreater(m["aligned_slow_median"], 0)
        self.assertGreater(m["slow_consistency"], 0.55)


class StillStripes(unittest.TestCase):
    def test_still_trials_use_the_best_case_hypothetical_direction(self):
        angle = okn(1)
        still = rm.trial_metrics(session(angle, stim_direction=0))
        moving = rm.trial_metrics(session(angle, stim_direction=1))
        self.assertEqual(still["direction_basis"], "best-case hypothetical (still stripes)")
        self.assertAlmostEqual(still["aligned_slow_median"], moving["aligned_slow_median"])
        self.assertAlmostEqual(still["slow_consistency"], moving["slow_consistency"])
        self.assertIsNone(still["apparent_gain"])                    # no stimulus speed to compare with


class Gain(unittest.TestCase):
    def test_stimulus_angular_speed_needs_a_known_device_and_distance(self):
        deg = rm.stimulus_deg_per_s(126, "iPhone17,1", 27.5)
        self.assertAlmostEqual(deg, np.degrees(126 * 25.4 / (460 / 3) / 275), places=6)
        self.assertTrue(4.0 < deg < 4.7)
        for args in ((126, "iPhone99,9", 27.5), (126, "iPhone17,1", None), (126, "iPhone17,1", 0), (None, "iPhone17,1", 27)):
            self.assertIsNone(rm.stimulus_deg_per_s(*args), args)

    def test_gain_is_eye_velocity_over_stimulus_velocity_in_the_same_units(self):
        m = rm.trial_metrics(session(okn(1, noise=0), stim_direction=1), 126, "iPhone17,1", 27.5)
        self.assertAlmostEqual(m["apparent_gain"], m["aligned_slow_median"] / m["stimulus_deg_s"])
        self.assertIsNone(rm.trial_metrics(session(okn(1), stim_direction=1), 126, "Pixel", 27.5)["apparent_gain"])


class Classification(unittest.TestCase):
    def test_auc_threshold_and_unavailable_scores(self):
        self.assertEqual(ar.auc([3, 4], [1, 2]), 1.0)
        self.assertEqual(ar.auc([None], [0.0]), 0.0)                 # unavailable never counts as evidence
        self.assertEqual(ar.auc([1], [1]), 0.5)
        thr = ar.best_threshold([3, 4, 5], [1, 2])
        self.assertTrue(2 < thr <= 3)
        self.assertFalse(ar.positive(None, -1e9))

    def test_confusion_counts_only_okn_and_still(self):
        rows = [dict(condition="OKN", aligned_slow_median=2.0), dict(condition="OKN", aligned_slow_median=None),
                dict(condition="FIXSTILL", aligned_slow_median=0.1), dict(condition="FIXMOVE", aligned_slow_median=5.0)]
        c = ar.confusion(rows, "B", lambda r: dict(A=0, B=1.0, C=0))
        self.assertEqual((c["tp"], c["fn"], c["tn"], c["fp"]), (1, 1, 1, 0))


if __name__ == "__main__":
    unittest.main()
