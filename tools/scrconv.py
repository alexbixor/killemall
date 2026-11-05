#!/usr/bin/env python3
"""scrconv.py - PNG <-> ZX Spectrum .scr (6912 bytes) converter with attribute-rule quantisation.

  scrconv.py png2scr <in.png> <out.scr> [--preview out.png] [--strict]
  scrconv.py scr2png <in.scr> <out.png> [--scale N]
  scrconv.py check   <in.scr>                 (size, flash bits, bright-black consistency, dark bottom rows)

Spectrum screen format: 6144 pixel bytes (address 16384 + ((y&0xC0)<<5) + ((y&7)<<8) + ((y&0x38)<<2) + (x>>3),
bit 7 = leftmost pixel, bit set = INK) followed by 768 attribute bytes (row-major 32x24):
bits 0-2 ink, 3-5 paper, bit 6 bright, bit 7 flash.  Palette (GRB index): 0 black 1 blue 2 red 3 magenta
4 green 5 cyan 6 yellow 7 white; bright variants at full intensity (bright black == black).

Quantisation: every pixel is mapped to the nearest of the 15 palette colours; per 8x8 cell the two most
frequent colours are kept (others are snapped to the nearer of the two) and the cell is reported as a
VIOLATION if it held more than two colours or mixed BRIGHT and non-BRIGHT non-black colours.
Deterministic: same PNG in -> same bytes out.  Exit code 1 with --strict if any cell violates.
"""
import sys, pathlib
from PIL import Image

NORM, BRI = 0xD7, 0xFF
def _rgb(i, level):
    return ((level if i & 2 else 0), (level if i & 4 else 0), (level if i & 1 else 0))  # GRB bits: b0 blue b1 red b2 green
# palette entries: (index 0..7, bright flag) -> RGB ; bright black is the same as black, so 15 colours
PALETTE = [((i, 0), _rgb(i, NORM)) for i in range(8)] + [((i, 1), _rgb(i, BRI)) for i in range(1, 8)]

def nearest(rgb):
    r, g, b = rgb[:3]
    best = None
    for key, (pr, pg, pb) in PALETTE:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if best is None or d < best[0]:
            best = (d, key)
    return best[1]

def pix_offset(x, y):
    return ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + (x >> 3)

def png2scr(png_path, scr_path, preview=None, strict=False, quiet=False):
    img = Image.open(png_path).convert('RGB')
    assert img.size == (256, 192), f"{png_path}: need 256x192, got {img.size}"
    px = img.load()
    # map every pixel once (cache by rgb value)
    cache = {}
    def key_of(x, y):
        c = px[x, y]
        k = cache.get(c)
        if k is None:
            k = cache[c] = nearest(c)
        return k
    scr = bytearray(6912)
    violations = []
    for cy in range(24):
        for cx in range(32):
            counts = {}
            for y in range(cy * 8, cy * 8 + 8):
                for x in range(cx * 8, cx * 8 + 8):
                    k = key_of(x, y)
                    counts[k] = counts.get(k, 0) + 1
            # deterministic order: most frequent first, ties by palette key
            order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            cols = [k for k, _ in order]
            if len(cols) > 2:
                violations.append((cx, cy, f"{len(cols)} colours {cols}"))
            two = cols[:2]
            # bright: any non-black bright colour -> bright cell; mixed bright/normal non-black = violation
            nonblack = [k for k in two if k[0] != 0]
            brights = {k[1] for k in nonblack}
            if len(brights) > 1:
                violations.append((cx, cy, f"mixed bright {two}"))
            bright = 1 if (nonblack and max(k[1] for k in nonblack)) else 0
            # paper = black if present else the most frequent colour; ink = the other
            if (0, 0) in two:
                paper = (0, 0); ink = two[1] if two[1:] and two[1] != paper else two[0]
            else:
                paper = two[0]; ink = two[1] if len(two) > 1 else two[0]
            if len(two) == 1:
                ink = paper
            attr = (ink[0] & 7) | ((paper[0] & 7) << 3) | (bright << 6)
            scr[6144 + cy * 32 + cx] = attr
            prgb = dict(PALETTE)[paper]; irgb = dict(PALETTE)[ink]
            for y in range(cy * 8, cy * 8 + 8):
                byte = 0
                for bit, x in enumerate(range(cx * 8, cx * 8 + 8)):
                    k = key_of(x, y)
                    if k == ink and k != paper:
                        on = 1
                    elif k == paper:
                        on = 0
                    else:  # third colour: snap to the nearer of ink/paper
                        c = px[x, y]
                        di = sum((a - b) ** 2 for a, b in zip(c, irgb)); dp = sum((a - b) ** 2 for a, b in zip(c, prgb))
                        on = 1 if di < dp else 0
                    byte |= on << (7 - bit)
                scr[pix_offset(x, y)] = byte
    pathlib.Path(scr_path).write_bytes(bytes(scr))
    if not quiet:
        print(f"{scr_path}: 6912 bytes, {len(violations)} violating cells")
        for cx, cy, why in violations[:40]:
            print(f"  cell ({cx},{cy}) px ({cx*8},{cy*8}): {why}")
    if preview:
        scr2png(scr_path, preview, quiet=quiet)
    if strict and violations:
        sys.exit(1)
    return violations

def decode(scr):
    assert len(scr) == 6912, f"scr must be 6912 bytes, got {len(scr)}"
    img = Image.new('RGB', (256, 192))
    px = img.load()
    pal = dict(PALETTE)
    for y in range(192):
        for cx in range(32):
            attr = scr[6144 + (y // 8) * 32 + cx]
            ink, paper, bright = attr & 7, (attr >> 3) & 7, (attr >> 6) & 1
            irgb = pal[(ink, bright if ink else 0)]; prgb = pal[(paper, bright if paper else 0)]
            byte = scr[pix_offset(cx * 8, y)]
            for bit in range(8):
                px[cx * 8 + bit, y] = irgb if byte & (0x80 >> bit) else prgb
    return img

def scr2png(scr_path, png_path, scale=1, quiet=False):
    img = decode(pathlib.Path(scr_path).read_bytes())
    if scale != 1:
        img = img.resize((256 * scale, 192 * scale), Image.NEAREST)
    img.save(png_path)
    if not quiet:
        print(f"{png_path}: {img.size[0]}x{img.size[1]} rendered from {scr_path}")

def check(scr_path, dark_rows=range(16, 24)):
    """Returns list of problems (empty = OK)."""
    scr = pathlib.Path(scr_path).read_bytes()
    problems = []
    if len(scr) != 6912:
        return [f"size {len(scr)} != 6912"]
    for cy in range(24):
        for cx in range(32):
            a = scr[6144 + cy * 32 + cx]
            if a & 0x80:
                problems.append(f"cell ({cx},{cy}) flash bit set")
            if cy in dark_rows:
                ink, paper = a & 7, (a >> 3) & 7
                pixels = [scr[pix_offset(cx * 8, y)] for y in range(cy * 8, cy * 8 + 8)]
                if paper != 0 or (ink != 0 and any(pixels)):
                    problems.append(f"cell ({cx},{cy}) not dark: attr {a:#04x} pixels {pixels}")
    return problems

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(2)
    cmd = a[0]
    if cmd == 'png2scr':
        prev = a[a.index('--preview') + 1] if '--preview' in a else None
        png2scr(a[1], a[2], preview=prev, strict='--strict' in a)
    elif cmd == 'scr2png':
        scale = int(a[a.index('--scale') + 1]) if '--scale' in a else 1
        scr2png(a[1], a[2], scale)
    elif cmd == 'check':
        p = check(a[1])
        print(f"{a[1]}: {'OK' if not p else str(len(p)) + ' problems'}")
        for s in p[:40]:
            print("  " + s)
        sys.exit(1 if p else 0)
    else:
        print(__doc__); sys.exit(2)

if __name__ == '__main__':
    main()
