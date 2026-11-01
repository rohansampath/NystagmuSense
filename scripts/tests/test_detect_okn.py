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
    def data_for(self, t, angle):
        a = np.radians(-np.asarray(angle))
        return {"t_s": np.asarray(t), "tracked": np.ones(len(t)),
                "left_dir_x": np.sin(a), "right_dir_x": np.sin(a),
                "left_dir_z": np.cos(a), "right_dir_z": np.cos(a)}

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
        data = self.data_for(np.arange(10) / RATE, np.zeros(10))
        data.update(blink_left=np.array([0, 0, 0, 0, 0.9, 0, 0, 0, 0, 0.0]),
                    blink_right=np.zeros(10))
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

    def test_jittered_timestamps_preserve_constant_velocity(self):
        t = np.cumsum(np.tile([0.008, 0.025], 30))
        r = detect_okn.analyse(self.data_for(t, 10 * t), detect_okn.Params())
        np.testing.assert_allclose(r["velocity"], 10, atol=1e-6)

    def test_dropped_frames_do_not_create_a_fast_phase(self):
        t = np.r_[np.arange(20) / RATE, 2 + np.arange(20) / RATE]
        angle = np.r_[np.zeros(20), np.full(20, 15)]
        r = detect_okn.analyse(self.data_for(t, angle), detect_okn.Params())
        self.assertEqual(r["fast"], [])
        self.assertTrue(all(s["end"] - s["start"] < 0.4 for s in r["slow"]))
        np.testing.assert_allclose(r["velocity"], 0, atol=1e-6)

    def test_beats_cannot_bridge_invalid_samples(self):
        data = detect_okn.load_session(self.run_detector(synthetic_csv(okn_angle))[1])
        baseline = detect_okn.analyse(data, detect_okn.Params(pad_ms=0))
        # Remove the final slow sample immediately before every reset. It must
        # break the slow/fast pairing, even though the time gap is under 0.1 s.
        for beat in baseline["beats"]:
            i = np.searchsorted(data["t_s"], beat["slow"]["end"])
            data["tracked"][i] = 0
        r = detect_okn.analyse(data, detect_okn.Params(pad_ms=0))
        self.assertEqual(r["beats"], [])

    def test_beat_does_not_skip_an_intervening_fast_phase(self):
        slow = [dict(start=0, end=0.5, velocity=10)]
        fast = [dict(start=0.52, direction=1), dict(start=0.56, direction=-1)]
        self.assertEqual(detect_okn.detect_beats(slow, fast, detect_okn.Params()), [])

    def test_direction_reversals_are_not_merged(self):
        t = np.linspace(0, 2, 121)
        beats = [dict(time=time, direction=d, slow_velocity=10 * d)
                 for time, d in [(0.2, 1), (0.5, 1), (1.5, -1), (1.8, -1)]]
        p = detect_okn.Params(window_s=1, step_s=0.5)
        intervals = detect_okn.merge_windows(detect_okn.okn_windows(t, beats, p), beats)
        self.assertEqual([iv["direction"] for iv in intervals], [1, -1])

    def test_candidate_offset_never_exceeds_recording(self):
        t = np.linspace(0, 0.3, 19)
        beats = [dict(time=time, direction=1, slow_velocity=10) for time in [0.1, 0.2]]
        p = detect_okn.Params()
        intervals = detect_okn.merge_windows(detect_okn.okn_windows(t, beats, p), beats)
        self.assertTrue(intervals)
        self.assertLessEqual(intervals[-1]["offset"], t[-1])

    def test_last_window_includes_non_aligned_recording_tail(self):
        t = np.linspace(0, 3.3, 199)
        beats = [dict(time=time, direction=1, slow_velocity=10) for time in [2.8, 3.2]]
        self.assertTrue(detect_okn.okn_windows(t, beats, detect_okn.Params()))

    def test_single_available_blink_channel_is_used(self):
        t = np.arange(10) / RATE
        data = self.data_for(t, np.zeros(10))
        data["blink_left"] = np.zeros(10)
        data["blink_left"][4] = 0.9
        r = detect_okn.analyse(data, detect_okn.Params(pad_ms=0))
        self.assertFalse(r["valid"][4])

    def test_nonfinite_and_zero_eye_directions_are_invalid(self):
        t = np.arange(20) / RATE
        data = self.data_for(t, np.zeros(20))
        data["left_dir_x"][:10] = np.inf
        data["left_dir_z"][10:] = 0
        r = detect_okn.analyse(data, detect_okn.Params())
        self.assertFalse(r["valid"].any())

    def test_invalid_parameters_fail_cleanly(self):
        _, path = self.run_detector(synthetic_csv(okn_angle))
        cases = [("step-s", "0"), ("window-s", "nan"), ("min-beats", "0"),
                 ("sg-polyorder", "0"), ("sg-polyorder", "-1"),
                 ("pad-ms", "-1"), ("min-agreement", "1.1")]
        for name, value in cases:
            with self.subTest(name=name, value=value), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(detect_okn.main([path, "--" + name, value]), 1)

    def test_extra_csv_fields_are_rejected(self):
        text = synthetic_csv(okn_angle).splitlines()
        text[1] += ",unexpected"
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("\n".join(text))
        self.addCleanup(Path(f.name).unlink)
        with self.assertRaises(detect_okn.SessionError):
            detect_okn.load_session(f.name)

    def test_stimulus_reversal_is_not_reported_as_one_direction(self):
        self.assertEqual(detect_okn.stimulus_direction({"stim_displacement_pt":
                         np.array([0, 10, 20, 10, 5])}), 0)

    def test_quadratic_angle_derivative_on_irregular_samples(self):
        t = np.cumsum(np.tile([0.008, 0.025], 30))
        r = detect_okn.analyse(self.data_for(t, 3 * t**2 + 2 * t), detect_okn.Params())
        np.testing.assert_allclose(r["velocity"], 6 * t + 2, atol=1e-6)

    def test_gap_breaks_candidate_windows_even_with_beats_on_both_sides(self):
        data = detect_okn.load_session(self.run_detector(synthetic_csv(okn_angle))[1])
        # Keep short windows of actual slow/reset waveforms separated by gaps.
        keep = (data["t_s"] < 4) | (data["t_s"] > 6)
        data = {k: values[keep] for k, values in data.items()}
        r = detect_okn.analyse(data, detect_okn.Params())
        self.assertTrue(r["intervals"])
        self.assertTrue(all(iv["offset"] < 4 or iv["onset"] > 6 for iv in r["intervals"]))

    def test_valid_but_too_short_runs_do_not_become_slow_phases(self):
        t = np.arange(60) / RATE
        data = self.data_for(t, 10 * t)
        data["tracked"][4::5] = 0
        r = detect_okn.analyse(data, detect_okn.Params(pad_ms=0, sg_window=7))
        self.assertFalse(np.isfinite(r["velocity"]).any())
        self.assertEqual(r["slow"], [])
        self.assertEqual(r["intervals"], [])


if __name__ == "__main__":
    unittest.main()
