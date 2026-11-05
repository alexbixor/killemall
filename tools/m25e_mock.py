#!/usr/bin/env python3
"""m25e_mock.py - M2.5 step E mock (user 1 Nov 11:0xZ: "we are back with the colour clashing ... change the ground colour where the
sprite is or ... implement occlusion?"). Real renders from the Z80 core (level 1 start view, zombie ahead), then the attribute /
pixel treatment of the cells the sprite touches is simulated in Python (faithful: pixels are the engine's, only attribute bytes
and, for C, the cell clearing differ):
  A current  : ceiling rows level ink, floor rows FLOORINK; a sprite across the horizon is two-tone.
  B ground   : cells the sprite touches below the horizon take the ceiling (level) ink -> sprite one colour; the floor dots / wall
               texture inside those cells turn to the level ink too (the clash moves to the background).
  C occlusion: as B, and the background pixels inside those cells are erased (the sprite 'occludes' them) -> black boxes below.
  D own ink  : every cell the sprite touches takes a sprite ink (magenta) -> coloured box of background texture (M2.4 style).
Output: build/m25e_mock_strip.png (two scenes x four panels, crops of the window at 3x) + per-panel cell counts on stdout.
usage: .venv/bin/python tools/m25e_mock.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, set_thing, BUF0, BUFCOLS, BUFSTR
from run48 import PAL
from PIL import Image, ImageDraw

ATTR0, WIN_Y0, WIN_X0 = 22528, 8, 4          # window rows 0..95 = screen y 8..103, byte columns 4..27; horizon = y 56 = attr row 7

def scr_addr(y, bx): return 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + bx

def render_scene(dist):
    m = machine()
    data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
    m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
    call(m, "cls", "hud_init", "init_game")
    sx, sy = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1]
    clear_things(m); call(m, "render", "hud_update"); without = bytes(m.memory[16384:16384 + 6912])
    set_thing(m, 0, 2, sx + 0.5 + dist, sy + 0.5); call(m, "render", "hud_update"); with_ = bytes(m.memory[16384:16384 + 6912])
    # figure pixels: the sprite drawn alone over a zeroed BUF (test_one_ink technique) -> screen-space mask
    N = BUFCOLS * BUFSTR
    m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things")
    fig = bytearray(6912)
    for bc in range(BUFCOLS):
        for r in range(96):
            fig[scr_addr(WIN_Y0 + r, WIN_X0 + bc) - 16384] = m.memory[BUF0 + bc * BUFSTR + r]
    return without, with_, bytes(fig)

def touched_cells(without, with_, fig):
    cells = set()
    for y in range(WIN_Y0, WIN_Y0 + 96):
        for bx in range(WIN_X0, WIN_X0 + 24):
            a = scr_addr(y, bx) - 16384
            if without[a] != with_[a] or fig[a]: cells.add((y // 8, bx))
    return cells

def panel(scr, cells, mode, ceil_ink, spr_ink=3, fig=None):
    s = bytearray(scr)
    for (ar, bx) in cells:
        i = 6144 + ar * 32 + bx
        if mode == "B" and ar >= 7: s[i] = ceil_ink
        if mode == "C" and ar >= 7:
            s[i] = ceil_ink
            for y in range(ar * 8, ar * 8 + 8):
                a = scr_addr(y, bx) - 16384
                s[a] = scr[a] & fig[a]                       # keep only the figure's pixels: background occluded
        if mode == "D": s[i] = spr_ink
    return bytes(s)

def to_img(scr, x0, x1, y0, y1, scale=3):
    img = Image.new("RGB", (x1 - x0, y1 - y0)); px = img.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            bx, bit = x // 8, x % 8
            b = scr[scr_addr(y, bx) - 16384]; attr = scr[6144 + (y // 8) * 32 + bx]
            px[x - x0, y - y0] = PAL[attr & 7] if (b >> (7 - bit)) & 1 else PAL[(attr >> 3) & 7]
    return img.resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)

def main():
    rows = []
    for dist in (1.5, 2.5):
        without, with_, fig = render_scene(dist)
        cells = touched_cells(without, with_, fig)
        below = sorted(c for c in cells if c[0] >= 7); above = sorted(c for c in cells if c[0] < 7)
        print("zombie %.1f ahead: sprite touches %d cells (%d above the horizon, %d below); below = attr rows %s cols %s" % (
            dist, len(cells), len(above), len(below), sorted({r for r, _ in below}), sorted({c for _, c in below})))
        ceil_ink = with_[6144 + 1 * 32 + 4]
        pans = [("A current (two-tone)", with_), ("B ground takes level ink", panel(with_, cells, "B", ceil_ink)),
                ("C occlusion (black boxes)", panel(with_, cells, "C", ceil_ink, fig=fig)), ("D own ink (magenta box)", panel(with_, cells, "D", ceil_ink))]
        # crop around the sprite: its byte columns +-2, full window height
        cols = sorted({c for _, c in cells}); x0 = max(WIN_X0, min(cols) - 3) * 8; x1 = min(WIN_X0 + 24, max(cols) + 4) * 8
        rows.append([(lab, to_img(s, x0, x1, 0, 104)) for lab, s in pans])
    w = max(sum(im.size[0] for _, im in r) + 12 * 3 for r in rows); h = sum(r[0][1].size[1] + 22 for r in rows) + 10
    strip = Image.new("RGB", (w, h), (40, 40, 40)); d = ImageDraw.Draw(strip); y = 0
    for r in rows:
        x = 0
        for lab, im in r:
            d.text((x + 4, y + 4), lab, fill=(255, 255, 255)); strip.paste(im, (x, y + 22)); x += im.size[0] + 12
        y += r[0][1].size[1] + 32
    out = ROOT / "build/m25e_mock_strip.png"; strip.save(out); print("strip", out, strip.size)

if __name__ == "__main__":
    main()
