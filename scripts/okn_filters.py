"""Experimental velocity estimators for OKN fast-phase detection (offline only).

detect_okn.py is unchanged; its SG detector stays the default. These functions
swap ONLY the eye-velocity estimate and reuse every downstream step:

  sg     detect_okn.sg_velocity on the raw angle (5 samples, order 2)
  bw     Butterworth low-pass (order 2, zero-phase sosfiltfilt) on the angle,
         then np.gradient against the measured timestamps
  bw+sg  the same Butterworth low-pass, then detect_okn.sg_velocity

fast_phases() then runs detect_okn.detect_fast_phases on each continuous valid
run exactly as detect_okn.analyse does, and okn_variants.direction_filter keeps
resets against the stripes (still stripes keep everything).

Segments and gaps: every estimator works on detect_okn.continuous_runs, so no
filter or derivative crosses a blink, tracking loss or missing frame. A run
shorter than sg_window samples gets no velocity (as for SG). The Butterworth
filter needs a fixed rate: each run's rate is measured from its timestamps
and a run whose intervals deviate from their median by more than 1 % is
refused (ValueError) rather than filtered as if uniform. Pilot 03 runs are
60.01 Hz with < 0.01 % deviation.

Boundaries: sosfiltfilt pads each run by odd reflection (padlen up to
3 × (2 × sections + 1) samples, shortened to fit short runs), which keeps a
linear trend through the ends instead of pulling it toward zero.

Frequency behaviour differs: SG 5/2 is itself a low-pass differentiator, while
np.gradient is a central difference (gain sin(ωT)/(ωT) of an ideal
derivative). Forward-backward filtering needs future samples, so none of this
is a real-time (on-device) implementation.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt

import detect_okn
import okn_variants

METHODS = ("sg", "bw", "bw+sg")
BW_ORDER = 2
MAX_INTERVAL_DEVIATION = 0.01


def run_rate(t):
    """Sampling rate (Hz) of one run; ValueError if its intervals aren't uniform."""
    intervals = np.diff(t)
    median = float(np.median(intervals))
    if np.max(np.abs(intervals - median)) > MAX_INTERVAL_DEVIATION * median:
        raise ValueError("irregular sampling within a run; a fixed-rate Butterworth filter would be invalid")
    return 1 / median


def butter_lowpass(x, fs, cutoff, order=BW_ORDER):
    """Zero-phase Butterworth low-pass of one uniformly sampled run."""
    if not 0 < cutoff < fs / 2:
        raise ValueError(f"cutoff {cutoff} Hz must be between 0 and Nyquist ({fs / 2:.1f} Hz)")
    sos = butter(order, cutoff, btype="low", fs=fs, output="sos")
    padlen = min(3 * (2 * len(sos) + 1), len(x) - 1)
    return sosfiltfilt(sos, x, padtype="odd", padlen=padlen)


def smoothed_angle(t, angle, valid, dt, cutoff, min_samples=5):
    """Butterworth-filtered angle per continuous run; NaN outside runs long enough to filter."""
    out = np.full_like(angle, np.nan)
    for a, b in detect_okn.continuous_runs(t, valid, dt):
        if b - a >= min_samples:
            out[a:b] = butter_lowpass(angle[a:b], run_rate(t[a:b]), cutoff)
    return out


def velocity(t, angle, valid, dt, method, cutoff=None, p=None):
    """deg/s; NaN outside continuous runs of at least sg_window samples."""
    p = p or detect_okn.Params()
    if method == "sg":
        return detect_okn.sg_velocity(angle, valid, dt, p, t=t)
    smooth = smoothed_angle(t, angle, valid, dt, cutoff, min_samples=p.sg_window)
    ok = valid & np.isfinite(smooth)
    if method == "bw+sg":
        return detect_okn.sg_velocity(smooth, ok, dt, p, t=t)
    if method != "bw":
        raise ValueError(f"unknown method {method!r}")
    vel = np.full_like(angle, np.nan)
    for a, b in detect_okn.continuous_runs(t, ok, dt):
        if b - a >= 2:
            vel[a:b] = np.gradient(smooth[a:b], t[a:b])
    return vel


def signal(data, p=None):
    """t, angle, valid mask and median interval, exactly as detect_okn.analyse derives them."""
    p = p or detect_okn.Params()
    t = data["t_s"]
    angle = detect_okn.eye_angle(data)
    return t, angle, detect_okn.valid_mask(t, angle, data, p), float(np.median(np.diff(t)))


def fast_phases(data, method, threshold, cutoff=None):
    """detect_okn's fast phases with the chosen velocity estimator (no direction check)."""
    t, angle, valid, dt = signal(data)
    return fast_phases_from(t, angle, valid, dt, velocity(t, angle, valid, dt, method, cutoff), threshold)


def fast_phases_from(t, angle, valid, dt, vel, threshold):
    """detect_okn.detect_fast_phases per continuous run, as in detect_okn.analyse, for a given velocity."""
    p = detect_okn.Params(fast_threshold=threshold)
    out = []
    for a, b in detect_okn.continuous_runs(t, valid, dt):
        if b - a < p.sg_window:
            continue
        for f in detect_okn.detect_fast_phases(t[a:b], angle[a:b], vel[a:b], np.isfinite(vel[a:b]), p):
            f["i0"] += a
            f["i1"] += a
            out.append(f)
    return out


def predict(data, method, threshold, cutoff=None):
    """Reset start times: fast phases against the stripes (all of them for still stripes)."""
    return reset_starts(data, fast_phases(data, method, threshold, cutoff))


def reset_starts(data, fast):
    expected = okn_variants.expected_reset_direction(detect_okn.stimulus_direction(data))
    return [f["start"] for f in okn_variants.direction_filter(fast, expected)]
