"""Pilot 05 nominal-contrast grating model (Python mirror of GratingContrast.swift).

    python3 analysis/pilot_05/contrast_model.py            # print the table
    python3 analysis/pilot_05/contrast_model.py --write    # refresh scripts/tests/fixtures/contrast_codes.json

Michelson contrast C = (Lmax - Lmin) / (Lmax + Lmin) on RELATIVE luminance
(0 = black, 1 = display white). Bars cover a fraction d = 1 / pitchToWidthRatio
of each period; the area-weighted mean d*Lbar + (1 - d)*Lbackground is held at
MEAN for every contrast:

    x = 2C / (1 + (1 - 2d) C);   Lbackground = MEAN (1 + d x);   Lbar = MEAN (1 - (1 - d) x)

Code values use the inverse sRGB transfer function (IEC 61966-2-1). That the
iPhone reproduces sRGB greys with exactly that curve is an ASSUMPTION; every
contrast is nominal until measured with a photometer. The table also shows the
contrast that survives rounding to 8-bit and 10-bit code values, under the
same assumed curve.
"""

import argparse
import json
from pathlib import Path

LEVELS = [0, 5, 10, 20, 40, 80]
MEAN = 0.5
PITCH_TO_WIDTH = 2.4
BAR_FRACTION = 1 / PITCH_TO_WIDTH
FIXTURE = Path(__file__).resolve().parents[2] / "scripts" / "tests" / "fixtures" / "contrast_codes.json"


def name_code(percent):
    return f"C{percent:03d}"


def luminances(c, mean=MEAN, d=BAR_FRACTION):
    x = 2 * c / (1 + (1 - 2 * d) * c)
    return mean * (1 + d * x), mean * (1 - (1 - d) * x)


def srgb_encode(lum):
    lum = min(max(lum, 0.0), 1.0)
    return 12.92 * lum if lum <= 0.0031308 else 1.055 * lum ** (1 / 2.4) - 0.055


def srgb_decode(v):
    v = min(max(v, 0.0), 1.0)
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def codes(c, mean=MEAN, d=BAR_FRACTION):
    bg, bar = luminances(c, mean, d)
    return srgb_encode(bg), srgb_encode(bar)


def michelson(l_bg, l_bar):
    return (max(l_bg, l_bar) - min(l_bg, l_bar)) / (l_bg + l_bar) if l_bg + l_bar else 0.0


def quantized(c, bits):
    """Contrast and mean after rounding both code values to `bits`, under the assumed curve."""
    top = 2 ** bits - 1
    bg, bar = (round(v * top) / top for v in codes(c))
    l_bg, l_bar = srgb_decode(bg), srgb_decode(bar)
    return michelson(l_bg, l_bar), BAR_FRACTION * l_bar + (1 - BAR_FRACTION) * l_bg, round(bg * top), round(bar * top)


def table():
    rows = []
    for p in LEVELS:
        c = p / 100
        l_bg, l_bar = luminances(c)
        c_bg, c_bar = codes(c)
        c8, m8, bg8, bar8 = quantized(c, 8)
        c10, m10, _, _ = quantized(c, 10)
        rows.append(dict(percent=p, code=name_code(p), contrast=c, luminance_background=l_bg, luminance_bar=l_bar,
                         code_background=c_bg, code_bar=c_bar, code8_background=bg8, code8_bar=bar8,
                         contrast_8bit=c8, mean_8bit=m8, contrast_10bit=c10, mean_10bit=m10))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    rows = table()
    print(f"bar fraction {BAR_FRACTION:.4f}, mean relative luminance {MEAN}")
    print(f"{'level':>5} {'L bg':>6} {'L bar':>6} {'code bg':>8} {'code bar':>8} {'8-bit':>9} {'C 8-bit':>8} {'C 10-bit':>8}")
    for r in rows:
        print(f"{r['code']:>5} {r['luminance_background']:6.4f} {r['luminance_bar']:6.4f} {r['code_background']:8.4f} "
              f"{r['code_bar']:8.4f} {r['code8_background']:4d}/{r['code8_bar']:<4d} {100 * r['contrast_8bit']:7.2f}% "
              f"{100 * r['contrast_10bit']:7.2f}%")
    if args.write:
        FIXTURE.write_text(json.dumps(dict(
            definition="Michelson contrast on relative luminance; constant area-weighted mean; inverse sRGB "
                       "transfer function (assumed display curve). Shared by GratingContrast.swift and "
                       "analysis/pilot_05/contrast_model.py.",
            mean_relative_luminance=MEAN, pitch_to_width_ratio=PITCH_TO_WIDTH,
            levels=[{k: r[k] for k in ("percent", "code", "contrast", "luminance_background", "luminance_bar",
                                       "code_background", "code_bar")} for r in rows]), indent=2) + "\n")
        print(f"wrote {FIXTURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
