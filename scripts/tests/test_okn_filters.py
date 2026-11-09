import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analysis" / "pilot_03"))
import compare_filters  # noqa: E402
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402
import okn_filters as F  # noqa: E402

FS = 60.01
DT = 1 / FS


def session(angle_deg, stim_direction=1, tracked=None):
    """Synthetic session dict in detect_okn.load_session's format; eye_angle() returns angle_deg."""
    angle_deg = np.asarray(angle_deg, float)
    n = len(angle_deg)
    rad = np.radians(-angle_deg)
    x, z = np.sin(rad), np.cos(rad)
    return {"t_s": np.arange(n) * DT, "tracked": np.ones(n) if tracked is None else tracked,
            "left_dir_x": x, "left_dir_z": z, "right_dir_x": x.copy(), "right_dir_z": z.copy(),
            "blink_left": np.zeros(n), "blink_right": np.zeros(n),
            "stim_displacement_pt": stim_direction * np.arange(n, dtype=float)}


def sawtooth(reset_sign, n=600, period=60, amplitude=4.0):
    """Slow drift against reset_sign with a one-frame reset every `period` samples."""
    k = np.arange(n) % period
    return -reset_sign * amplitude * (k / (period - 1) - 0.5)


class Butterworth(unittest.TestCase):
    def test_removes_high_frequency_noise_and_keeps_slow_signal(self):
        t = np.arange(600) * DT
        clean = 2 * np.sin(2 * np.pi * 1.0 * t)
        noisy = clean + 0.3 * np.random.default_rng(0).standard_normal(600)
        smooth = F.butter_lowpass(noisy, FS, 8)
        self.assertLess(np.sqrt(np.mean((smooth - clean) ** 2)), 0.5 * np.sqrt(np.mean((noisy - clean) ** 2)))
        basis = np.sin(2 * np.pi * 1.0 * t)
        self.assertAlmostEqual(smooth @ basis / (basis @ basis), 2.0, delta=0.05)   # 1 Hz amplitude kept

    def test_zero_phase(self):
        t = np.arange(600) * DT
        x = np.sin(2 * np.pi * 2 * t)
        y = F.butter_lowpass(x, FS, 8)
        lag = np.argmax(np.correlate(y[100:-100], x[100:-100], "full")) - (len(x[100:-100]) - 1)
        self.assertEqual(lag, 0)

    def test_cutoff_must_be_below_nyquist(self):
        with self.assertRaises(ValueError):
            F.butter_lowpass(np.zeros(50), FS, 31)

    def test_irregular_sampling_is_refused(self):
        t = np.cumsum(np.r_[0, np.full(30, DT), 1.5 * DT, np.full(30, DT)])
        with self.assertRaises(ValueError):
            F.run_rate(t)


class Velocity(unittest.TestCase):
    def test_uses_timestamps_and_keeps_a_ramp_through_the_boundaries(self):
        t = np.arange(200) * DT
        angle = 10 * t                                            # 10 deg/s
        valid = np.ones(200, bool)
        for method in ("bw", "bw+sg"):
            v = F.velocity(t, angle, valid, DT, method, cutoff=8)
            self.assertTrue(np.allclose(v, 10, atol=0.05), method)  # odd padding: no edge transient on a trend

    def test_gap_is_never_filtered_across(self):
        angle = np.r_[np.zeros(100), np.full(5, np.nan), np.full(100, 3.0)]
        t = np.arange(len(angle)) * DT
        valid = np.isfinite(angle)
        for method in F.METHODS:
            v = F.velocity(t, angle, valid, DT, method, cutoff=8)
            self.assertTrue(np.all(np.isnan(v[100:105])), method)
            self.assertLess(np.nanmax(np.abs(v)), 1e-6, method)   # a level change hidden in the gap is no reset

    def test_short_segments(self):
        angle = np.r_[np.zeros(3), np.nan, np.arange(6.0), np.nan, np.zeros(50)]
        t = np.arange(len(angle)) * DT
        valid = np.isfinite(angle)
        for method in F.METHODS:
            v = F.velocity(t, angle, valid, DT, method, cutoff=8)
            self.assertTrue(np.all(np.isnan(v[:3])), method)        # shorter than sg_window: no velocity
            self.assertTrue(np.all(np.isfinite(v[4:10])), method)   # 6 samples: filtered with a shortened pad

    def test_sg_method_is_the_unchanged_baseline(self):
        rng = np.random.default_rng(3)
        data = session(sawtooth(1) + 0.05 * rng.standard_normal(600))
        data["tracked"][200:204] = 0
        for thr in (22, 40):
            ours = [(f["start"], f["end"], f["direction"]) for f in F.fast_phases(data, "sg", thr)]
            base = [(f["start"], f["end"], f["direction"])
                    for f in detect_okn.analyse(data, detect_okn.Params(fast_threshold=thr))["fast"]]
            self.assertEqual(ours, base)


class Direction(unittest.TestCase):
    def test_rightward_and_leftward_stimuli_keep_only_resets_against_the_stripes(self):
        for sign in (1, -1):
            for method, cutoff in (("sg", None), ("bw", 12), ("bw+sg", 12)):
                right = F.predict(session(sawtooth(sign), stim_direction=sign), method, 15, cutoff)
                wrong = F.predict(session(sawtooth(sign), stim_direction=-sign), method, 15, cutoff)
                self.assertEqual(len(right), 9, (sign, method))
                self.assertEqual(wrong, [], (sign, method))

    def test_still_stripes_keep_every_fast_phase_for_false_positive_counting(self):
        data = session(sawtooth(1), stim_direction=0)
        for method, cutoff in (("sg", None), ("bw", 12)):
            preds = F.predict(data, method, 15, cutoff)
            self.assertEqual(len(preds), 9)
            s = evaluate_okn.score_trial([], preds, 0.1, artifacts="exclude")
            self.assertEqual((s["tp"], s["fp"], s["fn"]), (0, 9, 0))


class Sweep(unittest.TestCase):
    def trials(self):
        out = []
        for i, sign in enumerate((1, -1)):
            data = session(sawtooth(sign) + 0.05 * np.random.default_rng(i).standard_normal(600), stim_direction=sign)
            t, angle, valid, dt = F.signal(data)
            resets = [float(t[k]) for k in range(59, 600, 60) if k + 1 < 600]
            out.append(dict(trial_id=f"T{i}", row=dict(participant=f"P0{i + 1}", condition="OKN",
                                                        direction="RIGHT" if sign > 0 else "LEFT"),
                            data=data, t=t, angle=angle, valid=valid, dt=dt, duration=float(t[-1]),
                            events=[(x, "fast_phase") for x in resets]))
        return out

    def test_sweep_is_reproducible(self):
        configs = [("sg", None, 22), ("bw", 8, 20), ("bw+sg", 12, 18)]
        a, _ = compare_filters.run_sweep(self.trials(), configs)
        b, _ = compare_filters.run_sweep(self.trials(), configs)
        strip = lambda r: {c: [(s["tp"], s["fp"], s["fn"]) for s in v] for c, v in r.items()}
        self.assertEqual(strip(a), strip(b))
        self.assertTrue(all(s["tp"] == 9 for s in a[("sg", None, 22)]))

    def test_selection_prefers_f1_then_fewer_false_positives_then_less_processing(self):
        g = lambda f1, fp: dict(f1=f1, fp_per_10s=fp)
        self.assertEqual(compare_filters.choose({("bw", 8, 20): g(0.70, 1.0), ("bw", 8, 22): g(0.695, 0.5),
                                                 ("bw", 5, 14): g(0.60, 0.1)}), ("bw", 8, 22))
        self.assertEqual(compare_filters.choose({("bw", 8, 22): g(0.70, 0.5), ("bw", 15, 22): g(0.70, 0.5)}),
                         ("bw", 15, 22))
        self.assertEqual(compare_filters.choose({("sg", None, 20): g(0.70, 0.5), ("sg", None, 24): g(0.70, 0.5)}),
                         ("sg", None, 24))

    def test_matching_is_one_to_one(self):
        trial = self.trials()[0]
        s = compare_filters.score([trial], {"T0": [trial["events"][0][0], trial["events"][0][0] + 0.02]})[0]
        self.assertEqual((s["tp"], s["fp"], s["fn"]), (1, 1, 8))

    def test_grid_is_the_documented_one(self):
        g = compare_filters.grid()
        self.assertEqual(len(g), 16 + 2 * 4 * 16)
        self.assertEqual({c[1] for c in g if c[0] != "sg"}, {5, 8, 12, 15})
        self.assertIn(compare_filters.REFERENCE, g)


if __name__ == "__main__":
    unittest.main()
