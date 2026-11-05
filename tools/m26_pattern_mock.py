#!/usr/bin/env python3
"""m26_pattern_mock.py - 2 Nov 'make the ceiling and floor patterns different': real engine frames (48K image, level 1 start
view) with the ceiling fill words (CLRBUF cl_ce / cl_cb / cl_cw) poked to candidate patterns; floor stays the shipped diamond
lattice (DE 0x0100 / BC 0x1000). Zero code cost: these are the two constant words apply_opts already patches.
Output build/m26_pattern_sheet2.png (6 panels, 3x) + 8x close-up strip of the ceiling."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img

# (label, DE' = even ceiling words, BC' = odd ceiling words). low byte -> even row (46-4k / 44-4k), high byte -> odd row.
CANDS = [("C0 TODAY: single dots in a square grid (ceiling now) - for reference", 0x0001, 0x0000),
         ("D1 DIAMONDS WITH LINES: lozenges 8 px wide x 4 rows, edges drawn as diagonal dotted lines, 18.8%", 0x2280, 0x2208),
         ("D2 small diamonds with lines: lozenges 4 px wide x 4 rows, solid diagonal edges, 37.5%", 0x5522, 0x5588),
         ("D3 zigzag: V-shaped chevrons 8 px wide x 4 rows (open diamonds), 25%", 0x8142, 0x2418),
         ("D4 diagonal hatching: one direction only, 12.5%", 0x0208, 0x2080),
         ("FLOOR for comparison: the shipped diamond DOTS (what the floor has), 6.25%", 0x0100, 0x1000)]

def main():
    m = fresh()
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    dx, dy = {0: (1.5, 0), 64: (0, 1.5), 128: (-1.5, 0), 192: (0, -1.5)}.get(ang, (1.5, 0))
    S = 3; W, H = 194 * S, 98 * S; gap = 12
    sheet = Image.new("RGB", (2 * W + 3 * gap, 44 + 3 * (H + 44)), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((gap, 6), "Ceiling = diamonds drawn with lines (your 11:0x request). Real 48K engine frames; the floor keeps its diamond dots in all six panels.", fill=(255, 255, 0))
    d.text((gap, 22), "Only two constant words in the clear routine change -> 0 bytes of code, 0 fps. The perspective distance lines stay as they are.", fill=(255, 255, 0))
    tiles = []
    for i, (lab, de, bc) in enumerate(CANDS):
        line = (de & 0xFF00) | 0x00FF                      # ceiling line word: even row solid, odd row keeps the pattern
        m.set_memory_block(SYM["cl_ce"] + 1, bytes([de & 255, de >> 8])); m.set_memory_block(SYM["cl_cb"] + 1, bytes([bc & 255, bc >> 8]))
        m.set_memory_block(SYM["cl_cw"] + 1, bytes([line & 255, line >> 8]))
        clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy); call(m, "render", "hud_update")
        img = scr_img(bytes(m.memory[16384:16384 + 6912]))
        crop = img.crop((31, 7, 225, 105)); tiles.append((lab, img.crop((100, 8, 160, 40))))
        x = gap + (i % 2) * (W + gap); y = 44 + (i // 2) * (H + 44)
        d.text((x, y), lab, fill=(255, 255, 255)); d.text((x, y + 14), "DE' %04X  BC' %04X" % (de, bc), fill=(200, 200, 200))
        sheet.paste(crop.resize((W, H), Image.NEAREST), (x, y + 30)); print(lab, "line %04X" % line)
    out = ROOT / "build/m26_pattern_sheet2.png"; sheet.save(out); print("sheet", out, sheet.size)
    Z = 8; strip = Image.new("RGB", (3 * (60 * Z + 12), 2 * (32 * Z + 24) + 4), (40, 40, 40)); d = ImageDraw.Draw(strip)
    for i, (lab, t) in enumerate(tiles):
        x = (i % 3) * (60 * Z + 12); y = (i // 3) * (32 * Z + 24)
        d.text((x + 4, y + 4), lab[:48], fill=(255, 255, 0)); strip.paste(t.resize((60 * Z, 32 * Z), Image.NEAREST), (x, y + 20))
    out2 = ROOT / "build/m26_pattern_closeup2.png"; strip.save(out2); print("closeup", out2, strip.size)

if __name__ == "__main__":
    main()
