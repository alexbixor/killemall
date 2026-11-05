#!/usr/bin/env python3
"""m26_pattern_mock3.py - 2 Nov 'make the ceiling a diamond pattern with lines'.
Real 48K engine frames (level-1 start view, zombie ahead). Two ceilings that are diamonds drawn with lines:
  D1 = dotted diagonals, repeats every 8 px x 4 rows  -> fits today's clear routine (2 fill words), 0 bytes / 0 fps.
  D5 = continuous 45-degree diagonals, repeats every 8 px x 8 rows -> needs 4 fill words (code change in CLRBUF).
D5 cannot be poked into the running image (only 2 ceiling words exist), so it is composited exactly: the ceiling
background mask = pixels that differ between a frame with ceiling words 0x0000 and one with 0xFFFF (walls, sprite,
gun, distance lines are identical in both and therefore excluded); every masked pixel takes pattern(x mod 8, row phase).
Outputs build/m26_pattern_sheet3.png and build/m26_pattern_closeup3.png."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img

TOP = 8            # screen row of BUF row 0 (3D window), checked below against the mask bounding box
HORIZON = 48       # BUF row of the first floor row; ceiling word 0 = BUF rows 46/47

def frame(m, de, bc, line, sx, sy, dx, dy):
    m.set_memory_block(SYM["cl_ce"] + 1, bytes([de & 255, de >> 8]))
    m.set_memory_block(SYM["cl_cb"] + 1, bytes([bc & 255, bc >> 8]))
    m.set_memory_block(SYM["cl_cw"] + 1, bytes([line & 255, line >> 8]))
    clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy); call(m, "render", "hud_update")
    return scr_img(bytes(m.memory[16384:16384 + 6912])).convert("L")

def d5(x, bufrow):
    """continuous-line diamonds, 8 px wide x 8 rows tall; r=0 is the ceiling row just above the horizon"""
    r = (HORIZON - 1 - bufrow) % 8; c = x % 8
    return c == r or c == (-r) % 8

def composite(real, black, white, pat):
    out = real.copy(); px = out.load(); pb = black.load(); pw = white.load()
    w, h = real.size; n = 0; ymin = 999
    for y in range(h):
        for x in range(w):
            if pb[x, y] != pw[x, y]:
                ymin = min(ymin, y); n += 1
                px[x, y] = 255 if pat(x, y - TOP) else 0
    return out, n, ymin

def main():
    m = fresh()
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    dx, dy = {0: (1.5, 0), 64: (0, 1.5), 128: (-1.5, 0), 192: (0, -1.5)}.get(ang, (1.5, 0))
    panels = []
    for dist_label, k in (("zombie 1.5 cells away", 1.0), ("zombie 1.0 cell away", 1.0 / 1.5)):
        ddx, ddy = dx * k, dy * k
        today = frame(m, 0x0001, 0x0000, 0x00FF, sx, sy, ddx, ddy)
        again = frame(m, 0x0001, 0x0000, 0x00FF, sx, sy, ddx, ddy)
        d1 = frame(m, 0x2280, 0x2208, 0x22FF, sx, sy, ddx, ddy)
        d6 = frame(m, 0x6681, 0x6618, 0x66FF, sx, sy, ddx, ddy)   # rows top->bottom BC'.lo 0x18, BC'.hi 0x66, DE'.lo 0x81, DE'.hi 0x66: lozenge 8 px x 4 rows, continuous; both odd rows 0x66 so one line word fits either parity
        black = frame(m, 0x0000, 0x0000, 0x00FF, sx, sy, ddx, ddy)
        white = frame(m, 0xFFFF, 0xFFFF, 0x00FF, sx, sy, ddx, ddy)
        rep = sum(1 for a, b in zip(today.getdata(), again.getdata()) if a != b)
        d5img, n, ymin = composite(today, black, white, d5)
        print("%s: repeat-render diff px=%d  ceiling mask px=%d  mask top row=%d (expect %d)" % (dist_label, rep, n, ymin, TOP))
        panels.append((dist_label, today, d1, d6, d5img))
    S = 3; W, H = 194 * S, 98 * S; gap = 12
    cols = [("TODAY: single dots in a square grid", None),
            ("D1: diamonds 8 px wide x 4 rows, DOTTED diagonal edges - no code change", None),
            ("D6: diamonds 8 px wide x 4 rows, SOLID stepped edges - no code change", None),
            ("D5: diamonds 8 px wide x 8 rows, SOLID 45-degree edges (same diamonds as the floor dots) - small code change", None)]
    NC = len(cols)
    sheet = Image.new("RGB", (NC * W + (NC + 1) * gap, 50 + 2 * (H + 40)), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((gap, 6), "Ceiling = a diamond pattern drawn with lines. Real 48K engine frames; the floor keeps its diamond dots everywhere.", fill=(255, 255, 0))
    d.text((gap, 22), "Row 1: zombie 1.5 cells away. Row 2: zombie 1.0 cell away (does the busier ceiling hurt the head?).", fill=(255, 255, 0))
    tiles = []
    for ri, (dist_label, *imgs) in enumerate(panels):
        for ci, img in enumerate(imgs):
            x = gap + ci * (W + gap); y = 50 + ri * (H + 40)
            d.text((x, y), cols[ci][0] if ri == 0 else dist_label, fill=(255, 255, 255))
            crop = img.crop((31, 7, 225, 105)).convert("RGB")
            sheet.paste(crop.resize((W, H), Image.NEAREST), (x, y + 14))
            if ri == 0:
                tiles.append((cols[ci][0][:44], img.crop((96, 8, 160, 40)).convert("RGB")))
    out = ROOT / "build/m26_pattern_sheet3.png"; sheet.save(out); print("sheet", out, sheet.size)
    Z = 8; strip = Image.new("RGB", (NC * (64 * Z + 12), 32 * Z + 28), (40, 40, 40)); d = ImageDraw.Draw(strip)
    for i, (lab, t) in enumerate(tiles):
        x = i * (64 * Z + 12)
        d.text((x + 4, y := 4), lab, fill=(255, 255, 0)); strip.paste(t.resize((64 * Z, 32 * Z), Image.NEAREST), (x, 24))
    out2 = ROOT / "build/m26_pattern_closeup3.png"; strip.save(out2); print("closeup", out2, strip.size)

if __name__ == "__main__":
    main()
