#!/usr/bin/env python3
"""check: count ink pixels in the zombie box of each panel of build/m26_zombie_compare.png (3x sheet) and in the raw crops."""
import pathlib
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
im = Image.open(ROOT / "build/m26_zombie_compare.png").convert("RGB")
S = 3; W, H = 194 * S, 98 * S
for i in range(3):
    y = 26 + i * (H + 30) + 14
    for j, x in enumerate((0, W + 12)):
        tile = im.crop((x, y, x + W, y + H))
        px = tile.load()
        white = sum(1 for yy in range(H) for xx in range(W) if px[xx, yy] in ((255, 255, 255), (215, 215, 215)))
        red = sum(1 for yy in range(H) for xx in range(W) if px[xx, yy][0] > 150 and px[xx, yy][1] < 80)
        # lit pixels per 1/3 of the width
        thirds = [sum(1 for yy in range(H) for xx in range(k * W // 3, (k + 1) * W // 3) if px[xx, yy] in ((255, 255, 255), (215, 215, 215))) for k in range(3)]
        print("row %d %s: white %d red %d thirds %s" % (i, "LEFT " if j == 0 else "RIGHT", white, red, thirds))
