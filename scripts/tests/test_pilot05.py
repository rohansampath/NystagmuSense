"""Pilot 05 contrast model, receiver contract 2, manifest and analysis scaffolding.

All recordings here are SYNTHETIC. Code-value tests cannot show that a
display produces the nominal contrast.
"""

import contextlib
import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_okn_filters import session  # noqa: E402
from test_receive_recordings import ServerTestCase  # noqa: E402


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((ROOT / path).parent))
    spec.loader.exec_module(mod)
    return mod


cm = module("contrast_model", "analysis/pilot_05/contrast_model.py")
manifest = module("p05_manifest", "analysis/pilot_05/build_manifest.py")
analysis = module("analyze_contrast", "analysis/pilot_05/analyze_contrast.py")
FIXTURE = json.loads((ROOT / "scripts/tests/fixtures/contrast_codes.json").read_text())
COLUMNS = ["t_s", "tracked", "left_dir_x", "left_dir_z", "right_dir_x", "right_dir_z", "blink_left", "blink_right",
           "stim_bg_gray", "stim_displacement_pt"]


def okn_angle(stim, gain, n=600, period=60, seed=0):
    """Slow drift with the stimulus scaled by `gain`, resets against it; plus noise."""
    k = np.arange(n) % period
    return -stim * 4.0 * gain * (k / (period - 1) - 0.5) + 0.03 * np.random.default_rng(seed).standard_normal(n)


def write_p05(parent, participant, trial, percent, direction, gain=None, **stim_overrides):
    name = f"P05-{participant}_T{trial:03d}_OKN_{direction}_C{percent:03d}_20261113_{10 + trial // 60:02d}{trial % 60:02d}00"
    stim = 1 if direction == "RIGHT" else -1
    gain = percent / 80 if gain is None else gain
    data = session(okn_angle(stim, gain, seed=trial), stim_direction=stim)
    bg, bar = cm.codes(percent / 100)
    data["stim_bg_gray"] = np.full(len(data["t_s"]), bg)
    data["stim_displacement_pt"] = stim * 126 * data["t_s"]
    data["tracked"] = data["tracked"].astype(int)          # the app writes 1/0, not 1.0
    folder = Path(parent) / name
    folder.mkdir(parents=True)
    with open(folder / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(zip(*(data[c] for c in COLUMNS)))
    stimulus = dict(stripeWidthRatio=0.02, pitchToWidthRatio=2.4, trialMode="okn", direction="rightward" if stim > 0 else "leftward", speedPointsPerSecond=126,
                    michelsonContrast=percent / 100, meanRelativeLuminance=0.5, fixedBackgroundGray=bg, stripeGray=bar)
    stimulus.update(stim_overrides)
    meta = dict(schemaVersion=7, experimentID="P05", recordingName=name, participantID=participant, trialNumber=trial,
                directionCode=direction, issues=[], stimulus=stimulus, device=dict(model="iPhone17,1"),
                faceDistance=dict(check="passed", fractionOutsideRange=0, medianCm=27.5))
    (folder / f"{name}.json").write_text(json.dumps(meta))
    return name


def cohort(trials, people=("P01", "P02"), start=120):
    trial = start
    for p in people:
        for c in cm.LEVELS:
            for d in ("LEFT", "RIGHT"):
                for _ in range(2):
                    write_p05(trials, p, trial, c, d)
                    trial += 1
    return trial


class ContrastModel(unittest.TestCase):
    def test_fixture_matches_the_model(self):
        self.assertEqual(FIXTURE["mean_relative_luminance"], cm.MEAN)
        for level, row in zip(FIXTURE["levels"], cm.table()):
            for k in ("percent", "code", "contrast", "luminance_background", "luminance_bar", "code_background", "code_bar"):
                self.assertAlmostEqual(level[k], row[k], places=12) if isinstance(row[k], float) else \
                    self.assertEqual(level[k], row[k])

    def test_michelson_and_constant_mean_on_luminance_not_code_values(self):
        for p in cm.LEVELS:
            bg, bar = cm.luminances(p / 100)
            self.assertAlmostEqual(cm.michelson(bg, bar), p / 100, places=12)
            self.assertAlmostEqual(cm.BAR_FRACTION * bar + (1 - cm.BAR_FRACTION) * bg, cm.MEAN, places=12)
            cbg, cbar = cm.codes(p / 100)
            self.assertAlmostEqual(cm.srgb_decode(cbg), bg, places=12)
            if p:
                self.assertGreater(abs(cm.michelson(cbg, cbar) - p / 100), 1e-3)   # codes are not luminance

    def test_zero_contrast_is_uniform_and_quantisation_is_reported(self):
        self.assertEqual(*cm.codes(0))
        c8 = {r["percent"]: r["contrast_8bit"] for r in cm.table()}
        self.assertLess(abs(c8[5] - 0.05), 0.005)            # 8-bit rounding: 4.77 % instead of 5 %
        self.assertLess(abs(c8[80] - 0.80), 0.002)


class Receiver(ServerTestCase):
    def meta(self, name, contrast, **extra):
        return json.dumps(dict(schemaVersion=7, experimentID="P05", participantID=name[4:7], recordingName=name,
                               directionCode=name.split("_")[3], stimulus=dict(michelsonContrast=contrast), **extra))

    def cases(self):
        fixture = json.loads((ROOT / "scripts/tests/fixtures/recording_names.json").read_text())
        return [c for c in fixture["generated"] if c["testType"] == "P05"]

    def test_pilot_05_names_arrive_as_matching_pairs(self):
        for case in self.cases():
            name = case["name"]
            self.assertEqual(self.upload(stem=name, meta=self.meta(name, case["contrast"] / 100))[0], 201, name)
            self.assertEqual(sorted(p.name for p in (self.trials / name).iterdir()), [name + ".csv", name + ".json"])

    def test_contrast_must_agree_between_name_and_metadata(self):
        name = self.cases()[2]["name"]                                   # ..._C020_...
        for meta in (self.meta(name, 0.4), self.meta(name, None)):
            status, data = self.upload(stem=name, meta=meta)
            self.assertEqual((status, data["code"]), (400, "mismatched_metadata"))
        p04 = "P04-P01_T061_OKN_RIGHT_20261109_150000"
        meta = json.dumps(dict(experimentID="P04", participantID="P01", recordingName=p04,
                               stimulus=dict(michelsonContrast=0.2)))
        self.assertEqual(self.upload(stem=p04, meta=meta)[1]["code"], "mismatched_metadata")
        self.assertEqual(self.saved_folders(), [])

    def test_invalid_contrast_is_rejected_without_breaking_receiver(self):
        name = self.cases()[2]["name"]  # C020
        for value in (float("nan"), float("inf"), -float("inf"), True, -0.2, 1.2, 0.204):
            with self.subTest(value=value):
                status, data = self.upload(stem=name, meta=self.meta(name, value))
                self.assertEqual((status, data["code"]), (400, "mismatched_metadata"))
        for stimulus in (None, [], "bad"):
            meta = json.dumps(dict(recordingName=name, stimulus=stimulus))
            self.assertEqual(self.upload(stem=name, meta=meta)[1]["code"], "mismatched_metadata")
        self.assertEqual(self.saved_folders(), [])
        self.assertEqual(self.upload(stem=name, meta=self.meta(name, 0.2))[0], 201)

    def test_contract_1_names_are_still_accepted_and_retries_stay_idempotent(self):
        p04 = "P04-P01_T061_OKN_RIGHT_20261109_150000"
        meta = json.dumps(dict(experimentID="P04", participantID="P01", recordingName=p04,
                               stimulus=dict(trialMode="okn")))
        self.assertEqual(self.upload(stem=p04, meta=meta)[0], 201)
        name = self.cases()[0]["name"]
        self.assertEqual(self.upload(stem=name, meta=self.meta(name, 0.0))[0], 201)
        self.assertEqual(self.upload(stem=name, meta=self.meta(name, 0.0))[0], 200)
        self.assertEqual(self.upload(stem=name, meta=self.meta(name, 0.0, trialNumber=9))[1]["code"], "conflict")

    def test_health_reports_contract_2(self):
        self.assertEqual(self.request("GET", "/health")[1]["name_contract"], 2)


class Manifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trials = Path(self.tmp.name) / "trials"
        self.trials.mkdir()

    def test_full_plan_is_48_primary_recordings(self):
        cohort(self.trials)
        rows, cells = manifest.build(self.trials)
        self.assertEqual(sum(r["eligibility"] == "primary" for r in rows), 48)
        self.assertTrue(all(r["role"] == "exploratory_contrast" for r in rows))
        self.assertEqual(manifest.shortfalls(cells), [])

    def test_technical_checks_extras_and_shortfalls(self):
        trial = cohort(self.trials, people=("P01",))
        bad_codes = write_p05(self.trials, "P01", trial, 20, "LEFT", fixedBackgroundGray=0.9)
        bad_contrast = write_p05(self.trials, "P01", trial + 1, 40, "RIGHT", michelsonContrast=0.2)
        wrong_speed = write_p05(self.trials, "P01", trial + 2, 80, "RIGHT", speedPointsPerSecond=90)
        extra = write_p05(self.trials, "P01", trial + 3, 5, "LEFT")
        by_id = {r["trial_id"]: r for r in manifest.build(self.trials)[0]}
        self.assertIn("code values", by_id[bad_codes]["technical_notes"])
        self.assertIn("disagrees with name", by_id[bad_contrast]["technical_notes"])
        self.assertIn("speed", by_id[wrong_speed]["technical_notes"])
        self.assertEqual(by_id[extra]["eligibility"], "extra")
        write_p05(self.trials, "P02", 999, 0, "LEFT")
        self.assertIn("P02 C000 LEFT: 1/2", manifest.shortfalls(manifest.build(self.trials)[1]))

    def test_nonfinite_codes_and_changed_geometry_are_technical_failures(self):
        for i, overrides in enumerate((dict(stripeGray=float("nan")),
                                       dict(fixedBackgroundGray=float("nan")),
                                       dict(pitchToWidthRatio=3), dict(stripeWidthRatio=0.04),
                                       dict(michelsonContrast=0.204))):
            name = write_p05(self.trials, "P01", 800 + i, 20, "LEFT", **overrides)
            problems, _ = manifest.technical_check(self.trials / name)
            self.assertTrue(problems, overrides)
        self.assertTrue(all(r["eligibility"] == "excluded" for r in manifest.build(self.trials)[0]))

    def test_empty_trials_folder_writes_nothing(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(manifest.main(["--trials-dir", str(self.trials), "--output", str(Path(self.tmp.name) / "m.csv")]), 1)
        self.assertFalse((Path(self.tmp.name) / "m.csv").exists())


class Analysis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.trials = self.dir / "trials"
        self.trials.mkdir()
        self.manifest = self.dir / "manifest.csv"

    def run_analysis(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return analysis.main(["--manifest", str(self.manifest), "--trials-dir", str(self.trials),
                                  "--output-dir", str(self.dir / "out")])

    def test_synthetic_contrast_response_meets_the_feasibility_criteria(self):
        cohort(self.trials)
        self.manifest.write_text(manifest.render(manifest.build(self.trials)[0]))
        self.assertEqual(self.run_analysis(), 0)
        rows = list(csv.DictReader(open(self.dir / "out" / "trial_metrics.csv")))
        self.assertEqual(len(rows), 48)
        zero = [r for r in rows if r["contrast_percent"] == "0"]
        self.assertTrue(all(r["aligned_slow_median"] != "" for r in zero))     # scored against the intended direction
        crit = list(csv.DictReader(open(self.dir / "out" / "criteria.csv")))
        for name in ("1 high-contrast response", "2 weak 0 % response", "3 rising with contrast",
                     "4 direction reversal (>= 20 %)"):
            self.assertTrue(all(c["met"] == "True" for c in crit if c["criterion"] == name), name)
        for png in ("response_vs_contrast.png", "consistency_vs_contrast.png"):
            self.assertTrue((self.dir / "out" / png).stat().st_size > 1000)

    def test_flat_response_fails_the_criteria(self):
        for i, c in enumerate(cm.LEVELS):
            for d in ("LEFT", "RIGHT"):
                for r in range(2):
                    write_p05(self.trials, "P01", 200 + 4 * i + 2 * (d == "RIGHT") + r, c, d, gain=0.0)
        self.manifest.write_text(manifest.render(manifest.build(self.trials)[0]))
        self.run_analysis()
        crit = {c["criterion"]: c["met"] for c in csv.DictReader(open(self.dir / "out" / "criteria.csv"))
                if c["participant"] in ("P01", "all")}
        self.assertEqual(crit["1 high-contrast response"], "False")
        self.assertEqual(crit["4 direction reversal (>= 20 %)"], "False")

    def test_unavailable_responses_do_not_inflate_direction_reversal(self):
        rows = []
        for i in range(10):
            rows.append(dict(participant="P01", contrast_percent=80, direction="RIGHT",
                             aligned_slow_median=2.0 if i == 0 else None,
                             slow_consistency=0.8 if i == 0 else None,
                             slow_median=-2.0 if i == 0 else None, valid_fraction=0.95))
        result = next(r for r in analysis.criteria(rows) if r["criterion"].startswith("4 "))
        self.assertFalse(result["met"])
        self.assertEqual(result["value"], "0.1 of 10 trials")

    def test_all_unavailable_responses_still_produce_a_plot(self):
        path = self.dir / "unavailable.png"
        rows = [dict(participant="P01", contrast_percent=80, direction="RIGHT", aligned_slow_median=None)]
        analysis.plot(rows, "aligned_slow_median", "velocity", path)
        self.assertGreater(path.stat().st_size, 1000)

    def test_empty_and_missing_data_are_errors_not_results(self):
        self.manifest.write_text(",".join(manifest.FIELDS) + "\n")
        with self.assertRaises(SystemExit):
            self.run_analysis()
        name = write_p05(self.trials, "P01", 120, 20, "LEFT")
        self.manifest.write_text(manifest.render(manifest.build(self.trials)[0]))
        for f in (self.trials / name).iterdir():
            f.unlink()
        with self.assertRaises(SystemExit):
            self.run_analysis()
        self.assertFalse((self.dir / "out").exists())


if __name__ == "__main__":
    unittest.main()
