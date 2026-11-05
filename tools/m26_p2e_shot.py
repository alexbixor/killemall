#!/usr/bin/env python3
"""m26_p2e_shot.py - stills from the REAL rebuilt 48K image (build/kea48.tap) with D5 ceiling + P2E colour: the same two views as
build/m26_d5_real.png (start room with a zombie 2.5 cells ahead; imp 1.5 cells with a wall close on the left) plus a third view
with health + ammo items and a corpse. Prints per view: render T-states, fps, count of BRIGHT wall cells, sprite-coloured cells
by ink, and the oracle diff (tools/p2e_oracle.py) - evidence, not a mock. Output build/m26_p2e_real.png (3x)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img
from test_game_sprites import set_player
from p2e_oracle import engine_expectation, diff, attrs

NAMES = {0: "black", 1: "blue", 2: "red", 3: "magenta", 4: "green", 5: "cyan", 6: "yellow", 7: "white"}
m = fresh()
shots = []
views = ((" start room, zombie 2.5 cells ahead", (3.5, 7.5, 0), [(2, 6.0, 7.5, 1)]),
         (" imp 1.5 cells, wall close on the left", (5.0, 2.6, 0), [(1, 6.5, 2.6, 1)]),
         (" health + ammo 1.5 cells, zombie corpse 1.2", (3.5, 7.5, 0), [(16, 5.0, 7.2, 0), (17, 5.0, 7.8, 0), (2, 4.7, 7.5, 3)]))
for name, (px, py, ang), things in views:
    set_player(m, px, py, ang); clear_things(m)
    for i, (t, x, y, st) in enumerate(things):
        set_thing(m, i, t, x, y); m.set_memory_block(SYM["things"] + 8 * i + 5, bytes([st]))
    T = call(m, "render", "hud_update")
    scr = bytes(m.memory[16384:16384 + 6912]); a = attrs(m); bad = diff(a, engine_expectation(m))
    tint = m.memory[SYM["at_tint"]]
    bright_wall = sum(1 for r in range(12) for c in range(24) if a[r][c] == (tint | 0x40))
    spr = {}
    for r in range(12):
        for c in range(24):
            v = a[r][c]
            if v & 0x40 and (v & 7) != tint: spr[NAMES[v & 7]] = spr.get(NAMES[v & 7], 0) + 1
    info = "render %d T = %.1f fps | near-wall BRIGHT cells %d | sprite cells %s | oracle diff %d" % (T, 3_500_000 / T, bright_wall, spr or "none", len(bad))
    print(name.strip(), "|", info)
    shots.append((name, info, scr_img(scr)))
S = 3
out = Image.new("RGB", (3 * 256 * S + 4 * 8, 192 * S + 44), (30, 30, 30)); d = ImageDraw.Draw(out)
for i, (name, info, im) in enumerate(shots):
    x = 8 + i * (256 * S + 8)
    d.text((x, 4), "REAL 48K BUILD (kea48.tap, D5 ceiling + P2E colour):" + name, fill=(255, 255, 0))
    d.text((x, 18), info, fill=(200, 200, 200))
    out.paste(im.resize((256 * S, 192 * S), Image.NEAREST), (x, 36))
p = ROOT / "build/m26_p2e_real.png"; out.save(p); print(p, out.size)
