"""Trial-level OKN response metrics from one recording (exploratory research code).

Everything is built on the FROZEN detector (detect_okn.analyse with SG
window 5, order 2, threshold 22 deg/s; direction check as in
evaluate_okn's sg-direction). Nothing here changes it.

Sign convention (measured label-free on Pilot 03, re-checked by
analyze_response.py): in detect_okn's eye angle, OKN resets have the sign of
the stimulus (okn_variants.expected_reset_direction) and the slow phase the
opposite sign. "Aligned" values multiply by that expected slow-phase sign, so
positive means "eye drifting with the stripes".

Metrics per recording:
  A. Fast-phase rate: frozen-detector fast phases per 10 s of VALID time;
     direction-consistent ones (against the stripes) for moving stimuli.
  B. Slow-phase velocity: the frozen detector's SG velocity on slow-phase
     samples = valid samples inside continuous runs, |v| <= threshold, and
     more than `margin_s` from any detected fast phase (either direction).
     Mean, median and mean |v|, SD (within-trial variability), the share of
     samples that are slow-phase, and the stimulus-aligned median.
  C. Direction consistency: share of slow-phase samples whose velocity has
     the expected slow-phase sign (0.5 = chance), and the share of detected
     fast phases that oppose the stimulus (reset consistency).
Still stripes have no stimulus direction. The direction metrics are computed
for both hypothetical directions and the larger value is reported
("best-case direction"), so a still control is never helped by a direction
chosen for it. That is conservative for specificity. The direction-free
statistics (|median v|, all-fast rate) are reported as well.

Apparent gain = aligned median slow-phase velocity / stimulus angular velocity,
the latter from speedPointsPerSecond, the device's point size (known models
only) and the ARKit median face distance. Both the eye angle and the distance
are uncalibrated, so this is an apparent gain, not a physiological one. None
for unknown devices or missing distance.

Any metric that needs slow-phase samples is None (unavailable, never 0) when
fewer than `min_slow_s` seconds of slow-phase samples remain.
"""

import math

import numpy as np

import detect_okn
import okn_variants

FROZEN = detect_okn.Params(fast_threshold=22)          # window 5, order 2: the frozen detector
MARGIN_S = 0.05
MIN_SLOW_S = 1.0
# millimetres per UIKit point: 25.4 / (ppi / scale). Only devices we've verified.
MM_PER_POINT = {"iPhone17,1": 25.4 / (460 / 3)}       # iPhone 16 Pro, 874 × 402 pt landscape


def stimulus_deg_per_s(speed_pt_s, device_model, distance_cm):
    """Stripe angular speed at the screen centre, or None when it can't be derived."""
    mm = MM_PER_POINT.get(device_model)
    if mm is None or not distance_cm or not math.isfinite(distance_cm) or distance_cm <= 0 or speed_pt_s is None:
        return None
    return math.degrees(speed_pt_s * mm / (10 * distance_cm))


def _fraction(values):
    return float(np.mean(values)) if len(values) else None


def slow_mask(r, margin_s=MARGIN_S, threshold=None):
    """Slow-phase candidate samples: valid, finite velocity, under threshold, away from any fast phase."""
    t, vel = r["t"], r["velocity"]
    threshold = FROZEN.fast_threshold if threshold is None else threshold
    with np.errstate(invalid="ignore"):
        mask = r["valid"] & np.isfinite(vel) & (np.abs(vel) <= threshold)
    for f in r["fast"]:
        mask &= ~((t >= f["start"] - margin_s) & (t <= f["end"] + margin_s))
    return mask


def direction_scores(vel_slow, fast, slow_sign):
    """Slow-phase and reset direction consistency for one expected slow-phase sign (+1/-1)."""
    return dict(slow_consistency=_fraction(slow_sign * vel_slow > 0) if len(vel_slow) else None,
                reset_consistency=_fraction([f["direction"] == -slow_sign for f in fast]) if fast else None,
                aligned_median=float(slow_sign * np.median(vel_slow)) if len(vel_slow) else None,
                aligned_fast=sum(f["direction"] == -slow_sign for f in fast))


def trial_metrics(data, speed_pt_s=None, device_model=None, distance_cm=None, exclusion_params=None,
                  margin_s=MARGIN_S, min_slow_s=MIN_SLOW_S):
    """Metrics for one session dict (detect_okn.load_session). exclusion_params changes ONLY
    which fast phases are removed from the slow-phase samples (robustness checks)."""
    r = detect_okn.analyse(data, FROZEN)
    t, vel, valid = r["t"], r["velocity"], r["valid"]
    dt = r["dt"]
    valid_s = float(np.sum(valid)) * dt
    stim = detect_okn.stimulus_direction(data)
    expected_reset = okn_variants.expected_reset_direction(stim)
    fast = r["fast"]
    excl = detect_okn.analyse(data, exclusion_params)["fast"] if exclusion_params else fast
    mask = slow_mask(dict(r, fast=excl), margin_s)
    v = vel[mask]
    enough = len(v) * dt >= min_slow_s
    per10 = lambda n: 10 * n / valid_s if valid_s > 0 else None
    out = dict(valid_fraction=float(np.mean(valid)), valid_s=valid_s, stimulus_direction=stim,
               n_fast=len(fast), fast_rate_all=per10(len(fast)),
               slow_fraction=float(np.mean(mask)), slow_s=len(v) * dt, slow_available=enough)
    if enough:
        out.update(slow_mean=float(np.mean(v)), slow_median=float(np.median(v)),
                   slow_mean_abs=float(np.mean(np.abs(v))), slow_sd=float(np.std(v)),
                   slow_abs_median=float(abs(np.median(v))))
    else:
        out.update(slow_mean=None, slow_median=None, slow_mean_abs=None, slow_sd=None, slow_abs_median=None)
    vs = v if enough else np.array([])
    if expected_reset:
        d = direction_scores(vs, fast, -expected_reset)
        out.update(direction_basis="stimulus", n_fast_consistent=d["aligned_fast"],
                   fast_rate_consistent=per10(d["aligned_fast"]), slow_consistency=d["slow_consistency"],
                   reset_consistency=d["reset_consistency"], aligned_slow_median=d["aligned_median"])
    else:
        # No stimulus direction: evaluate both hypothetical directions, report the larger (best case).
        cand = [direction_scores(vs, fast, s) for s in (1, -1)]
        best = lambda k: max((c[k] for c in cand if c[k] is not None), default=None)
        n = max(c["aligned_fast"] for c in cand)
        out.update(direction_basis="best-case hypothetical (still stripes)", n_fast_consistent=n,
                   fast_rate_consistent=per10(n), slow_consistency=best("slow_consistency"),
                   reset_consistency=best("reset_consistency"), aligned_slow_median=best("aligned_median"))
    stim_deg = stimulus_deg_per_s(speed_pt_s, device_model, distance_cm) if speed_pt_s else None
    out.update(stimulus_deg_s=stim_deg,
               apparent_gain=(out["aligned_slow_median"] / stim_deg
                              if stim_deg and expected_reset and out["aligned_slow_median"] is not None else None))
    return out
