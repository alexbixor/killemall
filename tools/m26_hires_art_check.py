#!/usr/bin/env python3
"""m26_hires_art_check.py - validate a 32x48 hi-res sprite text file and render it big for a look:
exactly 48 rows of 32 chars from {#,o,.}; prints ink/black counts, bounding box, and saves build/m26_art_<name>.png (8x)
with the 16x24 original (EPX-upscaled, 8x) beside it. usage: m26_hires_art_check.py 04_zombie_walk_a"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m25e_hires_proto import load, epx
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parents[1]

def load_hires(name):
    rows = [l for l in (ROOT / "assets/sprites_hires" / (name + ".txt")).read_text().splitlines() if l and not l.startswith(";")]
    assert len(rows) == 48, "need 48 rows, got %d" % len(rows)
    for i, r in enumerate(rows):
        assert len(r) == 32, "row %d has %d chars" % (i, len(r))
        assert set(r) <= set("#o."), "row %d bad chars %r" % (i, set(r) - set("#o."))
    return [[{"#": 1, "o": 2}.get(ch, 0) for ch in r] for r in rows]

def to_img(px, zoom, bg=(40, 40, 40)):
    h, w = len(px), len(px[0]); im = Image.new("RGB", (w, h), bg); p = im.load()
    for y in range(h):
        for x in range(w):
            p[x, y] = (215, 215, 215) if px[y][x] == 1 else (0, 0, 0) if px[y][x] == 2 else bg
    return im.resize((w * zoom, h * zoom), Image.NEAREST)

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "04_zombie_walk_a"
    hi = load_hires(name); lo = epx(load(name))
    ink = sum(r.count(1) for r in hi); blk = sum(r.count(2) for r in hi)
    xs = [x for r in hi for x, v in enumerate(r) if v]; ys = [y for y, r in enumerate(hi) if any(r)]
    print("%s: 32x48 ok, ink %d black %d, bbox x %d..%d y %d..%d" % (name, ink, blk, min(xs), max(xs), min(ys), max(ys)))
    Z = 8
    a, b = to_img(lo, Z), to_img(hi, Z)
    sheet = Image.new("RGB", (a.size[0] + b.size[0] + 36, a.size[1] + 30), (60, 60, 60)); d = ImageDraw.Draw(sheet)
    d.text((4, 4), "16x24 original, EPX-upscaled", fill=(255, 255, 0))
    d.text((a.size[0] + 28, 4), "hand-drawn 32x48", fill=(255, 255, 0))
    sheet.paste(a, (4, 24)); sheet.paste(b, (a.size[0] + 28, 24))
    out = ROOT / ("build/m26_art_%s.png" % name); sheet.save(out); print("sheet", out, sheet.size)

if __name__ == "__main__":
    main()
