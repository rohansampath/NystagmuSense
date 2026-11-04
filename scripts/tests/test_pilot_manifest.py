"""The published Pilot 01 cohort must survive missing private inputs."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "analysis/pilot_01/run_pilot.py"
spec = importlib.util.spec_from_file_location("pilot_01", SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotManifestTests(unittest.TestCase):
    def test_missing_inputs_leave_published_outputs_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "analysis"
            out.mkdir()
            manifest = out / "manifest.csv"
            with manifest.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["filename"])
                writer.writerows([[f"trial{i}"] for i in range(21)])
            original = manifest.read_bytes()
            metrics = out / "metrics_per_trial.csv"
            metrics.write_text("published metrics\n")
            with patch.object(pilot, "ROOT", root), patch.object(pilot, "OUT", out):
                with self.assertRaisesRegex(FileNotFoundError, "no outputs changed"):
                    pilot.main()
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(metrics.read_text(), "published metrics\n")
            self.assertFalse((out / "figures").exists())
