#!/usr/bin/env python3
"""m25e_mock_e.py - panel E for the clash discussion (user 1 Nov 11:2xZ: "use dots to render the image?"): the Chase H.Q. / TTT way =
ONE ink in the whole window, floor and ceiling told apart by dot pattern only (ceiling sparse dots + lines, floor checker + lines), so a
sprite is always one colour and never boxed. Same engine renders as m25e_mock.py; only the 12 x 24 attribute bytes change."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m25e_mock import render_scene, touched_cells, to_img, ROOT, WIN_X0
from PIL import Image, ImageDraw
rows = []
for dist in (1.5, 2.5):
    without, with_, fig = render_scene(dist)
    cells = touched_cells(without, with_, fig)
    a = bytearray(with_); d = bytearray(with_)
    for ar in range(1, 13):
        for bx in range(4, 28):
            a[6144 + ar * 32 + bx] = 7                      # E: one ink (level tint), dots do the floor/ceiling job
    cols = sorted({c for _, c in cells}); x0 = max(WIN_X0, min(cols) - 3) * 8; x1 = min(WIN_X0 + 24, max(cols) + 4) * 8
    rows.append([("A current (two-tone)", to_img(with_, x0, x1, 0, 104)), ("E one ink, dots separate floor/ceiling", to_img(bytes(a), x0, x1, 0, 104))])
    lit_c = sum(bin(with_[i]).count("1") for i in range(0, 6144) if False)
w = max(sum(im.size[0] for _, im in r) + 12 for r in rows); h = sum(r[0][1].size[1] + 32 for r in rows)
strip = Image.new("RGB", (w, h), (40, 40, 40)); dr = ImageDraw.Draw(strip); y = 0
for r in rows:
    x = 0
    for lab, im in r:
        dr.text((x + 4, y + 4), lab, fill=(255, 255, 255)); strip.paste(im, (x, y + 22)); x += im.size[0] + 12
    y += r[0][1].size[1] + 32
out = ROOT / "build/m25e_mock_e.png"; strip.save(out); print("strip", out, strip.size)
