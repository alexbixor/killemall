#!/usr/bin/env python3
"""check 2: per panel, histogram of colours in the middle third (where the zombie is) of build/m26_zombie_compare.png."""
import pathlib, collections
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
im = Image.open(ROOT / "build/m26_zombie_compare.png").convert("RGB")
S = 3; W, H = 194 * S, 98 * S
for i in range(3):
    y = 26 + i * (H + 30) + 14
    for j, x in enumerate((0, W + 12)):
        tile = im.crop((x + W // 3, y, x + 2 * W // 3, y + H))
        hist = collections.Counter(tile.getdata())
        print("row %d %s:" % (i, "LEFT " if j == 0 else "RIGHT"), hist.most_common(5))
