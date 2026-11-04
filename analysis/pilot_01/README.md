# Pilot 01 analysis (2026-11-04)

[`report.md`](report.md) is a **snapshot** of how `scripts/detect_okn.py`
behaved, with its default parameters and its documented sign convention as of
2026-11-04. If the detector is changed later, the numbers here must not be
replaced with the new detector's output. Run a new analysis instead.

| File | What it is |
|---|---|
| `run_pilot.py` | Regenerates everything below. Reuses `plot_gaze.py` / `detect_okn.py` unchanged |
| `report.md` | The written analysis and its limitations |
| `manifest.csv` | 21 recordings in time order, the planned vs recorded condition, and whether each matched |
| `metrics_per_trial.csv`, `condition_summary.csv`, `batch1_results.json` | Per-trial and per-condition metrics |
| `figures/*.png` | The 7 summary figures linked from the report |

**Not committed** (git-ignored, regenerated locally):
- `figures/trials/`: 42 per-trial plots;
- `detector_output/`: the full text report from each detector run.

The report links to both. The **raw recordings**
(`trials/NS_20261104-*/`) are also kept out of this public repository, and are
backed up privately with SHA-256 checksums.

To reproduce, with the 21 raw recording folders in `trials/`:

The committed manifest defines the frozen cohort. Extra recordings are ignored;
missing CSV or JSON files stop the run before any published output is changed.

```bash
python3 -m pip install -r scripts/requirements.txt
python3 analysis/pilot_01/run_pilot.py
```
