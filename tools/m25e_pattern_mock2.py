#!/usr/bin/env python3
"""m25e_pattern_mock2.py - step E floor/ceiling candidates with a 4-ROW period (two fill words alternating per PUSH word: even
words push DE, odd words push BC -> rows repeat every 4). Faithful composition: the open floor/ceiling pixels are found by XOR of two
real engine renders (fill 0x0000 vs 0xFFFF, lines off), the pattern is painted only there, then the DETAIL-LOW render (black fill,
distance lines on, zombie 1.5 cells ahead) is used as the base. Window 192x96 at 3x.
Pattern spec per candidate: floor (word_even_w, word_odd_w), ceiling (word_even_w, word_odd_w); word = (odd row << 8) | even row,
floor word w covers rows 48+2w / 49+2w, ceiling word w covers rows 46-2w / 47-2w (mirror).
usage: .venv/bin/python tools/m25e_pattern_mock2.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, set_thing, BUF0, BUFCOLS, BUFSTR
from run48 import PAL
from PIL import Image, ImageDraw

def scr_addr(y, bx): return 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + bx

def render(fw, cw, lines=True, dist=1.5):
    m = machine()
    data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
    m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
    call(m, "cls", "hud_init", "init_game")
    m.set_memory_block(SYM["cl_de"] + 1, bytes([fw & 255, fw >> 8]))
    m.set_memory_block(SYM["cl_ce"] + 1, bytes([cw & 255, cw >> 8]))
    m.set_memory_block(SYM["cl_cw"] + 1, bytes([0x00, 0xFF]))           # ceiling line word (FF even row solid, 00 odd row)
    m.set_memory_block(SYM["cl_col"] + 1, bytes([0x00, 0xFF]))          # floor line word (00 even row, FF odd row solid)
    if not lines: m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))
    sx, sy = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1]
    clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dist, sy + 0.5)
    call(m, "render", "hud_update")
    return bytearray(m.memory[16384:16384 + 6912])

def compose(base, open_mask, floor_words, ceil_words):
    s = bytearray(base)
    for r in range(96):
        y = 8 + r
        if r >= 48:
            w = (r - 48) // 2; word = floor_words[w & 1]; byte = (word >> 8) if (r & 1) else (word & 255)
        else:
            w = (47 - r) // 2; word = ceil_words[w & 1]; byte = (word >> 8) if ((47 - r) & 1) else (word & 255)
            # ceiling word w: rows 46-2w (even row of the word = low byte) and 47-2w (odd = high byte)
            byte = (word & 255) if r == 46 - 2 * w else (word >> 8)
        for bx in range(4, 28):
            a = scr_addr(y, bx) - 16384
            s[a] |= byte & open_mask[a]
    return s

def to_img(scr, scale=3):
    img = Image.new("RGB", (192, 96)); px = img.load()
    for y in range(8, 104):
        for x in range(32, 224):
            bx, bit = x // 8, x % 8
            b = scr[scr_addr(y, bx) - 16384]; attr = scr[6144 + (y // 8) * 32 + bx]
            px[x - 32, y - 8] = PAL[attr & 7] if (b >> (7 - bit)) & 1 else PAL[(attr >> 3) & 7]
    return img.resize((192 * scale, 96 * scale), Image.NEAREST)

def dens(words): return sum(bin(w).count("1") for w in words) * 100 / 32

CANDS = [
    ("A current (2-row): floor 55AA checker 50%, ceiling 1144 dots 25%", (0x55AA, 0x55AA), (0x1144, 0x1144)),
    ("S1 squares 4x4: floor 0011/0000 (x3,x7 every 4th row), ceiling 0001/0000", (0x0011, 0x0000), (0x0001, 0x0000)),
    ("D1 diamonds 8x4: floor 0001/0010 (x7, then x3 two rows down), ceiling 0010/0001 sparser? same", (0x0001, 0x0010), (0x0001, 0x0010)),
    ("D2 diamonds floor 0001/0010, ceiling squares 0001/0000 (half density)", (0x0001, 0x0010), (0x0001, 0x0000)),
    ("D3 diamonds 4x4 denser: floor 0011/0044, ceiling 0001/0010", (0x0011, 0x0044), (0x0001, 0x0010)),
    ("S2 squares 8x4: floor 0001/0000, ceiling 0010/0000", (0x0001, 0x0000), (0x0010, 0x0000)),
]

def main():
    black = render(0x0000, 0x0000, lines=False); white = render(0xFFFF, 0xFFFF, lines=False)
    open_mask = bytes(a ^ b for a, b in zip(black, white))
    base = render(0x0000, 0x0000, lines=True)
    n_open = sum(bin(v).count("1") for v in open_mask[:6144])
    print("open floor+ceiling pixels in the start view: %d of %d window pixels" % (n_open, 192 * 96))
    panels = []
    for lab, fwords, cwords in CANDS:
        scr = compose(base, open_mask, fwords, cwords)
        print("%-88s floor %4.1f%%  ceiling %4.1f%%" % (lab, dens(fwords), dens(cwords)))
        panels.append((lab, to_img(scr)))
    w = panels[0][1].size[0]; h = sum(im.size[1] + 24 for _, im in panels) + 8
    strip = Image.new("RGB", (w, h), (40, 40, 40)); d = ImageDraw.Draw(strip); y = 0
    for lab, im in panels:
        d.text((4, y + 4), lab[:92], fill=(255, 255, 255)); strip.paste(im, (0, y + 20)); y += im.size[1] + 24
    out = ROOT / "build/m25e_pattern_mock2.png"; strip.save(out); print("strip", out, strip.size)

if __name__ == "__main__":
    main()
