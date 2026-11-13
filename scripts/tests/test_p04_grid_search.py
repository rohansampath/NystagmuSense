"""Tests for the Pilot 04 SG grid study. SYNTHETIC data only."""

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_okn  # noqa: E402
import evaluate_okn  # noqa: E402
from test_okn_filters import sawtooth, session  # noqa: E402

_spec = importlib.util.spec_from_file_location("grid_search", ROOT / "analysis/pilot_04/optimization/grid_search.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)


def summ(f1, still_fp=0.5, okn_recall=0.8, worst=0.6):
    return dict(all=dict(f1=f1), still=dict(fp_per_10s=still_fp), okn=dict(recall=okn_recall), worst_f1=worst)


class Grid(unittest.TestCase):
    def test_twenty_four_valid_configs_including_the_reference(self):
        g = gs.grid()
        self.assertEqual(len(g), 24)
        self.assertIn(gs.REFERENCE, g)
        for t, w, o in g:
            detect_okn.validate_params(detect_okn.Params(fast_threshold=t, sg_window=w, sg_polyorder=o))

    def test_sg_derivative_is_correct_for_every_window_and_order(self):
        t = np.arange(300) / 60.01
        angle = 5 * t ** 2                                         # velocity 10 t
        valid = np.ones(300, bool)
        for _, w, o in gs.grid():
            v = detect_okn.sg_velocity(angle, valid, t[1] - t[0], detect_okn.Params(sg_window=w, sg_polyorder=o), t=t)
            self.assertTrue(np.allclose(v[5:-5], 10 * t[5:-5], atol=1e-6), (w, o))

    def test_reference_matches_the_frozen_sg_direction_detector(self):
        with tempfile.TemporaryDirectory() as d:
            data = session(sawtooth(1) + 0.05 * np.random.default_rng(2).standard_normal(600), stim_direction=1)
            path = Path(d) / "x.csv"
            cols = ["t_s", "tracked", "left_dir_x", "left_dir_z", "right_dir_x", "right_dir_z", "blink_left",
                    "blink_right", "stim_displacement_pt"]
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(zip(*(data[c] for c in cols)))
            self.assertEqual(gs.predict(detect_okn.load_session(path), gs.REFERENCE),
                             evaluate_okn.detector_predictions(path, "sg-direction"))

    def test_reversing_or_missing_stimulus_is_refused(self):
        data = session(sawtooth(1), stim_direction=0)
        data["stim_displacement_pt"] = np.r_[np.arange(300.0), 300 - np.arange(300.0)]   # right, then left
        with self.assertRaises(ValueError):
            gs.predict(data, gs.REFERENCE)
        data["stim_displacement_pt"][5] = np.nan
        with self.assertRaises(ValueError):
            gs.predict(data, gs.REFERENCE)


class Selection(unittest.TestCase):
    def test_reference_is_kept_unless_beaten_by_more_than_the_tie_band(self):
        ref = gs.REFERENCE
        self.assertEqual(gs.choose({ref: summ(0.60), (24, 5, 2): summ(0.605)})[0], ref)
        self.assertEqual(gs.choose({ref: summ(0.60), (24, 5, 2): summ(0.62)})[0], (24, 5, 2))

    def test_more_still_false_positives_or_lost_okn_recall_disqualify(self):
        ref = gs.REFERENCE
        self.assertEqual(gs.choose({ref: summ(0.60), (18, 5, 2): summ(0.70, still_fp=0.9)})[0], ref)
        self.assertEqual(gs.choose({ref: summ(0.60), (18, 5, 2): summ(0.70, okn_recall=0.7)})[0], ref)
        self.assertEqual(gs.choose({ref: summ(0.60), (18, 5, 2): summ(0.70, worst=0.5)})[0], ref)

    def test_ties_prefer_fewer_still_false_positives_then_the_simpler_filter(self):
        ref = gs.REFERENCE
        cands = {ref: summ(0.60), (24, 7, 3): summ(0.70, still_fp=0.4), (24, 5, 2): summ(0.70, still_fp=0.4),
                 (20, 7, 2): summ(0.695, still_fp=0.3)}
        self.assertEqual(gs.choose(cands)[0], (20, 7, 2))
        del cands[(20, 7, 2)]
        self.assertEqual(gs.choose(cands)[0], (24, 5, 2))


class Manifest(unittest.TestCase):
    def test_development_manifest_keeps_the_validation_history(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "m.csv", Path(d) / "dev.csv"
            src.write_text("trial_id,participant,condition,eligibility,role,split,trial_number\n"
                           "A,P01,OKN,primary,external_validation,evaluation,1\n"
                           "B,P01,OKN,extra,,,2\n")
            gs.development_manifest(src, out)
            rows = list(csv.DictReader(open(out)))
            self.assertEqual((rows[0]["role"], rows[0]["original_role"], rows[0]["split"]),
                             ("p04_development_after_validation", "external_validation", "development"))
            self.assertEqual((rows[1]["role"], rows[1]["split"]), ("", ""))
            self.assertIn("external_validation", src.read_text())          # original untouched


if __name__ == "__main__":
    unittest.main()
