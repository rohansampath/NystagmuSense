"""Contract/error checks using explicitly synthetic input, never device evidence."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from plot_gaze import read_recording


class RecordingTests(unittest.TestCase):
    def load(self, samples):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic.json'
            path.write_text(json.dumps({'schemaVersion': 1, 'units': 'meters', 'samples': samples}))
            return read_recording(path)

    def sample(self, timestamp, valid=True):
        return dict(timestamp=timestamp, x=0.1, y=0.2, z=1.0, valid=valid, faceTracked=valid)

    def test_actual_timestamps_and_invalid_frames(self):
        _, times, xs, _, invalid = self.load([
            self.sample(100), self.sample(100.03, False), self.sample(100.08)])
        self.assertAlmostEqual(times[-1], 0.08)
        self.assertEqual(invalid, 1)
        self.assertNotEqual(xs[1], xs[1])  # NaN breaks invalid data

    def test_empty_and_invalid_fail(self):
        for samples in ([], [self.sample(1, False)]):
            with self.assertRaisesRegex(ValueError, 'no gaze|No valid'):
                self.load(samples)

    def test_decreasing_or_bad_timestamp_fails(self):
        for samples in ([self.sample(2), self.sample(1)], [self.sample(float('nan'))]):
            with self.assertRaises(ValueError):
                self.load(samples)

    def test_empty_export_cli_reports_failure_without_png(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'empty.json'
            path.write_text(json.dumps({'schemaVersion': 1, 'units': 'meters', 'samples': []}))
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name('plot_gaze.py')), str(path)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Recording contains no gaze samples', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(path.with_suffix('.png').exists())

    def test_nonfinite_gaze_is_invalid(self):
        bad = self.sample(1)
        bad['x'] = float('inf')
        with self.assertRaisesRegex(ValueError, 'No valid'):
            self.load([bad])


if __name__ == '__main__':
    unittest.main()
