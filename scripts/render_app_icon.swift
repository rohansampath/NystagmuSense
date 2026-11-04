// Renders the NystagmuSense app icon (1024×1024, square, no rounded corners).
// Usage (from the repo root):
//   swift scripts/render_app_icon.swift NystagmuSense/Assets.xcassets/AppIcon.appiconset/AppIcon.png
//   swift scripts/render_app_icon.swift NystagmuSense/Assets.xcassets/AppIcon.appiconset/AppIcon-tinted.png tinted
// Eye + OKN sawtooth (slow drift, fast reset) on deep navy; default and dark
// appearances share AppIcon.png, the tinted appearance uses the grayscale render.
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
let out = URL(fileURLWithPath: args[1])
let tinted = args.count > 2 && args[2] == "tinted"
let S: CGFloat = 1024
let space = CGColorSpace(name: CGColorSpace.sRGB)!

func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    let r = CGFloat((hex >> 16) & 0xFF) / 255, g = CGFloat((hex >> 8) & 0xFF) / 255, b = CGFloat(hex & 0xFF) / 255
    if tinted {   // tinted variant: luminance only, iOS applies the tint
        let y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return CGColor(colorSpace: space, components: [y, y, y, a])!
    }
    return CGColor(colorSpace: space, components: [r, g, b, a])!
}

let ctx = CGContext(data: nil, width: Int(S), height: Int(S), bitsPerComponent: 8, bytesPerRow: 0,
                    space: space, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!   // opaque: app icons must not have alpha
// Work in top-left coordinates.
ctx.translateBy(x: 0, y: S)
ctx.scaleBy(x: 1, y: -1)
ctx.setShouldAntialias(true)
ctx.interpolationQuality = .high

let cyan: UInt32 = 0x2DE8F5, teal: UInt32 = 0x14C8B4, violet: UInt32 = 0x7A5CFF
let navyTop: UInt32 = 0x0A1328, navyBottom: UInt32 = 0x05070F

func linear(_ colors: [CGColor], _ from: CGPoint, _ to: CGPoint) {
    let g = CGGradient(colorsSpace: space, colors: colors as CFArray, locations: nil)!
    ctx.drawLinearGradient(g, start: from, end: to, options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
}

func radial(_ colors: [CGColor], _ c: CGPoint, _ r: CGFloat, locations: [CGFloat]? = nil) {
    let g = CGGradient(colorsSpace: space, colors: colors as CFArray, locations: locations)!
    ctx.drawRadialGradient(g, startCenter: c, startRadius: 0, endCenter: c, endRadius: r,
                           options: [.drawsAfterEndLocation])
}

/// Fills the stroke outline of `path` with a left→right cyan→violet gradient.
func gradientStroke(_ path: CGPath, width: CGFloat, cap: CGLineCap = .round, join: CGLineJoin = .round,
                    colors: [CGColor]? = nil) {
    ctx.saveGState()
    ctx.addPath(path.copy(strokingWithWidth: width, lineCap: cap, lineJoin: join, miterLimit: 10))
    ctx.clip()
    linear(colors ?? [rgb(cyan), rgb(teal), rgb(violet)], CGPoint(x: 140, y: 300), CGPoint(x: 900, y: 720))
    ctx.restoreGState()
}

// 1. Background: deep navy, a faint violet glow low right, a cyan glow behind the eye.
linear([rgb(navyTop), rgb(navyBottom)], CGPoint(x: 0, y: 0), CGPoint(x: S, y: S))
radial([rgb(violet, 0.22), rgb(violet, 0)], CGPoint(x: 860, y: 900), 620)
radial([rgb(cyan, 0.16), rgb(cyan, 0)], CGPoint(x: 512, y: 512), 470)

let c = CGPoint(x: 512, y: 512)

// 2. Eye outline (almond).
let eye = CGMutablePath()
eye.move(to: CGPoint(x: 118, y: 512))
eye.addCurve(to: CGPoint(x: 906, y: 512), control1: CGPoint(x: 300, y: 222), control2: CGPoint(x: 724, y: 222))
eye.addCurve(to: CGPoint(x: 118, y: 512), control1: CGPoint(x: 724, y: 802), control2: CGPoint(x: 300, y: 802))
eye.closeSubpath()

// 3. OKN trace through the eye: slow ramps and sharp resets across the full
//    width, fading out at the edges; the iris covers its middle.
let saw = CGMutablePath()
let amp: CGFloat = 50, period: CGFloat = 186, x0: CGFloat = 512 - 2.5 * 186
saw.move(to: CGPoint(x: x0, y: c.y + amp))
var x = x0
for _ in 0..<5 {
    saw.addLine(to: CGPoint(x: x + period * 0.84, y: c.y - amp))   // slow phase
    saw.addLine(to: CGPoint(x: x + period, y: c.y + amp))          // fast reset
    x += period
}
ctx.saveGState()
ctx.addPath(saw.copy(strokingWithWidth: 18, lineCap: .round, lineJoin: .miter, miterLimit: 10))
ctx.clip()
let fade = CGGradient(colorsSpace: space,
                      colors: [rgb(cyan, 0), rgb(cyan, 0.95), rgb(teal, 0.95), rgb(violet, 0.95), rgb(violet, 0)] as CFArray,
                      locations: [0.0, 0.22, 0.5, 0.78, 1.0])!
ctx.drawLinearGradient(fade, start: CGPoint(x: x0, y: 0), end: CGPoint(x: x0 + 5 * period, y: 0), options: [])
ctx.restoreGState()

// 4. Iris: dark disc that hides the trace behind it, glowing ring, pupil, highlight.
let irisR: CGFloat = 176
ctx.setFillColor(rgb(0x060A16))
ctx.fillEllipse(in: CGRect(x: c.x - irisR - 26, y: c.y - irisR - 26, width: 2 * (irisR + 26), height: 2 * (irisR + 26)))
ctx.saveGState()
ctx.addEllipse(in: CGRect(x: c.x - irisR, y: c.y - irisR, width: 2 * irisR, height: 2 * irisR))
ctx.clip()
radial([rgb(0x0B2F45), rgb(0x0F6F86), rgb(cyan)], c, irisR, locations: [0.35, 0.78, 1.0])
ctx.restoreGState()
gradientStroke(CGPath(ellipseIn: CGRect(x: c.x - irisR, y: c.y - irisR, width: 2 * irisR, height: 2 * irisR),
                      transform: nil), width: 18)
// Fine reticle ticks inside the ring: reads as "measurement" up close, blends into the ring when small.
ctx.saveGState()
ctx.setStrokeColor(rgb(cyan, 0.45))
ctx.setLineWidth(5)
ctx.setLineCap(.round)
for i in 0..<36 {
    let a = CGFloat(i) / 36 * 2 * .pi
    let r0: CGFloat = i % 3 == 0 ? 118 : 132, r1: CGFloat = 154
    ctx.move(to: CGPoint(x: c.x + r0 * cos(a), y: c.y + r0 * sin(a)))
    ctx.addLine(to: CGPoint(x: c.x + r1 * cos(a), y: c.y + r1 * sin(a)))
}
ctx.strokePath()
ctx.restoreGState()
let pupilR: CGFloat = 78
ctx.setFillColor(rgb(0x03050B))
ctx.fillEllipse(in: CGRect(x: c.x - pupilR, y: c.y - pupilR, width: 2 * pupilR, height: 2 * pupilR))
ctx.setFillColor(rgb(0xFFFFFF, 0.92))
ctx.fillEllipse(in: CGRect(x: c.x + 20, y: c.y - 60, width: 32, height: 32))

// 5. Eye outline on top.
gradientStroke(eye, width: 30)

let image = ctx.makeImage()!
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, image, nil)
precondition(CGImageDestinationFinalize(dest))
print("wrote \(out.path)")
