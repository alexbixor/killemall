#!/usr/bin/env python3
"""check 3: on the 1.0-cell close-up tiles, does the sprite (hand-drawn column) carry ink beyond the engine's own sprite box
(c0*3 .. c0*3+3*nc)? Prints, for the right-most tile vs the left tile, the leftmost/rightmost x of pixels that differ from the
plain background. Also checks there are no sprite pixels in rays where zbuf > hv (drawn through a wall)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, clear_things, set_thing
from m25e_hires_proto import load, epx
from m25e_sprite_mock2 import to_px
from m26_hires_art_check import load_hires
from m26_zombie_pictures import route2_pixels, s8
m = machine()
m.set_memory_block(SYM["level_data"], (ROOT / "src/48k/gen/level48.bin").read_bytes()); m.set_memory_block(SYM["level"], bytes([0]))
call(m, "cls", "hud_init", "init_game")
sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
art = to_px(load_hires("04_zombie_walk_a"), 32, 48)
for dist in (1.0, 1.5, 2.5):
    dx, dy = {0: (dist, 0), 64: (0, dist), 128: (-dist, 0), 192: (0, -dist)}.get(ang, (dist, 0))
    clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy); call(m, "render")
    vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6]); zbuf = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
    hv, c0, nc = vis[0], s8(vis[1]), vis[2]
    pix = route2_pixels(art, hv, c0, nc, zbuf)[0]
    xs = sorted({x for (x, y) in pix}); ys = sorted({y for (x, y) in pix})
    through = [(x, y) for (x, y) in pix if zbuf[x // 3] > hv]
    print("dist %.1f hv %d c0 %d nc %d: engine box x %d..%d, mock ink x %d..%d y %d..%d, pixels %d, through-wall %d" % (
        dist, hv, c0, nc, 3 * c0, 3 * c0 + 3 * nc - 1, xs[0], xs[-1], ys[0], ys[-1], len(pix), len(through)))
