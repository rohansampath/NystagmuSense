"""Experimental raw-angle segmentation + segment-local SG OKN detector.

The baseline lives in detect_okn.py and remains the default. This module uses
dynamic programming to select a penalised piecewise-linear polyline whose
knots are observed samples. Unlike a whole-run SG derivative, its short steep
segments can retain a reset spanning only one or two camera intervals.

Objective: sum of squared raw-angle residuals + penalty per added segment,
where penalty = penalty_scale * noise_sigma**2 * log(n). Lines interpolate
their endpoint samples; shared endpoints have zero residual. This is an exact
optimum for this constrained polyline model, NOT an implementation of CPOP
(which optimises free knot heights). O(n²) time, O(n) working memory per valid
run. No resampling, stimulus-based inference, or new dependencies.
"""

import math
from dataclasses import dataclass, fields

import numpy as np

import detect_okn as baseline


@dataclass
class HybridParams:
    penalty_scale: float = 6.0
    noise_floor_deg: float = 0.05
    min_reset_amplitude_deg: float = 0.5
    max_reset_s: float = 0.15


def validate_params(p):
    for f in fields(p):
        value = getattr(p, f.name)
        if not math.isfinite(value) or value <= 0:
            raise baseline.SessionError(f"hybrid {f.name} must be finite and positive")


def noise_sigma(t, angle, floor):
    """Robust measurement-noise scale from local linear interpolation errors.

    Normalise each three-point error by its noise gain for actual timestamps.
    MAD rejects occasional resets; the floor limits oversegmentation when the
    signal is noiseless or serially correlated. This is a heuristic noise model.
    """
    if len(t) < 3:
        return floor
    w = (t[1:-1] - t[:-2]) / (t[2:] - t[:-2])
    error = (angle[1:-1] - (1 - w) * angle[:-2] - w * angle[2:])
    error /= np.sqrt(1 + (1 - w)**2 + w**2)
    sigma = np.median(np.abs(error - np.median(error))) / 0.6744897501960817
    return max(floor, float(sigma))


def segment_linear(t, angle, p):
    """Return inclusive endpoint-index pairs and the estimated noise scale.

    Fit all possible segments with prefix sums; dynamic programming chooses
    the global minimum of the documented objective. A two-sample segment is
    allowed so a one-frame reset is representable. Run boundaries are supplied
    by the caller; this function never crosses a blink or missing-frame gap.
    """
    n = len(t)
    sigma = noise_sigma(t, angle, p.noise_floor_deg)
    if n < 2:
        return [], sigma
    # Translation improves numerical conditioning at large uptime/angle offsets.
    x, y = t - t[0], angle - angle[0]
    prefixes = [np.r_[0.0, np.cumsum(v)] for v in (x, y, x*x, x*y, y*y)]
    penalty = p.penalty_scale * sigma**2 * math.log(n)
    best = np.full(n, np.inf)
    previous = np.full(n, -1, dtype=int)
    best[0] = -penalty  # no penalty for the first segment
    for end in range(1, n):
        starts = np.arange(end)
        slope = (y[end] - y[starts]) / (x[end] - x[starts])
        intercept = y[starts] - slope * x[starts]
        sx, sy, sxx, sxy, syy = [v[end + 1] - v[starts] for v in prefixes]
        count = end - starts + 1
        residual = (syy - 2*slope*sxy - 2*intercept*sy
                    + slope*slope*sxx + 2*slope*intercept*sx + count*intercept*intercept)
        cost = best[starts] + np.maximum(0, residual) + penalty
        start = int(np.argmin(cost))
        best[end], previous[end] = cost[start], start
    segments, end = [], n - 1
    while end > 0:
        start = int(previous[end])
        segments.append((start, end))
        end = start
    return list(reversed(segments)), sigma


def reset_phases(t, angle, segments, p, hp):
    """Short steep polyline segments, with the SAME speed gate as the baseline.

    Merge adjacent same-direction steep segments before applying duration and
    amplitude gates. The recorded peak_velocity is the steepest fitted segment
    slope, not a measured physiological peak. No SG value selects a reset.
    """
    candidates = []
    for a, b in segments:
        slope = float((angle[b] - angle[a]) / (t[b] - t[a]))
        if abs(slope) <= p.fast_threshold:
            continue
        direction = int(np.sign(slope))
        if candidates and candidates[-1][1] == a and candidates[-1][2] == direction:
            old_a, _, _, peak = candidates[-1]
            candidates[-1] = (old_a, b, direction, max((peak, slope), key=abs))
        else:
            candidates.append((a, b, direction, slope))
    fast = []
    for a, b, direction, peak in candidates:
        amplitude = float(angle[b] - angle[a])
        if t[b] - t[a] > hp.max_reset_s or abs(amplitude) < hp.min_reset_amplitude_deg:
            continue
        fast.append(dict(start=float(t[a]), end=float(t[b]), i0=a, i1=b + 1,
                         direction=direction, peak_velocity=peak, amplitude=amplitude))
    return fast


def analyse(data, p, hp=None):
    hp = hp or HybridParams()
    baseline.validate_params(p)
    validate_params(hp)
    t = data["t_s"]
    if len(t) < 2 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise baseline.SessionError("need at least 2 finite, strictly increasing timestamps")
    dt = float(np.median(np.diff(t)))
    angle = baseline.eye_angle(data)
    valid = baseline.valid_mask(t, angle, data, p)
    velocity = np.full_like(angle, np.nan)
    fast, slow, beats, windows, intervals, diagnostics = [], [], [], [], [], []
    for a, b in baseline.continuous_runs(t, valid, dt):
        ts, angles = t[a:b], angle[a:b]
        segments, sigma = segment_linear(ts, angles, hp)
        fs = reset_phases(ts, angles, segments, p, hp)
        slow_mask = np.ones(b - a, dtype=bool)
        for f in fs:
            slow_mask[f["i0"]:f["i1"]] = False
        # SG fits never see a sample belonging to an identified reset. Short
        # inter-reset runs lack enough samples for SG and cannot form beats.
        vel = baseline.sg_velocity(angles, slow_mask, dt, p, t=ts)
        ss = baseline.detect_slow_phases(ts, angles, slow_mask, fs, p, velocity=vel)
        bs = baseline.detect_beats(ss, fs, p)
        ws = baseline.okn_windows(ts, bs, p)
        intervals.extend(baseline.merge_windows(ws, bs))
        for left, right in segments:
            slope = float((angles[right] - angles[left]) / (ts[right] - ts[left]))
            diagnostics.append(dict(i0=a + left, i1=a + right + 1,
                                    start=float(ts[left]), end=float(ts[right]),
                                    velocity=slope, noise_sigma_deg=sigma))
        for f in fs:
            # Display the actual frame-to-frame slopes inside each reset,
            # separated from SG slow velocity. These are noise-sensitive.
            left, right = f["i0"], f["i1"]
            raw_velocity = np.diff(angles[left:right]) / np.diff(ts[left:right])
            vel[left:right] = np.r_[raw_velocity, raw_velocity[-1]]
            f["i0"] += a
            f["i1"] += a
        velocity[a:b] = vel
        fast.extend(fs)
        slow.extend(ss)
        beats.extend(bs)
        windows.extend(ws)
    return dict(t=t, dt=dt, angle=angle, valid=valid, velocity=velocity, fast=fast,
                slow=slow, beats=beats, windows=windows, intervals=intervals,
                stimulus=baseline.stimulus_direction(data), background=data.get("stim_bg_gray"),
                method="hybrid", segments=diagnostics)
