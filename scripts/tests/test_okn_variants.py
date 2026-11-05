import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detect_okn  # noqa: E402
import okn_variants as v  # noqa: E402

DT = 1 / 60


def signal(angle, valid=None):
    t = np.arange(len(angle)) * DT
    valid = np.isfinite(angle) if valid is None else valid
    return dict(t=t, angle=np.asarray(angle, float), valid=valid, dt=DT)


def sawtooth(reset_sign=1, n=600, period=60, amplitude=2.0, rng=None):
    """Slow drift against reset_sign, then a one-frame reset; resets at samples period-1, 2·period-1, ..."""
    k = np.arange(n) % period
    angle = -reset_sign * amplitude * (k / (period - 1) - 0.5)
    if rng is not None:
        angle = angle + rng.normal(0, 0.03, n)
    return angle


def fast(start, direction, i0=0, i1=1):
    return dict(start=start, direction=direction, i0=i0, i1=i1)


class DirectionCheck(unittest.TestCase):
    def test_reset_sign_follows_stimulus(self):
        self.assertEqual(v.expected_reset_direction(1), 1)       # rightward stripes
        self.assertEqual(v.expected_reset_direction(-1), -1)     # leftward stripes
        self.assertEqual(v.expected_reset_direction(0), 0)       # still stripes: none

    def test_wrong_direction_fast_phases_are_dropped(self):
        phases = [fast(1.0, 1), fast(2.0, -1), fast(3.0, 1)]
        self.assertEqual([f["start"] for f in v.direction_filter(phases, 1)], [1.0, 3.0])
        self.assertEqual([f["start"] for f in v.direction_filter(phases, -1)], [2.0])

    def test_still_stripes_keep_every_fast_phase(self):
        phases = [fast(1.0, 1), fast(2.0, -1)]
        self.assertEqual(v.direction_filter(phases, 0), phases)

    def test_detector_output_on_rightward_and_leftward_sawtooth(self):
        for sign in (1, -1):
            r = signal(sawtooth(sign))
            p = detect_okn.Params(fast_threshold=20)        # SG spreads a 2° one-frame reset to ~36 deg/s
            r["velocity"] = detect_okn.sg_velocity(r["angle"], r["valid"], DT, p, t=r["t"])
            phases = detect_okn.detect_fast_phases(r["t"], r["angle"], r["velocity"], r["valid"], p)
            kept = v.direction_filter(phases, v.expected_reset_direction(sign))
            self.assertEqual(len(kept), 9)
            self.assertEqual(v.direction_filter(phases, v.expected_reset_direction(-sign)), [])


class LocalStep(unittest.TestCase):
    def test_clean_reset_has_its_amplitude_and_a_large_fit_improvement(self):
        r = signal(sawtooth(1))
        s = v.step_features(r, [fast(r["t"][60], 1, 60, 61)])[0]
        self.assertAlmostEqual(s["amplitude"], 2.0, delta=0.1)
        self.assertGreater(s["improvement"], 0.95)
        self.assertEqual(s["direction"], 1)
        self.assertLess(s["pre_slope"], 0)                        # slow phase drifts the other way

    def test_spike_that_returns_is_rejected(self):
        angle = np.zeros(120)
        angle[60] = 3.0
        r = signal(angle)
        self.assertEqual(v.linear_validate(r, [fast(r["t"][60], 1, 60, 61)]), [])

    def test_candidate_next_to_a_gap_is_not_fitted_across_it(self):
        angle = sawtooth(1, n=200)
        angle[61:64] = np.nan                                    # tracking lost right after the reset
        r = signal(angle)
        self.assertEqual(v.step_features(r, [fast(r["t"][60], 1, 60, 61)]), [None])

    def test_candidate_at_the_start_of_a_run_has_no_features(self):
        r = signal(sawtooth(1, n=200))
        self.assertEqual(v.step_features(r, [fast(0.0, 1, 0, 2)]), [None])

    def test_direction_of_the_step_must_match_the_fast_phase(self):
        r = signal(sawtooth(1))
        self.assertEqual(v.linear_validate(r, [fast(r["t"][60], -1, 60, 61)]), [])


class Standalone(unittest.TestCase):
    def test_finds_each_reset_once_at_the_transition(self):
        r = signal(sawtooth(1, rng=np.random.default_rng(0)))
        found = v.piecewise_resets(r)
        starts = np.array([c["start"] for c in found])
        expected = r["t"][np.arange(59, 600 - 3, 60)]             # last slow-phase sample before each reset
        self.assertEqual(len(starts), len(expected))
        self.assertLess(np.max(np.abs(starts - expected)), 2 * DT)

    def test_expected_direction_removes_opposite_steps(self):
        r = signal(sawtooth(1))
        self.assertTrue(v.piecewise_resets(r, expected=1))
        self.assertEqual(v.piecewise_resets(r, expected=-1), [])

    def test_noise_alone_gives_no_resets(self):
        r = signal(np.random.default_rng(1).normal(0, 0.05, 600))
        self.assertEqual(v.piecewise_resets(r), [])

    def test_slow_ramp_is_not_a_reset(self):
        r = signal(np.linspace(0, 3, 600))
        self.assertEqual(v.piecewise_resets(r), [])

    def test_never_fits_across_missing_data(self):
        angle = np.r_[np.zeros(100), np.full(5, np.nan), np.full(100, 2.0)]   # level change hidden in a gap
        self.assertEqual(v.piecewise_resets(signal(angle)), [])


if __name__ == "__main__":
    unittest.main()
