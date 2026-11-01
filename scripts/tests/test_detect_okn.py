"""Unit tests for detect_okn.py.

Run: python3 -m unittest discover scripts/tests   (needs numpy + scipy)

All recordings here are SYNTHETIC fixtures written in the app's CSV format;
they are not experimental data.
"""

import contextlib
import io
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detect_okn  # noqa: E402

HEADER = ("t_s,host_time_s,tracked,lookat_x_m,lookat_y_m,lookat_z_m,"
          "left_dir_x,left_dir_y,left_dir_z,right_dir_x,right_dir_y,right_dir_z,"
          "blink_left,blink_right,stim_bg_gray,stim_displacement_pt")
RATE, DURATION, NOISE_SD = 60, 10.0, 0.15


def okn_angle(t):
    """Fixation, then 2–8 s: 10 deg/s rightward for 0.35 s + 3.5 deg reset over 3 frames."""
    slow, reset = 0.35, 3 / RATE
    if not 2 <= t < 8:
        return 0.0
    phase = (t - 2) % (slow + reset)
    return 10 * phase if phase < slow else 3.5 * (1 - (phase - slow) / reset)


def saccade_angle(t):
    """±8 deg square wave, 0.7 s period."""
    return 8.0 if t % 0.7 < 0.35 else -8.0


def synthetic_csv(angle_fn, tracked=True, seed=0):
    """Rows in the app's format; eye angle + = subject's right → dir_x = sin(-angle)."""
    rng = np.random.default_rng(seed)
    lines = [HEADER]
    for i in range(int(DURATION * RATE)):
        t = i / RATE
        if not tracked:
            lines.append(f"{t:.6f},{100 + t:.6f},0,,,,,,,,,,,,1.000000,{90 * t:.3f}")
            continue
        a = math.radians(-(angle_fn(t) + rng.normal(0, NOISE_SD)))
        x, z = math.sin(a), math.cos(a)
        lines.append(f"{t:.6f},{100 + t:.6f},1,0,0,0.4,{x},0,{z},{x},0,{z},0,0,1.000000,{90 * t:.3f}")
    return "\n".join(lines) + "\n"


class DetectOKNTests(unittest.TestCase):
    def run_detector(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(text)
        self.addCleanup(Path(f.name).unlink)
        return detect_okn.analyse(detect_okn.load_session(f.name), detect_okn.Params()), f.name

    def test_synthetic_okn_is_detected(self):
        r, _ = self.run_detector(synthetic_csv(okn_angle))
        fast = r["fast"]
        self.assertLessEqual(abs(len(fast) - 15), 1, f"{len(fast)} fast phases")
        self.assertTrue(all(f["direction"] == -1 for f in fast), "all resets should be leftward")
        self.assertGreaterEqual(len(r["beats"]), 12)
        spv = np.median([b["slow_velocity"] for b in r["beats"]])
        self.assertAlmostEqual(spv, 10, delta=1.0)
        self.assertEqual(len(r["intervals"]), 1)
        iv = r["intervals"][0]
        self.assertTrue(iv["onset"] < 8 and iv["offset"] > 2, iv)
        self.assertEqual(iv["direction"], 1)
        self.assertEqual(r["stimulus"], 1)

    def test_back_and_forth_saccades_are_not_okn(self):
        r, _ = self.run_detector(synthetic_csv(saccade_angle))
        directions = {f["direction"] for f in r["fast"]}
        self.assertEqual(directions, {1, -1})
        self.assertEqual(r["windows"], [])
        self.assertEqual(r["intervals"], [])

    def test_all_untracked_does_not_crash(self):
        r, path = self.run_detector(synthetic_csv(okn_angle, tracked=False))
        self.assertFalse(r["valid"].any())
        self.assertEqual((r["fast"], r["beats"], r["intervals"]), ([], [], []))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(detect_okn.main([path]), 0)
        self.assertIn("no candidate OKN windows", out.getvalue())

    def test_blinks_are_masked_with_padding(self):
        data = {"t_s": np.arange(10) / RATE, "tracked": np.ones(10),
                "blink_left": np.array([0, 0, 0, 0, 0.9, 0, 0, 0, 0, 0.0]),
                "blink_right": np.zeros(10)}
        angle = np.zeros(10)
        valid = detect_okn.valid_mask(data["t_s"], angle, data, detect_okn.Params())
        # 50 ms pad at 60 Hz covers 3 samples each side of the blink at index 4.
        self.assertEqual(valid.tolist(), [True] + [False] * 7 + [True] * 2)

    def test_velocity_is_not_computed_across_gaps(self):
        t = np.arange(20) / RATE
        angle = 10 * t
        valid = np.ones(20, dtype=bool)
        valid[8:10] = False
        vel = detect_okn.sg_velocity(angle, valid, 1 / RATE, detect_okn.Params())
        self.assertTrue(np.all(np.isnan(vel[8:10])))
        np.testing.assert_allclose(vel[valid], 10, atol=1e-6)

    def test_missing_columns_fail_cleanly(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("t_s,tracked\n0,1\n0.1,1\n")
        self.addCleanup(Path(f.name).unlink)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(detect_okn.main([f.name]), 1)


if __name__ == "__main__":
    unittest.main()
