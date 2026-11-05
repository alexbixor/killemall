#!/usr/bin/env python3
"""m25e_pattern_mock.py - step E (user 1 Nov 11:3xZ: "make the ceiling and the floor less dense, i.e. a square/diamond pattern"):
candidate CLRBUF fill words, rendered as they would appear on the Spectrum (window 192 x 96 at 3x) with the real engine scene behind.
The fill is two bytes per byte column (PUSH of a word: even row = low byte, odd row = high byte), so a pattern repeats every 2 rows.
Candidates (floor word / ceiling word), 'density' = lit pixels per 16:
  A current  : floor 0x55AA checker (8/16 = 50 %), ceiling 0x1144 dots (4/16 = 25 %)
  B squares  : floor 0x1111 (same column both rows -> 2-px tall squares every 4 px, 4/16 = 25 %), ceiling 0x0101 (1/16 = 6 %) ...
  C diamonds : floor 0x4411 (offset dots every 4 px = diamond lattice, 25 %), ceiling 0x1001 (2/16 = 12 %)
  D sparse diamonds: floor 0x1001 / 0x0110 alternating per column -> needs a per-column phase (not possible with one PUSH word) -> skipped
  E 8-px squares: floor 0x0101 (1 px every 8, 6 %), ceiling 0x1001 (12 %)
Output: build/m25e_pattern_mock.png (strip of panels) + density numbers.
usage: .venv/bin/python tools/m25e_pattern_mock.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, set_thing, BUF0, BUFCOLS, BUFSTR
from run48 import PAL
from PIL import Image, ImageDraw

def scr_addr(y, bx): return 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + bx

def render(floor_word, ceil_word, line_f=0xFFAA, line_c=0x11FF, dist=1.5):
    m = machine()
    data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
    m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
    call(m, "cls", "hud_init", "init_game")
    # poke the fill words directly into CLRBUF (apply_opts would overwrite them; we call render only)
    m.set_memory_block(SYM["cl_de"] + 1, bytes([floor_word & 255, floor_word >> 8]))
    m.set_memory_block(SYM["cl_ce"] + 1, bytes([ceil_word & 255, ceil_word >> 8]))
    m.set_memory_block(SYM["cl_cw"] + 1, bytes([line_c & 255, line_c >> 8]))
    m.set_memory_block(SYM["cl_col"] + 1, bytes([line_f & 255, line_f >> 8]))
    sx, sy = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1]
    clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dist, sy + 0.5)
    call(m, "render", "hud_update")
    return bytes(m.memory[16384:16384 + 6912])

def to_img(scr, scale=3):
    img = Image.new("RGB", (192, 96)); px = img.load()
    for y in range(8, 104):
        for x in range(32, 224):
            bx, bit = x // 8, x % 8
            b = scr[scr_addr(y, bx) - 16384]; attr = scr[6144 + (y // 8) * 32 + bx]
            px[x - 32, y - 8] = PAL[attr & 7] if (b >> (7 - bit)) & 1 else PAL[(attr >> 3) & 7]
    return img.resize((192 * scale, 96 * scale), Image.NEAREST)

def density(word): return bin(word & 255).count("1") + bin(word >> 8).count("1")

CANDS = [("A current: floor 55AA checker, ceiling 1144 dots", 0x55AA, 0x1144, 0xFFAA, 0x11FF),
         ("B squares: floor 1111 (2x1 squares /4px), ceiling 0101", 0x1111, 0x0101, 0xFF11, 0x01FF),
         ("C diamonds: floor 4411 (offset dots /4px), ceiling 1001", 0x4411, 0x1001, 0xFF11, 0x01FF),
         ("E 8px: floor 0101, ceiling 1001", 0x0101, 0x1001, 0xFF01, 0x01FF),
         ("F diamonds 8px: floor 1001 both? -> 1001/0110 impossible; floor 1001, ceiling 0000", 0x1001, 0x0000, 0xFF01, 0x00FF)]

def main():
    panels = []
    for lab, fw, cw, lf, lc in CANDS:
        scr = render(fw, cw, lf, lc)
        print("%-70s floor %2d/16 = %3d%%  ceiling %2d/16 = %3d%%" % (lab, density(fw), density(fw) * 100 // 16, density(cw), density(cw) * 100 // 16))
        panels.append((lab, to_img(scr)))
    w = panels[0][1].size[0]; h = sum(im.size[1] + 24 for _, im in panels) + 8
    strip = Image.new("RGB", (w, h), (40, 40, 40)); d = ImageDraw.Draw(strip); y = 0
    for lab, im in panels:
        d.text((4, y + 4), lab, fill=(255, 255, 255)); strip.paste(im, (0, y + 20)); y += im.size[1] + 24
    out = ROOT / "build/m25e_pattern_mock.png"; strip.save(out); print("strip", out, strip.size)

if __name__ == "__main__":
    main()
