# Trials

Real device recordings exported from the app, one folder per trial, each with the
CSV and its plot (`python3 scripts/plot_gaze.py <csv>`). CSV format: see the main README.

| Trial | Date | Notes |
|---|---|---|
| `trackingtest1` | 2026-10-24 | First on-device run. iPhone 16 Pro (`iPhone17,1`), iOS 26.6.2, session `3DA64179`. 599 samples, 60 Hz, 100 % tracked, no gaps (3 frames outside the 10 s window dropped as expected). Blink at ~0.9–1.05 s (blink 0.81, lookAt y dips to −0.22 m). No clear OKN sawtooth. |
