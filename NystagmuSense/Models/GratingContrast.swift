//
//  GratingContrast.swift
//  NystagmuSense
//
//  Nominal-contrast gratings for Pilot 05. The contrast is defined on
//  luminance, then mapped to display code values with the sRGB transfer
//  function. That mapping is an assumption about the display, not a
//  measurement: every contrast here is NOMINAL until checked with a photometer.
//

import Foundation

/// Pilot 05 contrast levels: nominal Michelson contrast in whole percent.
enum NominalContrast: Int, CaseIterable, Identifiable, Codable {
    case c0 = 0, c5 = 5, c10 = 10, c20 = 20, c40 = 40, c80 = 80

    var id: Int { rawValue }
    /// Michelson contrast as a fraction, 0…1.
    var fraction: Double { Double(rawValue) / 100 }
    /// Recording-name field: `C` + whole percent, zero-padded to 3 digits (C000 … C080).
    var nameCode: String { Self.nameCode(percent: rawValue) }
    var label: String { "\(rawValue) %" }

    static func nameCode(percent: Int) -> String {
        let digits = String(percent)
        return "C" + String(repeating: "0", count: max(0, 3 - digits.count)) + digits
    }
}

/// Luminance model for a square-wave grating of dark bars on a lighter background.
///
/// Michelson contrast C = (Lmax − Lmin) / (Lmax + Lmin), with L relative
/// luminance (0 = black, 1 = display white). The bars cover a fraction d of
/// each period (1 / pitchToWidthRatio), so a plain midpoint grating would get
/// brighter as contrast rises. Instead the area-weighted mean
/// d·Lbar + (1 − d)·Lbackground is held at `mean` for every contrast:
///
///     x = 2C / (1 + (1 − 2d)·C)
///     Lbackground = mean · (1 + d·x),  Lbar = mean · (1 − (1 − d)·x)
///
/// At C = 0 both equal `mean`, a uniform field. Code values come from the
/// inverse sRGB transfer function (IEC 61966-2-1), assuming the display
/// reproduces sRGB-encoded greys with that curve (True Tone and Night Shift
/// off). That assumption is not verified.
enum GratingLuminance {
    /// Mean relative luminance held constant across Pilot 05 contrasts. 0.5
    /// leaves headroom: at 80 % the background needs 0.79 of display white.
    static let meanRelativeLuminance = 0.5

    static func luminances(contrast c: Double, mean: Double = meanRelativeLuminance,
                           barFraction d: Double) -> (background: Double, bar: Double) {
        let x = 2 * c / (1 + (1 - 2 * d) * c)
        return (mean * (1 + d * x), mean * (1 - (1 - d) * x))
    }

    /// Relative luminance → sRGB-encoded code value, both 0…1.
    static func srgbEncode(_ l: Double) -> Double {
        let l = min(max(l, 0), 1)
        return l <= 0.0031308 ? 12.92 * l : 1.055 * pow(l, 1 / 2.4) - 0.055
    }

    /// sRGB-encoded code value → relative luminance (the assumed display curve).
    static func srgbDecode(_ v: Double) -> Double {
        let v = min(max(v, 0), 1)
        return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
    }

    /// `Color(white:)` code values (sRGB) for background and bars.
    static func codeValues(contrast c: Double, mean: Double = meanRelativeLuminance,
                           barFraction d: Double) -> (background: Double, bar: Double) {
        let l = luminances(contrast: c, mean: mean, barFraction: d)
        return (srgbEncode(l.background), srgbEncode(l.bar))
    }
}

extension StimulusConfig {
    /// Fraction of each stripe period covered by a bar.
    var barFraction: Double { 1 / pitchToWidthRatio }

    /// Pilot 05: moving OKN grating at a nominal contrast, constant mean
    /// luminance. Speed, direction, stripe geometry and timing are unchanged;
    /// at 0 % the stripes still move (and are logged) but are invisible.
    mutating func applyNominalContrast(_ contrast: NominalContrast) {
        let codes = GratingLuminance.codeValues(contrast: contrast.fraction, barFraction: barFraction)
        michelsonContrast = contrast.fraction
        meanRelativeLuminance = GratingLuminance.meanRelativeLuminance
        fixedBackgroundGray = codes.background
        stripeGray = codes.bar
    }
}
