# Trials

Real device recordings exported from the app, one folder per trial, each with the
CSV and its plot (`python3 scripts/plot_gaze.py <csv>`). CSV format: see the main README.

| Trial | Date | Notes |
|---|---|---|
| `trackingtest1` | 2026-10-24 | First on-device run. iPhone 16 Pro (`iPhone17,1`), iOS 26.6.2, session `3DA64179`. 599 samples, 60 Hz, 100 % tracked, no gaps (3 frames outside the 10 s window dropped as expected). Blink at ~0.9–1.05 s (blink 0.81, lookAt y dips to −0.22 m). No clear OKN sawtooth. |
| `trackingtest2` | 2026-11-01 | iPhone 16 Pro (`iPhone17,1`), iOS 26.6.2, session `F9B940E8`. 597 samples, 60 Hz, 592 tracked (99.2 %; first ~0.08 s untracked), no gaps. Rightward stimulus, 90 pt/s. Gaze steps between flat plateaus (~±0.15 m lookAt x) about every 0.5–1 s, with vertical moving alongside; looks like deliberate left/right fixations, not an OKN sawtooth. |
| `trackingtest3` | 2026-11-01 | First schema-v2 run (white bars on constant black, landscape 874×402 pt, rightward 90 pt/s). iPhone 16 Pro (`iPhone17,1`), iOS 26.6.2, session `E79BC426`. 599 samples, 60 Hz, 100 % tracked, no gaps, no issues. `detect_okn.py`: 94 % valid after blink masking, 7 fast phases (5 right / 2 left), 4 beats, one candidate OKN 2.88–5.68 s with slow phases **opposite** to the stimulus (median −2.6 deg/s). The plot shows a sawtooth (slow leftward drift, quick rightward reset) from ~2.8–7 s: either not OKN, or the unverified eye-angle sign is inverted, in which case it follows the stimulus. Needs a sign-calibration trial (look left, then right). Plots: `trackingtest3.png`, `trackingtest3_okn.png`. |
