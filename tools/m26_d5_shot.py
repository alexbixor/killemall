#!/usr/bin/env python3
"""m26_d5_shot.py - stills from the REAL rebuilt 48K image (build/kea48.tap) with the D5 ceiling: start view + zombie, near wall.
Output build/m26_d5_real.png (two frames side by side, 3x)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img
from test_game_sprites import set_player

m = fresh()
shots = []
for name, (px, py, ang), things in (("start room, zombie 2.5 cells ahead", (3.5, 7.5, 0), [(2, 6.0, 7.5)]),
                                    ("imp 1.5 cells, wall close on the left", (5.0, 2.6, 0), [(1, 6.5, 2.6)])):
    set_player(m, px, py, ang); clear_things(m)
    for i, (t, x, y) in enumerate(things): set_thing(m, i, t, x, y)
    T = call(m, "render")
    shots.append((name, T, scr_img(bytes(m.memory[16384:16384 + 6912]))))
S = 3
out = Image.new("RGB", (2 * 256 * S + 3 * 8, 192 * S + 40), (30, 30, 30)); d = ImageDraw.Draw(out)
for i, (name, T, im) in enumerate(shots):
    x = 8 + i * (256 * S + 8)
    d.text((x, 6), "REAL 48K BUILD (kea48.tap, D5 ceiling): %s - render %d T = %.1f fps" % (name, T, 3_500_000 / T), fill=(255, 255, 0))
    out.paste(im.resize((256 * S, 192 * S), Image.NEAREST), (x, 24))
p = ROOT / "build/m26_d5_real.png"; out.save(p); print(p, out.size, [(n, T) for n, T, _ in shots])
