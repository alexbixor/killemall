#!/usr/bin/env python3
"""m25e_hires_budget.py - byte budget of the hi-res enemy sprite options, all 8 enemy frames (+ 6 items that must share the box):
  16x24 current | 16x48 'vertical EPX' (EPX 2x2, column pairs merged: take the bevel if either half has one) | 32x48 EPX | 32x48 EPX
  with identical column run lists shared (offset table points at one copy).
Also prints the low-block free space from build/kea48.sym (level_data + 1081 must stay below 0x8000).
usage: .venv/bin/python tools/m25e_hires_budget.py"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m25e_hires_proto import load, epx, ROOT
ENEMIES = ["00_imp_walk_a", "01_imp_walk_b", "02_imp_attack", "03_imp_dead", "04_zombie_walk_a", "05_zombie_walk_b", "06_zombie_attack", "07_zombie_dead"]
ITEMS = ["08_health", "09_ammo", "10_red_key", "11_blue_key", "12_barrel", "13_lamp"]

def merge16(e, src):
    """32x48 EPX -> 16x48: output(x, y) = the half that differs from the source pixel (a bevel), else the source pixel."""
    h2 = len(e); out = []
    for y in range(h2):
        row = []
        for x in range(16):
            P = src[y // 2][x]; a, b = e[y][2 * x], e[y][2 * x + 1]
            row.append(a if a != P else b)
        out.append(row)
    return out

def nearest_v2(px): return [r[:] for r in px for _ in (0, 1)]

def col_runs(px, box_h, x, halo):
    h, w = len(px), len(px[0]); top = box_h - h
    def ink(xx, yy): return 0 <= xx < w and top <= yy < box_h and px[yy - top][xx] == 1
    codes = []
    for y in range(box_h):
        v = px[y - top][x] if top <= y < box_h else 0
        if v == 1: codes.append(3)
        elif v == 2: codes.append(1)
        elif halo and any(ink(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy): codes.append(1)
        else: codes.append(0)
    out, y = [], 0
    while y < box_h:
        e = y
        while e < box_h and codes[e] == codes[y]: e += 1
        out.append((e, codes[y])); y = e
    return tuple(out)

def size(px, box_h, halo, share):
    w = len(px[0]); lists = [col_runs(px, box_h, x, halo) for x in range(w)]
    uniq = set(lists) if share else lists
    return 2 * w + sum(len(l) + 1 for l in uniq), len(set(lists))

def main():
    tot = {}
    for name in ENEMIES + ITEMS:
        src = load(name); e = epx(src); halo = name in ENEMIES
        opts = [("16x24", src, 24, False), ("16x48 merge", merge16(e, src), 48, False), ("16x48 merge shared", merge16(e, src), 48, True),
                ("32x48 EPX", e, 48, False), ("32x48 EPX shared", e, 48, True)]
        if name in ITEMS:
            opts = [("16x24", src, 24, False), ("16x48 nearest", nearest_v2(src), 48, False), ("16x48 nearest shared", nearest_v2(src), 48, True),
                    ("32x48 nearest", [[v for v in r for _ in (0, 1)] for r in nearest_v2(src)], 48, False), ("32x48 nearest shared", [[v for v in r for _ in (0, 1)] for r in nearest_v2(src)], 48, True)]
        line = "%-17s" % name
        for i, (lab, px, bh, share) in enumerate(opts):
            b, u = size(px, bh, halo, share); tot[i] = tot.get(i, 0) + b
            line += " | %s %4d B (%2d uniq cols)" % (lab, b, u)
        print(line)
    print("TOTALS (enemies+items): " + " | ".join("opt%d %5d B" % (i, b) for i, b in sorted(tot.items())))
    syms = {}
    for l in open(ROOT / "build/kea48.sym"):
        m = re.match(r"^(\w+)\s+EQU\s+([0-9A-F]+)H", l.strip(), re.I)
        if m: syms[m.group(1)] = int(m.group(2), 16)
    cur = syms["spr_14"] - syms["spr_0"]
    print("current sprite data ids 0..13: %d B; low block free below 0x8000: %d B (level_data 0x%04X + 1081)" % (cur, 0x8000 - (syms["level_data"] + 1081), syms["level_data"]))
    for i, b in sorted(tot.items()):
        print("  opt%d: delta %+5d B -> free after %+5d B" % (i, b - cur, 0x8000 - (syms["level_data"] + 1081) - (b - cur)))

if __name__ == "__main__":
    main()
