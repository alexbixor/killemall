#!/usr/bin/env python3
"""m25_mock.py - attribute-legal mock stills of M2.5 layouts, float raycaster mimicking the engine look (gen48 textures,
CODEINK inks, dark-side 0xAA shade, floor checker + half-cell lines, textured ceiling = sparse dots + mirrored lines).
Sprite modes:  card = M2.4 (every cell of the sprite's byte-column span blacked + tinted)
               mono = masked sprite with 1-px black halo, no own attribute (inherits the cell ink)
               core = mono + cells lying fully inside the dilated silhouette are tinted with the sprite ink
               mono1[:ink] = whole 3D window drawn in ONE ink (default 7), sprite masked + halo, no attribute writes at all (TTT / Knight Lore)
               wins = mono + every cell touched by sprite ink takes the sprite ink; wall pixels are kept (sprite colour box on the wall)
usage: m25_mock.py out.png RAYS PXW PLANE MODE [px py ang256 zx zy]
HUD rows 13..23 are pasted from the real M2.4 screenshot build/m24_v4_start.png (3x), so the still is the full screen.
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image
import gen48
from chk48 import load_level

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAL = {0: (0, 0, 0), 1: (0, 0, 205), 2: (205, 0, 0), 3: (205, 0, 205), 4: (0, 205, 0), 5: (0, 205, 205), 6: (205, 205, 0), 7: (205, 205, 205)}
CODEINK = [0, 2, 7, 6, 5, 4, 7, 3, 6, 2, 1, 2, 4, 0, 0, 0]
FAR_H = 16
ZOMBIE_INK = 4
WROWS = 96
FL_D4 = [240, 240, 192, 128, 96, 77, 64, 55, 48, 43, 38, 35, 32, 30, 27, 26, 24, 23, 21, 20, 19, 18, 17, 17, 16]
FLOOR_INK = [1, 1, 7, 7, 7, 7]        # attr rows 6..11 (blue haze near the horizon, then white)
CEIL_INK = [7, 7, 7, 7, 1, 1]         # attr rows 0..5 (mirror)

def cast(cells, px, py, ang256, rays, plane):
    ang = ang256 * 2 * math.pi / 256
    dx, dy = math.cos(ang), math.sin(ang); pxl, pyl = -plane * dy, plane * dx
    out = []
    for r in range(rays):
        cam = 2 * (r + 0.5) / rays - 1
        rdx, rdy = dx + pxl * cam, dy + pyl * cam
        mx, my = int(px), int(py)
        ddx = abs(1 / rdx) if rdx else 1e9; ddy = abs(1 / rdy) if rdy else 1e9
        stx, sdx = (-1, (px - mx) * ddx) if rdx < 0 else (1, (mx + 1 - px) * ddx)
        sty, sdy = (-1, (py - my) * ddy) if rdy < 0 else (1, (my + 1 - py) * ddy)
        side = 0
        for _ in range(64):
            if sdx < sdy: sdx += ddx; mx += stx; side = 0
            else: sdy += ddy; my += sty; side = 1
            if cells[my * 32 + mx]: break
        dist = (sdx - ddx) if side == 0 else (sdy - ddy)
        hit = (py + dist * rdy) if side == 0 else (px + dist * rdx)
        u = int((hit - math.floor(hit)) * 16) & 15
        out.append((dist, cells[my * 32 + mx] & 15, side, u))
    return out

def load_art(name):
    art = [l.rstrip("\n") for l in (ROOT / "assets/sprites" / name).read_text().splitlines() if l and not l.startswith(";")]
    art = [l.ljust(16, ".")[:16] for l in art][:24]
    inkpx = {(x, y) for y, l in enumerate(art) for x, ch in enumerate(l) if ch == "#"}
    blackpx = {(x, y) for y, l in enumerate(art) for x, ch in enumerate(l) if ch == "o"}
    return inkpx, blackpx

def render(cells, px, py, ang, rays, pxw, plane, mode, zx, zy):
    W = rays * pxw; cols = W // 8
    pix = [[0] * W for _ in range(WROWS)]
    ink = [[0] * cols for _ in range(12)]
    tex = gen48.tex_pages()
    line_words = set()
    for w in range(24):
        top, bot = FL_D4[w], FL_D4[w + 1]
        if (top >> 3) != (bot >> 3) and bot < 64: line_words.add(w)
    for r in range(48, 96):                       # floor: 50 % checker + lines
        w = (r - 48) // 2; odd = (r - 48) % 2
        for x in range(W):
            pix[r][x] = 1 if (w in line_words and odd) else ((x + r) & 1)
    for r in range(0, 48):                        # ceiling: sparse dots 0x44 / 0x11 + mirrored lines
        rm = 47 - r; w = rm // 2; odd = rm % 2
        for x in range(W):
            if w in line_words and odd: pix[r][x] = 1
            else: pix[r][x] = 1 if ((x % 4 == 1 and r % 2 == 0) or (x % 4 == 3 and r % 2 == 1)) else 0
    zb = []
    for c, (dist, code, side, u) in enumerate(cast(cells, px, py, ang, rays, plane)):
        hv = 96 / dist if dist > 0 else 999
        h = max(2, min(96, int(hv))) & ~1 if hv < 96 else 96
        zb.append(min(255, int(hv)))
        top = 48 - h // 2
        page = gen48.TEXMAP[code]
        if hv <= 96: rows = gen48.band_rows(h)
        else:
            hc = int(min(192, hv)); t0 = (hc - 96) // 2
            rows = [((rr * (4096 // hc)) >> 8) & 15 for rr in range(t0, t0 + 96)]
        for i in range(h):
            v = rows[i]
            lit = 1 if h <= FAR_H else (1 if tex[page * 256 + u * 16 + v] else 0)
            for k in range(pxw):
                x = c * pxw + k
                shade = 1 if side == 0 else (((x + top + i) & 1) == 0)
                pix[top + i][x] = lit and shade
        col_ink = CODEINK[code] if h > FAR_H else 7
        for k in range(pxw):
            bc = (c * pxw + k) // 8
            for ar in range(12):
                r0 = ar * 8
                if r0 + 8 <= top: ink[ar][bc] = CEIL_INK[ar] if ar < 6 else 7
                elif r0 >= top + h: ink[ar][bc] = FLOOR_INK[ar - 6] if ar >= 6 else 7
                else: ink[ar][bc] = col_ink
    # ---- zombie at (zx, zy): depth along the view, lateral; feet on the floor line (hd = 0.8125 hv like the engine)
    a = ang * 2 * math.pi / 256
    dxz, dyz = zx - px, zy - py
    depth = dxz * math.cos(a) + dyz * math.sin(a)
    lat = -dxz * math.sin(a) + dyz * math.cos(a)
    hv = 96 / depth; hd = int(hv * 0.8125); top = int(48 + hv / 2 - hd)
    inkpx, blackpx = load_art("04_zombie_walk_a.txt")
    if mode in ("mono", "core", "wins") or mode.startswith("mono1"):   # 1-px halo around the ink -> opaque black
        blackpx = blackpx | ({(x + i, y + j) for (x, y) in inkpx for i in (-1, 0, 1) for j in (-1, 0, 1)
                              if 0 <= x + i < 16 and 0 <= y + j < 24} - inkpx)
    nc = max(1, round(min(128, hv) / 3))           # 2-px sprite columns as the engine (NCTAB = hcol/3)
    cx = W / 2 + (lat / depth) * (W / 2) / plane
    x0 = int(round(cx - nc))
    drawn = {}                                      # (r, x) -> 1 ink / 0 black
    for sc in range(nc):
        u = int(sc * 16 / nc)
        ray = min(rays - 1, max(0, (x0 + 2 * sc) // pxw))
        if zb[ray] > hv: continue
        for v in range(24):
            r0 = max(0, min(96, top + int(v * hd / 24))); r1 = max(0, min(96, top + int((v + 1) * hd / 24)))
            val = 1 if (u, v) in inkpx else (0 if (u, v) in blackpx else None)
            if val is None: continue
            for r in range(r0, r1):
                for k in range(2):
                    x = x0 + 2 * sc + k
                    if 0 <= x < W:
                        pix[r][x] = val; drawn[(r, x)] = val
    if mode == "card":                               # M2.4: byte-column span rows k0*8..k1*8+7 blacked, then tinted
        cells_hit = {(r // 8, x // 8) for (r, x), v in drawn.items() if v == 1}
        for bc in {b for (_, b) in cells_hit}:
            ks = [k for (k, b) in cells_hit if b == bc]
            for k in range(min(ks), max(ks) + 1):
                ink[k][bc] = ZOMBIE_INK
                for r in range(k * 8, k * 8 + 8):
                    for x in range(bc * 8, bc * 8 + 8):
                        if drawn.get((r, x)) != 1: pix[r][x] = 0
    elif mode == "core":                             # tint only cells with no background pixel left
        for k in range(12):
            for bc in range(cols):
                if all((r, x) in drawn for r in range(k * 8, k * 8 + 8) for x in range(bc * 8, bc * 8 + 8)):
                    ink[k][bc] = ZOMBIE_INK
    elif mode == "wins":                             # sprite ink wins in every cell it touches, wall pixels stay lit
        for (r, x), v in drawn.items():
            if v == 1: ink[r // 8][x // 8] = ZOMBIE_INK
    elif mode.startswith("mono1"):                   # one ink for the whole window: zero clash by construction
        tint = int(mode[5:]) if len(mode) > 5 else 7
        for k in range(12):
            for bc in range(cols): ink[k][bc] = tint
    return pix, ink, W

def compose(pix, ink, W, out, label):
    img = Image.new("RGB", (256, 192), (0, 0, 0))
    hud = Image.open(ROOT / "build/m24_v4_start.png").convert("RGB").resize((256, 192), Image.NEAREST)
    img.paste(hud.crop((0, 104, 256, 192)), (0, 104))
    x0 = (256 - W) // 2
    for r in range(WROWS):
        for x in range(W):
            if pix[r][x]:
                img.putpixel((x0 + x, 8 + r), PAL[ink[r // 8][x // 8]])
    for y in range(8, 104):
        img.putpixel((x0 - 1, y), PAL[2]); img.putpixel((x0 + W, y), PAL[2])
    viol = 0
    for cy in range(0, 192, 8):
        for cx in range(0, 256, 8):
            cols = {img.getpixel((cx + i, cy + j)) for i in range(8) for j in range(8)} - {(0, 0, 0)}
            if len(cols) > 1: viol += 1
    big = img.resize((768, 576), Image.NEAREST)
    big.save(out)
    print(f"{out}: window {W}x{WROWS} attr violations {viol} label {label}")
    return img

if __name__ == "__main__":
    out = sys.argv[1]; rays = int(sys.argv[2]); pxw = int(sys.argv[3]); plane = float(sys.argv[4]); mode = sys.argv[5]
    px, py, ang = (float(sys.argv[6]), float(sys.argv[7]), int(sys.argv[8])) if len(sys.argv) > 8 else (3.5, 7.5, 0)
    zx, zy = (float(sys.argv[9]), float(sys.argv[10])) if len(sys.argv) > 10 else (px + 1.5, py + 0.2)
    cells = load_level(ROOT / "build/level01.bin")
    pix, ink, W = render(cells, px, py, ang, rays, pxw, plane, mode, zx, zy)
    compose(pix, ink, W, out, f"{rays} rays x {pxw} px plane {plane} {mode}")
