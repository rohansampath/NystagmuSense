"""Experimental OKN reset detectors: direction check and local piecewise-linear fits.

The baseline detector in detect_okn.py is unchanged and stays the default.
Every function here takes its output (or the same raw signal) and returns
reset start times, so all variants are scored by evaluate_okn.py's rules.

Direction check
    An OKN reset runs against the stripes. In detect_okn's eye_angle the reset
    sign equals stimulus_direction() (the sign of d stim_displacement_pt / dt).
    This was measured without labels on every Pilot 03 OKN recording and on
    the earlier DIR/DEV direction recordings: the slow drift between resets
    has the opposite sign in all 20 with tracking. eye_angle is perfectly
    anti-correlated with ARKit lookAtPoint.x (documented +x = subject's left),
    so a rightward on-screen stimulus drives the eye toward eye_angle < 0. Which
    documented convention is mirrored is unresolved; the relation used here
    is the measured one. Still stripes (direction 0) have no expected reset
    direction, so every fast phase is kept.

Local piecewise-linear step
    Around a candidate transition, fit one line to the samples before it and
    one to the samples after it, each within window_s, never across a tracking
    gap or blink. Each side must be roughly linear (residual RMS at most
    max_side_rms × |step|), so a window that contains another reset is not
    mistaken for a slow phase. The step is the jump between the two lines at the middle of
    the transition. The fit improvement 1 - SSE(two lines) / SSE(one line over
    the same samples, with transition samples scored against a straight
    connector) is near 1 for a real offset and near 0 for a spike that
    returns to the same level or for noise. Amplitude survives SG smoothing,
    which spreads a 1-2 frame reset's velocity peak.

A piecewise-linear step does not prove OKN: fixation saccades are steps too.
Only the direction check ties an event to the stimulus.
"""

from dataclasses import dataclass

import numpy as np

import detect_okn

RESET_SIGN_PER_STIMULUS = 1   # reset sign in eye_angle = this × stimulus_direction()


def expected_reset_direction(stimulus):
    """+1/−1 for moving stripes, 0 when there is no stimulus direction."""
    return RESET_SIGN_PER_STIMULUS * int(np.sign(stimulus))


def direction_filter(fast, expected):
    """Fast phases that run against the stripes; all of them when expected is 0."""
    return list(fast) if expected == 0 else [f for f in fast if f["direction"] == expected]


@dataclass
class StepParams:
    window_s: float = 0.15            # data used for each line, on each side
    min_points: int = 3               # per side; ~50 ms at 60 Hz
    max_transition_s: float = 0.10    # standalone scan: longest reset considered
    min_amplitude_deg: float = 0.5    # |step| between the two lines
    min_improvement: float = 0.5      # 1 - SSE(two lines) / SSE(one line)
    max_side_rms: float = 0.35        # each side's residual RMS, as a fraction of |step|
    min_mean_speed: float = 10        # deg/s over the transition (standalone only)
    min_separation_s: float = 0.15    # standalone: keep the best step within this


class _Lines:
    """Least-squares lines over index ranges from prefix sums (one valid run)."""

    def __init__(self, t, y):
        self.t0 = float(t[0])
        x = t - self.t0
        z = lambda v: np.concatenate([[0.0], np.cumsum(v)])
        self.c = [z(np.ones_like(x)), z(x), z(x * x), z(y), z(x * y), z(y * y)]

    def sums(self, a, b):
        """Sums over [a, b)."""
        return np.array([c[b] - c[a] for c in self.c])

    @staticmethod
    def fit(s):
        """(slope, intercept, sse) for summed moments; flat line when n < 2 or x is constant."""
        n, sx, sxx, sy, sxy, syy = s
        var = n * sxx - sx * sx
        if n < 2 or var <= 1e-12:
            mean = sy / n
            return 0.0, mean, max(syy - n * mean * mean, 0.0)
        slope = (n * sxy - sx * sy) / var
        intercept = (sy - slope * sx) / n
        sse = syy - 2 * slope * sxy - 2 * intercept * sy + slope * slope * sxx + 2 * slope * intercept * sx \
            + n * intercept * intercept
        return slope, intercept, max(sse, 0.0)


def _step(lines, t, y, a, b, pre_end, post_start, p):
    """Two-line features for a transition between samples pre_end and post_start (same run [a, b))."""
    lo = int(np.searchsorted(t, t[pre_end] - p.window_s, side="left"))
    hi = int(np.searchsorted(t, t[post_start] + p.window_s, side="right"))
    lo, hi = max(lo, a), min(hi, b)
    n_pre, n_post = pre_end + 1 - lo, hi - post_start
    if n_pre < p.min_points or n_post < p.min_points:
        return None
    pre, post = lines.sums(lo, pre_end + 1), lines.sums(post_start, hi)
    s1, i1, e1 = lines.fit(pre)
    s2, i2, e2 = lines.fit(post)
    # Samples inside the transition are not free: they are scored against a
    # straight connector from the end of the first line to the start of the
    # second, so a longer transition than the data shows fits worse.
    x0, x1 = t[pre_end] - lines.t0, t[post_start] - lines.t0
    y0, y1 = s1 * x0 + i1, s2 * x1 + i2
    xm = t[pre_end + 1:post_start] - lines.t0
    e_mid = float(np.sum((y[pre_end + 1:post_start] - (y0 + (y1 - y0) * (xm - x0) / (x1 - x0)))**2))
    _, _, e_one = lines.fit(lines.sums(lo, hi))
    tc = (x0 + x1) / 2
    amplitude = (s2 * tc + i2) - (s1 * tc + i1)
    improvement = 1 - (e1 + e2 + e_mid) / e_one if e_one > 1e-12 else 0.0
    side_rms = max(np.sqrt(e1 / n_pre), np.sqrt(e2 / n_post))
    return dict(amplitude=float(amplitude), improvement=float(improvement), side_rms=float(side_rms), pre_slope=float(s1),
                post_slope=float(s2), duration=float(t[post_start] - t[pre_end]),
                direction=int(np.sign(amplitude)), n_pre=n_pre, n_post=n_post)


def _runs(r):
    return list(detect_okn.continuous_runs(r["t"], r["valid"], r["dt"]))


def step_features(r, fast, p=None):
    """Local two-line features for each SG fast phase (best transition in its span), or None at a run edge."""
    p = p or StepParams()
    t, angle = r["t"], r["angle"]
    runs = _runs(r)
    out = []
    for f in fast:
        run = next(((a, b) for a, b in runs if a <= f["i0"] and f["i1"] <= b), None)
        if run is None or f["i0"] - 1 < run[0] or f["i1"] >= run[1]:
            out.append(None)
            continue
        a, b = run
        lines, lo, hi = _Lines(t[a:b], angle[a:b]), f["i0"] - 1 - a, f["i1"] - a
        # SG spreads a reset over neighbouring samples: use the best transition inside the span.
        steps = [_step(lines, t[a:b], angle[a:b], 0, b - a, i, j, p)
                 for i in range(lo, hi) for j in range(i + 1, hi + 1)]
        steps = [s for s in steps if s]
        out.append(max(steps, key=lambda s: s["improvement"]) if steps else None)
    return out


def plausible(s, p):
    """Step gates shared by validation and the standalone scan."""
    return bool(s) and abs(s["amplitude"]) >= p.min_amplitude_deg and s["improvement"] >= p.min_improvement \
        and s["side_rms"] <= p.max_side_rms * abs(s["amplitude"])


def linear_validate(r, fast, p=None):
    """SG fast phases whose surroundings show a real step in the same direction."""
    p = p or StepParams()
    keep = []
    for f, s in zip(fast, step_features(r, fast, p)):
        if plausible(s, p) and s["direction"] == f["direction"]:
            keep.append(f)
    return keep


def piecewise_resets(r, p=None, expected=0):
    """Standalone scan: steps between local line fits, no SG velocity gate.

    For every sample k and every transition k → k+L lasting at most
    max_transition_s, fit the two lines and keep the best L for k. A candidate
    needs the amplitude, fit-improvement, side-linearity and mean-speed gates and, for moving
    stripes, the expected direction. Overlapping candidates are thinned to the
    largest |amplitude| × improvement within min_separation_s.
    """
    p = p or StepParams()
    t, angle = r["t"], r["angle"]
    found = []
    for a, b in _runs(r):
        if b - a < 2 * p.min_points:
            continue
        ts, ys, lines = t[a:b], angle[a:b], _Lines(t[a:b], angle[a:b])
        for k in range(p.min_points - 1, b - a - p.min_points):
            best = None
            for post in range(k + 1, b - a):
                if ts[post] - ts[k] > p.max_transition_s:
                    break
                s = _step(lines, ts, ys, 0, b - a, k, post, p)
                if s and (best is None or s["improvement"] > best["improvement"]):
                    best = s
            if not plausible(best, p) or abs(best["amplitude"]) / best["duration"] < p.min_mean_speed:
                continue
            if expected and best["direction"] != expected:
                continue
            found.append(dict(best, start=float(ts[k]), score=abs(best["amplitude"]) * best["improvement"]))
    kept = []
    for c in sorted(found, key=lambda c: -c["score"]):
        if all(abs(c["start"] - k["start"]) >= p.min_separation_s for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["start"])
