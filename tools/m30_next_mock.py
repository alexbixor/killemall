#!/usr/bin/env python3
"""m30_next_mock.py - Spectrum Next "option A" look mock-ups (4 Nov 2026), honest to the hardware:
  * 3D view = LoRes layer 128x80 (each pixel 2x2 screen pixels), ONE palette of 256 colours = 16 material ramps x 16 levels,
    every entry rounded to the Next's 9-bit colour (512 colours). Distance fog + per-cell torch light = ramp level drop,
    exactly what pre-shaded texture copies give the engine (benchmark m30_bench). Far textures use averaged 16x16 / 8x8
    copies (mip levels) so distant walls do not turn into noise.
  * Option A geometry: every map cell has its own floor and ceiling height; stairs, raised altar, tall hall, look up/down
    (horizon shift) and eye height follow the floor you stand on.
  * Enemies and the weapon = hardware sprites: full 256x192 resolution over the chunky 3D, own colours, 1-px dark outline,
    sizes limited to the chip's 1x/2x/4x scaling of a few base sizes (nearest size used, as the real engine would).
  * HUD = Layer 2 at full resolution in the bottom 32 lines (3D view therefore 80 LoRes rows), Spectrum ROM font (48.rom).
Writes build/m30_next_mock_<name>.png (4x = 1024x768) for the scenes in SCENES. usage: m30_next_mock.py [scene ...]"""
import math, pathlib, random, sys
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 128, 80
F = 64.0                                  # focal length in LoRes pixels: 90 degree field of view (wall 1.0 high at distance 1 = 64 rows)
random.seed(7)
ROMFONT = (ROOT / "tools/zesarux/48.rom").read_bytes()[0x3D00:0x4000]

# ---------------- material ramps (16 colours each, dark -> light); palette index = material*16 + level
def ramp(dark, light, bias=0.0):
    """dark/light in Next units 0..7 per channel; 16 levels, each channel rounded separately -> neutral stays neutral"""
    return [tuple(int(round(d + (l - d) * ((i / 15.0) ** (1.0 + bias)))) * 255 // 7 for d, l in zip(dark, light)) for i in range(16)]
MAT = {
    "stone":  ramp((0, 0, 0), (6, 6, 6)),
    "mortar": ramp((0, 0, 0), (3, 3, 3)),
    "brick":  ramp((1, 0, 0), (6, 3, 2)),
    "wood":   ramp((1, 0, 0), (6, 4, 2)),
    "iron":   ramp((0, 0, 1), (5, 5, 6)),
    "moss":   ramp((0, 1, 0), (3, 5, 2)),
    "flag":   ramp((0, 0, 0), (5, 5, 4)),
    "plaster":ramp((1, 1, 0), (7, 6, 5)),
    "gold":   ramp((2, 1, 0), (7, 6, 2)),
    "flame":  ramp((2, 0, 0), (7, 7, 4), -0.4),
    "blood":  ramp((1, 0, 0), (6, 1, 1)),
    "water":  ramp((0, 0, 1), (2, 4, 6)),
    "rust":   ramp((1, 0, 0), (5, 3, 1)),
    "bone":   ramp((1, 1, 0), (7, 7, 5)),
    "dark":   ramp((0, 0, 0), (1, 1, 2)),
    "sky":    ramp((0, 0, 0), (2, 2, 4)),
}
MATS = list(MAT.keys())
def q9(c): return tuple(max(0, min(255, (v >> 5) * 255 // 7)) for v in c)   # Next colours are 3 bits per channel
PAL = [c for m in MATS for c in MAT[m]]
assert len(PAL) == 256

# ---------------- procedural textures: 32x32 arrays of (material, level 0..15), plus averaged 16x16 and 8x8 copies
def noise(u, v, s=1.0): return (math.sin(u * 12.9898 * s + v * 78.233) * 43758.5453) % 1.0
# Pixel-art rule: ONE tone per block (brick, slab, plank), never per texel -> no speckle at any distance.
def block(u, v, bw, bh):
    """running-bond block id and the texel position inside the block: (bx, by, x, y)"""
    by = v // bh; off = bw // 2 if by % 2 else 0
    return (u + off) // bw, by, (u + off) % bw, v % bh
def tone(bx, by, n, seed=1.0): return int(noise(bx * 1.0, by * 1.0, seed) * n)
def tex_stone(u, v):
    bx, by, x, y = block(u, v, 16, 8)
    if x == 0 or y == 0 or x == 15 or y == 7: return ("mortar", 5)
    bevel = 1 if (x == 1 or y == 1) else (-1 if (x == 14 or y == 6) else 0)
    return ("stone", max(0, min(15, 8 + tone(bx, by, 4) + bevel)))
def tex_brick(u, v):
    bx, by, x, y = block(u, v, 16, 8)
    if y in (6, 7) or x in (14, 15): return ("mortar", 7)
    return ("brick", max(0, min(15, 9 + tone(bx, by, 3, 1.5) + (1 if y == 0 else 0))))
def tex_iron(u, v):
    x, y = u % 16, v % 16
    if x in (2, 13) and y in (2, 13): return ("iron", 15)
    if x == 0 or y == 0: return ("iron", 3)
    if x == 15 or y == 15: return ("iron", 12)
    return ("iron", 8 + tone(u // 16, v // 16, 2, 0.7))
def tex_wood(u, v):
    plank = (u // 8) % 4
    if u % 8 == 0: return ("dark", 6)
    grain = int(3 * math.sin(v * 0.6 + plank * 2 + math.sin(u * 0.9) * 1.5))
    return ("wood", max(0, min(15, 9 + grain)))
def tex_flag(u, v):
    x, y = u % 16, v % 16
    if x in (0, 1) or y in (0, 1) or (x in (8, 9) and y > 9) or (y in (8, 9) and x < 8): return ("dark", 9)
    slab = 0 if (y <= 7 and x < 8) else (1 if y <= 9 else (2 if x < 8 else 3))
    return ("flag", 9 + tone(u // 16 * 4 + slab, v // 16, 3, 1.3))
def tex_plaster(u, v):
    if (u % 16) < 2: return ("wood", 7)
    return ("plaster", 9 + tone(u // 8, v // 8, 2, 0.8))
def tex_moss(u, v):
    bx, by, x, y = block(u, v, 16, 8)
    m, l = tex_stone(u, v)
    if m == "stone" and by >= 2 and noise(bx * 1.7, by * 1.3) > 0.45:
        return ("moss", max(0, min(15, 7 + tone(bx, by, 4, 2.2) + (1 if y <= 2 else 0))))
    return (m, l)
def tex_altar(u, v):
    x, y = u % 16, v % 16
    if (x + y) % 16 in (0, 1, 15) or abs(x - y) in (0, 1, 15): return ("gold", 12)
    if x in (0, 15) or y in (0, 15): return ("dark", 9)
    return ("bone", 9 + tone(u // 16, v // 16, 3))
def tex_dais(u, v):                          # riser faces of steps: gold nosing, dark shadow line, bone blocks
    if v < 2: return ("gold", 13)
    if v == 2: return ("dark", 12)
    x, y = u % 8, (v - 3) % 6
    if x == 0 or y == 0: return ("mortar", 5)
    return ("bone", 8 + tone(u // 8, (v - 3) // 6, 3))
def tex_tread(u, v):                         # tops of steps: bone slabs, two per cell each way
    x, y = u % 16, v % 16
    if x in (0, 15) or y in (0, 15): return ("dark", 8)
    return ("bone", 7 + tone(u // 16, v // 16, 3, 1.7))
def tex_lintel(u, v):
    if v < 3: return ("dark", 10)
    if v in (3, 4): return ("gold", 11)
    return tex_stone(u, v)
def tex_vault(u, v):
    x, y = u % 16, v % 16
    if (x in (7, 8) and y in (7, 8)): return ("gold", 11)
    if x in (7, 8) or y in (7, 8): return ("stone", 9)
    return ("stone", 7 + tone(u // 8, v // 8, 2))
def tex_water(u, v): return ("water", 6 + int(4 * (0.5 + 0.5 * math.sin(u * 0.8 + v * 0.5))))
TEXF = {"stone": tex_stone, "brick": tex_brick, "iron": tex_iron, "wood": tex_wood, "flag": tex_flag, "plaster": tex_plaster,
        "moss": tex_moss, "altar": tex_altar, "water": tex_water, "dais": tex_dais, "vault": tex_vault, "lintel": tex_lintel,
        "tread": tex_tread}
def merge(blk):
    """majority material (first wins a tie, deterministic) and the mean level"""
    best = None
    for m, _ in blk:
        c = sum(1 for mm, _ in blk if mm == m); lv = sum(l for mm, l in blk if mm == m) / float(c)
        if best is None or (c, lv) > (best[1], best[2]): best = (m, c, lv)
    return (best[0], int(round(sum(l for _, l in blk) / float(len(blk)))))
def halve_u(t): return [[merge([row[u], row[u + 1]]) for u in range(0, len(row), 2)] for row in t]
def halve_v(t): return [[merge([t[v][u], t[v + 1][u]]) for u in range(len(t[0]))] for v in range(0, len(t), 2)]
SIZES = (32, 16, 8, 4, 2)
TEX = {}                                     # TEX[name][(iu, iv)] = texture with SIZES[iu] columns and SIZES[iv] rows
for k, f in TEXF.items():
    levels = {(0, 0): [[f(u, v) for u in range(32)] for v in range(32)]}
    for iu in range(1, 5): levels[(iu, 0)] = halve_u(levels[(iu - 1, 0)])
    for iu in range(5):
        for iv in range(1, 5): levels[(iu, iv)] = halve_v(levels[(iu, iv - 1)])
    TEX[k] = levels
def lvl_for(cells_per_px):
    """smallest texture that still gives at most ~1.5 texels per screen pixel in that direction"""
    for i, n in enumerate(SIZES):
        if n * cells_per_px <= 1.5: return i
    return 4
def texel(tex, fu, fv, cu, cv):
    """cu / cv = how many cells one screen pixel covers horizontally / vertically at this depth"""
    t = TEX[tex][(lvl_for(cu), lvl_for(cv))]; nv = len(t); nu = len(t[0])
    return t[int((fv % 1.0) * nv)][int((fu % 1.0) * nu)]

# ---------------- the level: per-cell floor/ceiling height, wall / floor / ceiling textures, torch light
# '#' stone wall, 'B' brick wall, 'I' iron wall, 'W' wooden door (solid), 'P' pillar; '.' corridor (floor 0, ceil 1.0),
# 'a','b','c' steps (-0.17/-0.33/-0.5 of the way), 'H' hall (floor -0.5, ceil 2.0), 's','t' altar steps (+0.0, +0.2), 'U' altar (+0.4),
# 'w' water pool (-0.75), 'L' low crawl (floor 0, ceil 0.6)
LEVEL = [
    "BBBBBBBBBBBBBBBBBBBBBBBB",
    "B......BMMMMMMMMMMMMMMMM",
    "B......WMMMMMMMUUUUUMMMM",
    "B......BMMMMMMtttttttMMM",
    "BBBB.BBBMMMMMsssssssssMM",
    "#..#.MMMMMMMMHHHHHHHHHMM",
    "#..#.......abHPHHHHHHHHM",
    "#..#.......abHHHHHHwwHHM",
    "#..#.......abHPHHHHwwHHM",
    "#..#.MMMMMMMMHHHHHHHHHMM",
    "#..#.MMMMMMMHHHHHHHHHMMM",
    "#..LLLL##################",
    "#.......I.....I.........",
    "#########IIIIIIIIIIIIIII",
]
SOLID = {"#": "stone", "B": "brick", "I": "iron", "W": "wood", "P": "moss", "M": "moss"}
HEIGHTS = {".": (0.0, 1.0), "a": (-0.17, 2.0), "b": (-0.33, 2.0), "H": (-0.5, 2.0), "s": (-0.25, 2.0), "t": (0.0, 2.0),
           "U": (0.25, 2.0), "w": (-0.75, 2.0), "L": (0.0, 0.6)}
def cell(cx, cy):
    if not (0 <= cy < len(LEVEL) and 0 <= cx < len(LEVEL[0])): return dict(solid="stone")
    ch = LEVEL[cy][cx]
    if ch in SOLID: return dict(solid=SOLID[ch])
    floor, ceil = HEIGHTS[ch]
    ftex = {"U": "altar", "s": "tread", "t": "tread", "a": "tread", "b": "tread", "w": "water"}.get(ch, "flag")
    ctex = "plaster" if ch in ".L" else "vault"
    wtex = "moss" if ch in "HwUst" else "stone"
    return dict(solid=None, floor=floor, ceil=ceil, ftex=ftex, ctex=ctex, wtex=wtex, ch=ch)
TORCHES = [(4.5, 7.5, 1.0), (12.5, 1.5, 0.9), (13.5, 9.5, 0.9), (20.5, 4.5, 0.9), (2.5, 12.5, 0.8), (8.5, 12.5, 0.7), (15.5, 2.5, 1.2), (19.5, 2.5, 1.2), (10.5, 7.5, 0.8), (14.5, 12.5, 0.8)]
def light_at(x, y):
    l = 0.45
    for tx, ty, k in TORCHES: l += k * 0.9 / (1.0 + ((x - tx) ** 2 + (y - ty) ** 2) * 0.30)
    return min(1.0, l)
LIGHT = {}
def light_cell(cx, cy):
    if (cx, cy) not in LIGHT: LIGHT[(cx, cy)] = light_at(cx + 0.5, cy + 0.5)
    return LIGHT[(cx, cy)]

# ---------------- renderer (option A: variable floor/ceiling per cell, pitch, eye height)
def shade_index(mat, lvl, shade):
    return MATS.index(mat) * 16 + max(0, min(15, int(lvl * (0.35 + 0.65 * shade) + 0.5)))
def fog(d): return max(0.15, 1.0 - d / 10.0)

def render(px, py, ang, pitch_px=0, crouch=0.0):
    img = [[MATS.index("dark") * 16] * W for _ in range(H)]
    zbuf = [1e9] * W
    dirx, diry = math.cos(ang), math.sin(ang)
    plx, ply = -diry * (64.0 / F), dirx * (64.0 / F)
    here = cell(int(px), int(py)); eye = (here["floor"] if not here["solid"] else 0.0) + 0.70 + crouch
    horizon = H / 2.0 - pitch_px             # pitch_px > 0 = look down: the horizon moves up the screen
    def ys(h, d): return horizon - (h - eye) * F / d
    for col in range(W):
        cam = 2.0 * (col + 0.5) / W - 1.0
        rx, ry = dirx + plx * cam, diry + ply * cam
        mx, my = int(px), int(py)
        ddx = abs(1.0 / rx) if rx else 1e30; ddy = abs(1.0 / ry) if ry else 1e30
        sx = -1 if rx < 0 else 1; sy = -1 if ry < 0 else 1
        sdx = (px - mx) * ddx if rx < 0 else (mx + 1.0 - px) * ddx
        sdy = (py - my) * ddy if ry < 0 else (my + 1.0 - py) * ddy
        cur = cell(mx, my); dprev = 0.02
        ytop, ybot = 0, H
        def span(y0, y1, h, tex):
            a, b = max(ytop, int(math.ceil(y0))), min(ybot, int(math.ceil(y1)))
            if b <= a: return
            for y in range(a, b):
                dy = (y + 0.5) - horizon
                if abs(dy) < 1e-6: continue
                d = (eye - h) * F / dy
                if d <= 0: continue
                wx, wy = px + rx * d, py + ry * d
                t = texel(tex, wx, wy, d / F, d * d / (abs(eye - h) * F))
                img[y][col] = shade_index(t[0], t[1], fog(d) * light_cell(int(wx), int(wy)))
        def wall(y0, y1, hitu, htop, hbot, tex, d, lightv, riser=False, nosing=False):
            a, b = max(ytop, int(math.ceil(y0))), min(ybot, int(math.ceil(y1)))
            if b <= a: return
            for y in range(a, b):
                h = htop - ((y + 0.5) - y0) / (y1 - y0) * (htop - hbot)
                if nosing and y0 >= ytop and (y == a or (y == a + 1 and d < 3.0)): img[y][col] = shade_index("gold", 13, fog(d)); continue
                t = texel(tex, hitu, min(0.999, (htop - h)) if riser else -h, d / F, d / F)
                img[y][col] = shade_index(t[0], t[1], fog(d) * lightv * (0.75 if riser else 1.0))
        for _ in range(64):
            if sdx < sdy: sdx += ddx; mx += sx; side = 0; d = sdx - ddx
            else: sdy += ddy; my += sy; side = 1; d = sdy - ddy
            d = max(d, 0.02)
            nxt = cell(mx, my)
            yf1, yf0 = ys(cur["floor"], dprev), ys(cur["floor"], d)
            if yf1 > yf0: span(yf0, yf1, cur["floor"], cur["ftex"]); ybot = min(ybot, max(ytop, int(math.ceil(yf0))))
            yc0, yc1 = ys(cur["ceil"], dprev), ys(cur["ceil"], d)
            if yc1 > yc0: span(yc0, yc1, cur["ceil"], cur["ctex"]); ytop = max(ytop, min(ybot, int(math.ceil(yc1))))
            hitu = (py + ry * d) if side == 0 else (px + rx * d)
            lv = light_cell(mx - (sx if side == 0 else 0), my - (sy if side == 1 else 0)) * (0.78 if side == 1 else 1.0)
            if nxt["solid"]:
                wall(ys(cur["ceil"], d), ys(cur["floor"], d), hitu, cur["ceil"], cur["floor"], nxt["solid"], d, lv)
                zbuf[col] = d; break
            if nxt["floor"] > cur["floor"]:
                wall(ys(nxt["floor"], d), ys(cur["floor"], d), hitu, nxt["floor"], cur["floor"], "dais", d, lv, riser=True, nosing=True)
                ybot = min(ybot, int(math.ceil(ys(nxt["floor"], d))))
            elif nxt["floor"] < cur["floor"]:                     # step down ahead: light the edge of the tread we are leaving
                r = int(math.ceil(ys(cur["floor"], d)))
                for rr in ((r, r + 1) if d < 4.0 else (r,)):
                    if ytop <= rr < ybot: img[rr][col] = shade_index("gold", 12, fog(d))
            if nxt["ceil"] < cur["ceil"]:
                wall(ys(cur["ceil"], d), ys(nxt["ceil"], d), hitu, cur["ceil"], nxt["ceil"], "lintel", d, lv * 0.85, riser=True)
                ytop = max(ytop, int(math.ceil(ys(nxt["ceil"], d))))
            if ytop >= ybot: zbuf[col] = d; break
            cur = nxt; dprev = d
    return img, zbuf, (dirx, diry, plx, ply, eye, horizon)

# ---------------- hardware sprites (hi-res 256x192 grid = 2x LoRes), own colours, dark outline
def outline(im):
    w, h = im.size; px = im.load(); out = im.copy(); op = out.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 0:
                if any(0 <= x + i < w and 0 <= y + j < h and px[x + i, y + j][3] and (i or j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
                    op[x, y] = (0, 0, 0, 255)
    return out
def imp_art(w, h):
    S = 8; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx = w * S / 2; g = h * S
    def el(x0, y0, x1, y1, c): d.ellipse([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=c)
    body = (176, 52, 36, 255); dark = (96, 24, 16, 255); light = (230, 110, 70, 255)
    for s in (-1, 1):
        d.polygon([(cx + s * w * S * 0.08, g * 0.62), (cx + s * w * S * 0.26, g * 0.63), (cx + s * w * S * 0.28, g * 0.90), (cx + s * w * S * 0.12, g * 0.90)], fill=dark)
        d.polygon([(cx + s * w * S * 0.10, g * 0.88), (cx + s * w * S * 0.34, g * 0.88), (cx + s * w * S * 0.36, g * 0.99), (cx + s * w * S * 0.08, g * 0.99)], fill=(40, 10, 8, 255))   # hooves
    el(cx - w * S * 0.30, g * 0.30, cx + w * S * 0.30, g * 0.70, body)
    el(cx - w * S * 0.20, g * 0.33, cx + w * S * 0.10, g * 0.52, light)
    for s in (-1, 1):
        d.polygon([(cx + s * w * S * 0.26, g * 0.34), (cx + s * w * S * 0.46, g * 0.42), (cx + s * w * S * 0.50, g * 0.68), (cx + s * w * S * 0.40, g * 0.68), (cx + s * w * S * 0.33, g * 0.48)], fill=body)
        el(cx + s * w * S * 0.45 - w * S * 0.07, g * 0.62, cx + s * w * S * 0.45 + w * S * 0.07, g * 0.74, dark)
    el(cx - w * S * 0.20, g * 0.10, cx + w * S * 0.20, g * 0.36, body)
    for s in (-1, 1):
        d.polygon([(cx + s * w * S * 0.12, g * 0.14), (cx + s * w * S * 0.30, g * 0.0), (cx + s * w * S * 0.20, g * 0.18)], fill=(236, 226, 190, 255))
        el(cx + s * w * S * 0.10 - w * S * 0.05, g * 0.19, cx + s * w * S * 0.10 + w * S * 0.05, g * 0.24, (255, 230, 60, 255))
    d.polygon([(cx - w * S * 0.10, g * 0.29), (cx + w * S * 0.10, g * 0.29), (cx, g * 0.33)], fill=(20, 0, 0, 255))
    im = im.resize((w, h), Image.LANCZOS); px = im.load()
    for y in range(h):
        for x in range(w):
            r, gg, b, a = px[x, y]
            if a < 128: px[x, y] = (0, 0, 0, 0); continue
            if gg > 150 and r > 200: px[x, y] = (255, 219, 0, 255); continue
            if r > 200 and gg > 180: px[x, y] = (219, 219, 182, 255); continue
            px[x, y] = q9((r, gg, b)) + (255,)
    return outline(im)
def brazier_art(w, h):
    S = 8; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cx = w * S / 2.0; g = h * S
    d.ellipse([cx - w * S * 0.42, g * 0.70, cx + w * S * 0.42, g * 0.98], fill=(50, 50, 62, 255))
    d.ellipse([cx - w * S * 0.36, g * 0.66, cx + w * S * 0.36, g * 0.78], fill=(100, 100, 118, 255))
    d.polygon([(cx - w * S * 0.30, g * 0.72), (cx - w * S * 0.12, g * 0.05), (cx + w * S * 0.04, g * 0.30), (cx + w * S * 0.32, g * 0.72)], fill=(200, 40, 20, 255))
    d.polygon([(cx - w * S * 0.20, g * 0.72), (cx - w * S * 0.06, g * 0.24), (cx + w * S * 0.04, g * 0.42), (cx + w * S * 0.20, g * 0.72)], fill=(240, 130, 30, 255))
    d.polygon([(cx - w * S * 0.10, g * 0.72), (cx, g * 0.44), (cx + w * S * 0.10, g * 0.72)], fill=(255, 230, 80, 255))
    im = im.resize((w, h), Image.LANCZOS); px = im.load()
    for y in range(h):
        for x in range(w):
            r, gg, b, a = px[x, y]
            px[x, y] = (0, 0, 0, 0) if a < 128 else q9((r, gg, b)) + (255,)
    return outline(im)
KINDS = {"imp": (imp_art, 0.9, True), "brazier": (brazier_art, 0.55, False)}   # art, height in cells, lit by the scene (else emissive)
BASE_SIZES = [(16, 24), (20, 32), (28, 40), (32, 48)]
def sprite_size(want_h):
    best = None
    for bw, bh in BASE_SIZES:
        for sc in (1, 2, 4):
            if best is None or abs(bh * sc - want_h) < abs(best[1] - want_h): best = (bw * sc, bh * sc, (bw, bh), sc)
    return best
def shotgun_art(w=64, h=64):
    S = 8; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); X = w * S / 64.0; Y = h * S / 64.0
    def P(pts, c): d.polygon([(x * X, y * Y) for x, y in pts], fill=c)
    steel, steel_d, steel_l = (84, 84, 104, 255), (40, 40, 56, 255), (170, 170, 196, 255)
    wood, wood_d, wood_l = (122, 70, 30, 255), (70, 36, 12, 255), (176, 110, 50, 255)
    glove, glove_d, glove_l = (150, 92, 48, 255), (90, 50, 24, 255), (200, 140, 80, 255)
    # stock + receiver (lower right), angled up-left into the scene
    P([(30, 64), (58, 64), (64, 46), (46, 40), (34, 48)], wood_d); P([(33, 64), (56, 64), (61, 48), (47, 43), (37, 50)], wood)
    P([(38, 52), (46, 45), (50, 46), (42, 55)], wood_l)
    P([(26, 44), (42, 36), (48, 46), (34, 56)], steel_d); P([(28, 44), (41, 38), (45, 45), (33, 53)], steel)   # receiver
    # magazine tube and barrel from the receiver to the muzzle (upper centre)
    P([(26, 44), (38, 36), (30, 6), (24, 6)], steel_d)                                            # tube
    P([(24, 42), (34, 34), (30, 4), (24, 2)], steel); P([(28, 40), (32, 36), (29, 4), (27, 4)], steel_l)   # barrel + highlight
    P([(23, 6), (31, 6), (31, 1), (23, 1)], steel_d); P([(24, 5), (30, 5), (30, 2), (24, 2)], steel)        # muzzle ring
    # fore-end (pump) with grooves
    P([(20, 36), (36, 26), (38, 34), (24, 44)], wood_d); P([(21, 36), (35, 27), (37, 33), (24, 42)], wood)
    for i in range(4): P([(23 + i * 3, 36 - i * 2), (24 + i * 3, 36 - i * 2 - 1), (26 + i * 3, 41 - i * 2 - 1), (25 + i * 3, 41 - i * 2)], wood_d)
    # gloved left hand gripping the pump: palm + four fingers + thumb
    d.ellipse([12 * X, 30 * Y, 32 * X, 48 * Y], fill=glove)
    for i in range(4): d.ellipse([(15 + i * 4) * X, (27 + i * 2) * Y, (20 + i * 4) * X, (33 + i * 2) * Y], fill=glove_l)
    for i in range(4): P([(17 + i * 4, 31 + i * 2), (18 + i * 4, 33 + i * 2), (16 + i * 4, 34 + i * 2)], glove_d)
    d.ellipse([10 * X, 36 * Y, 20 * X, 48 * Y], fill=glove_d); d.ellipse([11 * X, 37 * Y, 18 * X, 46 * Y], fill=glove)
    P([(14, 48), (30, 48), (30, 54), (14, 54)], glove_d)                                           # cuff
    im = im.resize((w, h), Image.LANCZOS); px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b_, a_ = px[x, y]
            px[x, y] = (0, 0, 0, 0) if a_ < 128 else q9((r, g, b_)) + (255,)
    return outline(im)

def rom_text(draw, x, y, text, colour):
    for ch in text:
        glyph = ROMFONT[(ord(ch) - 32) * 8:(ord(ch) - 32) * 8 + 8]
        for j in range(8):
            for i in range(8):
                if glyph[j] & (0x80 >> i): draw.point((x + i, y + j), fill=colour)
        x += 8
def hud(draw, y0, health, ammo, keys, kills, level):
    for i in range(32): draw.line([(0, y0 + i), (255, y0 + i)], fill=(22 + i // 2, 22 + i // 2, 28 + i // 2))
    draw.rectangle([0, y0, 255, y0 + 1], fill=(182, 36, 36)); draw.rectangle([0, y0 + 2, 255, y0 + 2], fill=(73, 0, 0))
    red, cream, grey = (219, 73, 73), (219, 219, 182), (146, 146, 146)
    rom_text(draw, 4, y0 + 5, "HEALTH", red); rom_text(draw, 80, y0 + 5, "AMMO %2d" % ammo, red); rom_text(draw, 152, y0 + 5, "KEYS", red); rom_text(draw, 200, y0 + 5, "KILLS %d" % kills, red)
    draw.rectangle([4, y0 + 17, 68, y0 + 25], outline=grey); draw.rectangle([5, y0 + 18, 5 + int(62 * health / 100), y0 + 24], fill=(219, 36, 36) if health < 35 else (36, 182, 36))
    rom_text(draw, 80, y0 + 17, "SHOTGUN", cream)
    for i, (c, on) in enumerate(zip([(219, 36, 36), (36, 73, 219), (219, 219, 36)], keys)):
        draw.rectangle([152 + i * 12, y0 + 17, 160 + i * 12, y0 + 25], fill=c if on else (40, 40, 44), outline=(90, 90, 90))
    rom_text(draw, 200, y0 + 17, level[:7], grey)

def compose(name, px, py, ang_deg, pitch_px, crouch, enemies, health=72, ammo=14, keys=(1, 0, 0), kills=7, level="CRYPT"):
    img, zbuf, (dirx, diry, plx, ply, eye, horizon) = render(px, py, math.radians(ang_deg), pitch_px, crouch)
    out = Image.new("RGB", (256, 192), (0, 0, 0)); o = out.load()
    det = plx * diry - dirx * ply
    placed = []
    for e in sorted(enemies, key=lambda e: -((e[0] - px) ** 2 + (e[1] - py) ** 2)):
        ex, ey = e[0], e[1]; kind = e[2] if len(e) > 2 else "imp"; artf, cells_high, lit = KINDS[kind]
        c = cell(int(ex), int(ey)); efloor = c["floor"] if not c["solid"] else 0.0
        sx, sy = ex - px, ey - py
        tx = (diry * sx - dirx * sy) / det; ty = (-ply * sx + plx * sy) / det
        if ty < 0.3 or abs(tx / ty) > 1.3: print("  WARNING enemy (%.1f, %.1f) outside the view: depth %.2f lateral/depth %.2f" % (ex, ey, ty, tx / ty if ty else 0)); continue
        scr_x = (W / 2.0) * (1 + tx / ty)
        bw, bh, base, sc = sprite_size(F * cells_high / ty * 2)
        foot = horizon - (efloor - eye) * F / ty
        placed.append((ex, ey, ty, scr_x, bw, bh, base, foot, artf, lit))
        if not lit: continue
        # shadow: darken the floor pixels under the feet (same material, lower level) - an ellipse bw/4 wide, bw/12 high in LoRes pixels
        rx_, ry_ = max(1.0, bw / 4.0), max(0.7, bw / 14.0)
        for yy in range(int(foot - ry_), int(foot + ry_) + 1):
            for xx in range(int(scr_x - rx_), int(scr_x + rx_) + 1):
                if 0 <= xx < W and 0 <= yy < H and zbuf[xx] >= ty and ((xx + 0.5 - scr_x) / rx_) ** 2 + ((yy + 0.5 - foot) / ry_) ** 2 <= 1.0:
                    idx = img[yy][xx]; img[yy][xx] = (idx // 16) * 16 + max(0, idx % 16 - 7)
    for y in range(H):
        for x in range(W):
            c = PAL[img[y][x]]
            o[x * 2, y * 2] = c; o[x * 2 + 1, y * 2] = c; o[x * 2, y * 2 + 1] = c; o[x * 2 + 1, y * 2 + 1] = c
    for ex, ey, ty, scr_x, bw, bh, base, foot, artf, lit in placed:
        art = artf(*base).resize((bw, bh), Image.NEAREST); ap = art.load()
        x0 = int(scr_x * 2 - bw / 2); y0 = int(foot * 2 - bh)
        sh = 0.6 + 0.4 * fog(ty) * light_cell(int(ex), int(ey))
        for yy in range(bh):
            for xx in range(bw):
                X, Y = x0 + xx, y0 + yy
                if not (0 <= X < 256 and 0 <= Y < H * 2) or zbuf[X // 2] < ty: continue
                r, g, b, a = ap[xx, yy]
                if a == 0: continue
                if lit and not (r > 200 and g > 200) and (r, g, b) != (0, 0, 0): r, g, b = int(r * sh), int(g * sh), int(b * sh)
                o[X, Y] = q9((r, g, b))
    gun = shotgun_art(); out.paste(gun, (120, H * 2 - 64), gun)
    hud(ImageDraw.Draw(out), H * 2, health, ammo, keys, kills, level)
    big = out.resize((1024, 768), Image.NEAREST); big.save(ROOT / ("build/m30_next_mock_%s.png" % name)); return big

SCENES = {
    # name: (px, py, angle deg (0 = +x east, 90 = +y south), pitch px (+ = look DOWN), crouch, sprites [(x, y[, kind])] - floor height from the cell)
    "altar_hall":  (15.3, 7.4, -76, 2, 0.0, [(16.3, 3.6), (17.0, 5.9), (15.5, 2.45, "brazier"), (19.5, 2.45, "brazier")]),
    "stairs_up":   (15.5, 7.5, 180, -4, 0.0, [(12.4, 8.2), (9.6, 6.4)]),
    "stairs_down": (10.3, 7.2, 14, 9, 0.0, [(14.6, 7.9), (17.4, 9.4)]),
    "look_up":     (13.5, 8.5, 20, -24, 0.0, [(16.6, 9.6)]),
}
if __name__ == "__main__":
    for n in (sys.argv[1:] or list(SCENES)):
        compose(n, *SCENES[n]); print("wrote build/m30_next_mock_%s.png" % n)
