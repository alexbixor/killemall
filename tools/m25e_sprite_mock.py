#!/usr/bin/env python3
"""m25e_sprite_mock.py - how the engine would draw the zombie at each SOURCE resolution (nearest sampling per 3-px ray column and
per screen row, exactly like sprites_f.asm: u = floor(c*W/nc), v = floor(r*H/hd)), at hv 64 (1.5 cells: nc 14, hd 51) and hv 40
(2.4 cells: nc 9, hd 32). Variants: 16x24 (current art), 16x48 (EPX 2x then every other column), 32x48 (EPX 2x), 32x48 EPX + interior
dither. Background = the one-ink floor lattice candidate (floor 0x44/0x00/0x11/0x00) so readability is judged on the real backdrop.
Output build/m25e_sprite_mock.png (6x zoom) + run-list byte counts.
usage: .venv/bin/python tools/m25e_sprite_mock.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m25e_hires_proto import load, epx, dither_interior, runs, ROOT
from PIL import Image, ImageDraw
SLOTW = [3, 3, 2, 4, 4, 2, 3, 3]

def subcols(px): return [r[0::2] for r in px]            # 32 -> 16 columns (left pixel of each pair)

def halo(px):
    h, w = len(px), len(px[0]); out = [r[:] for r in px]
    for y in range(h):
        for x in range(w):
            if px[y][x] == 0 and any(0 <= x + dx < w and 0 <= y + dy < h and px[y + dy][x + dx] == 1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                out[y][x] = 2
    return out

def blit(px, hv, zoom=6):
    """returns an RGB image of a 72 x 96 window crop: floor lattice background + the sprite scaled to hd = 0.8*hv rows, nc = round(2hv/9)
    ray columns of 3 px (slot widths as the engine), feet on row 48 + hv/2, sampled nearest from the source."""
    H, W = len(px), len(px[0]); hd = int(0.8 * hv) & ~1; nc = max(1, min(28, round(2 * hv / 9)))
    top = 48 + hv // 2 - hd; px = halo(px)
    img = Image.new("RGB", (72, 96), (0, 0, 0)); p = img.load()
    for y in range(96):
        for x in range(72):
            if y >= 48 and ((y % 4 == 0 and x % 8 == 1) or (y % 4 == 2 and x % 8 == 5)): p[x, y] = (255, 255, 255)   # floor lattice 44/00/11/00
            if y < 48 and ((y % 4 == 3 and x % 8 == 3) or (y % 4 == 1 and x % 8 == 7)): p[x, y] = (255, 255, 255)    # ceiling 10/00/01/00 mirrored
    x0 = 36 - (3 * nc) // 2
    xs = x0
    for c in range(nc):
        w = SLOTW[c & 7]; u = (c * W) // nc
        for r in range(hd):
            y = top + r
            if not (0 <= y < 96): continue
            v = (r * H) // hd
            val = px[v][u]
            if val == 0: continue
            col = (255, 255, 255) if val == 1 else (0, 0, 0)
            for dx in range(w):
                if 0 <= xs + dx < 72: p[xs + dx, y] = col
        xs += w
    return img.resize((72 * zoom, 96 * zoom), Image.NEAREST)

def main():
    src = load("04_zombie_walk_a"); e = epx(src)
    variants = [("16x24 current", src, 24), ("16x48 vertical EPX", subcols(e), 48), ("32x48 EPX", e, 48), ("32x48 EPX+dither", dither_interior(e), 48)]
    for lab, px, bh in variants:
        print("%-22s %dx%d run-list bytes %d" % (lab, len(px[0]), len(px), runs(px, bh)[0]))
    panels = []
    for hv in (64, 40):
        for lab, px, bh in variants:
            panels.append(("hv %d: %s" % (hv, lab), blit(px, hv)))
    pw, ph = panels[0][1].size; cols = 4
    sheet = Image.new("RGB", (cols * (pw + 8) + 8, 2 * (ph + 24) + 8), (60, 60, 60)); d = ImageDraw.Draw(sheet)
    for i, (lab, im) in enumerate(panels):
        x = 8 + (i % cols) * (pw + 8); y = 8 + (i // cols) * (ph + 24)
        d.text((x, y), lab, fill=(255, 255, 0)); sheet.paste(im, (x, y + 16))
    out = ROOT / "build/m25e_sprite_mock.png"; sheet.save(out); print("sheet", out, sheet.size)

if __name__ == "__main__":
    main()
