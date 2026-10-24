"""Unit tests for plot_gaze.py.

Run: python3 -m unittest discover scripts/tests

All CSVs here are SYNTHETIC fixtures for parser testing only; they are not
experimental recordings.
"""

import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plot_gaze  # noqa: E402

HEADER = ("t_s,host_time_s,tracked,lookat_x_m,lookat_y_m,lookat_z_m,"
          "left_dir_x,left_dir_y,left_dir_z,right_dir_x,right_dir_y,right_dir_z,"
          "stim_bg_gray,stim_displacement_pt")
TRACKED = "{t:.6f},{h:.6f},1,0.01,0.02,0.5,0.1,0,0.99,0.1,0,0.99,1.000000,0.000"
UNTRACKED = "{t:.6f},{h:.6f},0,,,,,,,,,,1.000000,0.000"


class PlotGazeTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_loads_and_marks_missing_as_nan(self):
        rows = [TRACKED.format(t=0, h=100), UNTRACKED.format(t=0.5, h=100.5),
                TRACKED.format(t=1, h=101)]
        data = plot_gaze.load_recording(self.write("\n".join([HEADER, *rows]) + "\n"))
        self.assertEqual(data["t_s"], [0, 0.5, 1])
        self.assertTrue(math.isnan(data["left_dir_x"][1]))

        stats = plot_gaze.compute_stats(data)
        self.assertEqual(stats["samples"], 3)
        self.assertEqual(stats["tracked"], 2)
        self.assertAlmostEqual(stats["mean_rate_hz"], 2.0)
        self.assertEqual(plot_gaze.untracked_spans(data["t_s"], data["tracked"]), [(0.5, 1)])

    def test_empty_recording_is_rejected(self):
        with self.assertRaisesRegex(plot_gaze.RecordingError, "no samples"):
            plot_gaze.load_recording(self.write(HEADER + "\n"))

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(plot_gaze.RecordingError, "tracked"):
            plot_gaze.load_recording(self.write("t_s,left_dir_x\n0,0.1\n"))

    def test_malformed_value_is_rejected(self):
        bad = TRACKED.format(t=0, h=100).replace("0.01", "abc")
        with self.assertRaisesRegex(plot_gaze.RecordingError, "line 2"):
            plot_gaze.load_recording(self.write(HEADER + "\n" + bad + "\n"))

    def test_main_returns_error_for_missing_file(self):
        self.assertEqual(plot_gaze.main(["/nonexistent/session.csv"]), 1)


if __name__ == "__main__":
    unittest.main()
