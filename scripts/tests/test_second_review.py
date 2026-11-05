import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "pilot_03"))
import second_review  # noqa: E402
import annotate_okn  # noqa: E402
import compare_detectors  # noqa: E402
from test_p03_benchmark import write_recording  # noqa: E402
import build_manifest  # noqa: E402

MANIFEST = ROOT / "analysis" / "pilot_03" / "manifest.csv"


class Selection(unittest.TestCase):
    def test_four_dot_moving_and_two_okn_from_development_only(self):
        picked = second_review.select(MANIFEST, 20261106)
        self.assertEqual([r["condition"] for r in picked], ["FIXMOVE"] * 4 + ["OKN"] * 2)
        self.assertTrue(all(r["split"] == "development" and r["eligibility"] == "primary" for r in picked))
        cells = {(r["participant"], r["direction"]) for r in picked[:4]}
        self.assertEqual(cells, {(p, d) for p in ("P01", "P02") for d in ("LEFT", "RIGHT")})
        okn = picked[4:]
        self.assertEqual([r["participant"] for r in okn], ["P01", "P02"])
        self.assertNotEqual(okn[0]["direction"], okn[1]["direction"])

    def test_reproducible_and_skips_recordings_shown_in_figures(self):
        a, b = second_review.select(MANIFEST, 1), second_review.select(MANIFEST, 1)
        self.assertEqual([r["trial_id"] for r in a], [r["trial_id"] for r in b])
        for seed in range(20):
            shown = {int(r["trial_number"]) for r in second_review.select(MANIFEST, seed)}
            self.assertFalse(shown & second_review.SHOWN_IN_FIGURES)


class Agreement(unittest.TestCase):
    def test_comparison_requires_one_annotator_and_uses_only_their_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trials, labels = root / "trials", root / "labels"
            tid = write_recording(trials, "P01", 1, "OKN", "RIGHT")
            rows = build_manifest.build(trials)[0]
            rows[0]["split"] = "development"
            manifest = root / "manifest.csv"
            manifest.write_text(build_manifest.render(rows))
            for who, time in (("AA", 1.0), ("BB", 2.0)):
                annotate_okn.save_annotations(labels, tid, who, [(time, "fast_phase")], "manual", True)
            with self.assertRaisesRegex(ValueError, "--annotator"):
                compare_detectors.load_trials(labels, trials, manifest)
            loaded = compare_detectors.load_trials(labels, trials, manifest, "AA")
            self.assertEqual(loaded[0]["events"], [(1.0, "fast_phase")])

    def test_one_to_one_matching_and_score(self):
        first = [(1.0, "fast_phase"), (2.0, "fast_phase"), (3.0, "uncertain")]
        second = [(1.05, "fast_phase"), (1.08, "fast_phase"), (4.0, "fast_phase")]
        pairs, only_first, only_second = second_review.agreement(first, second)
        self.assertEqual((len(pairs), only_first, len(only_second)), (1, [2.0], 2))
        self.assertAlmostEqual(second_review.agree_score(1, 1, 2), 2 / 5)
        self.assertIsNone(second_review.agree_score(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
