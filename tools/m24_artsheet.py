#!/usr/bin/env python3
"""m24_artsheet.py - render sprite text art at 8x (ink = colour, black card) for a quick design review before building.
usage: m24_artsheet.py out.png ink_hex file1.txt [file2.txt ...]"""
import sys, pathlib
from PIL import Image, ImageDraw
out = sys.argv[1]; ink = tuple(int(sys.argv[2][i:i + 2], 16) for i in (0, 2, 4)); files = sys.argv[3:]
S = 8
arts = []
for f in files:
    rows = [r for r in pathlib.Path(f).read_text().splitlines() if r and not r.startswith(";")]
    arts.append((pathlib.Path(f).stem, rows))
W = sum(16 * S + 16 for _, _ in arts); H = 24 * S + 24
img = Image.new("RGB", (W, H), (40, 40, 40)); d = ImageDraw.Draw(img)
x = 8
for name, rows in arts:
    top = 24 * S - len(rows) * S   # bottom aligned like the engine
    d.rectangle((x, 8, x + 16 * S - 1, 8 + 24 * S - 1), fill=(0, 0, 0))
    for y, r in enumerate(rows):
        for c, ch in enumerate(r):
            if ch == "#": d.rectangle((x + c * S, 8 + top + y * S, x + c * S + S - 1, 8 + top + y * S + S - 1), fill=ink)
    # cell grid (8 px cells)
    for gy in range(0, 25, 8): d.line((x, 8 + gy * S, x + 16 * S - 1, 8 + gy * S), fill=(70, 70, 70))
    d.line((x + 8 * S, 8, x + 8 * S, 8 + 24 * S - 1), fill=(70, 70, 70))
    d.text((x, 8 + 24 * S + 4), name, fill=(200, 200, 200))
    x += 16 * S + 16
img.save(out); print("wrote", out, img.size)
