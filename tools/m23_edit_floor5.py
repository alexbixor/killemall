#!/usr/bin/env python3
"""m23_edit_floor5.py - half-cell line spacing: compare bit 3 upward (and 0xF8) instead of the cell nibble (and 0xF0) and
cut at 4 cells (FL_KMAX*16 unchanged = 64 -> 7 half-cell grid lines in range, 5-6 visible). Phase keeps 1/16 cell steps.
Oracle (m23_floor_model.lines) gets a G parameter; test_floor_lines uses G = 8."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
def sub(path, pairs):
    p = ROOT / path; t = p.read_text()
    for old, new in pairs:
        if new in t: continue
        if t.count(old) != 1: print("count", t.count(old), path, old[:60]); sys.exit(2)
        t = t.replace(old, new, 1)
    p.write_text(t); print("edited", path)
sub("src/common/floor.asm", [
    ("        xor b\n        and 0xF0\n        ld a,0xD5              ; push de = checker\n        jr z,fl_w              ; both edges in the same 1-cell interval: no grid line crosses this word\n",
     "        xor b\n        and 0xF8\n        ld a,0xD5              ; push de = checker\n        jr z,fl_w              ; both edges in the same half-cell interval: no grid line crosses this word\n"),
    ("; distance 24/w cells = FL_D4[w] in 1/16 cell. A line is drawn in word w when a grid distance k*16 (k < FL_KMAX) lies\n; between FL_D4[w+1] and FL_D4[w] after both are shifted by the phase p = fl_ph/16, so the lines are 1 cell apart, flow\n",
     "; distance 24/w cells = FL_D4[w] in 1/16 cell. A line is drawn in word w when a grid distance k*8 (half cells, nearer than\n; FL_KMAX cells) lies between FL_D4[w+1] and FL_D4[w] after both are shifted by the phase p = fl_ph/16, so the lines are 1/2\n; cell apart, flow\n"),
    ("FL_KMAX equ 4                  ; lines at 1, 2, 3 cells (the 4th and beyond compress into the horizon: left as checker)\n",
     "FL_KMAX equ 4                  ; half-cell lines nearer than 4 cells (beyond that they compress into the horizon: checker)\n"),
])
sub("tools/m23_floor_model.py", [
    ("def lines(p, kmax=KMAX):\n    out = []\n    for w in range(24):\n        hi_bot = ((D4[w + 1] + p) & 0xFF) & 0xF0\n        hi_top = ((D4[w] + p) & 0xFF) & 0xF0\n        if hi_bot < kmax * 16 and hi_top != hi_bot:\n",
     "def lines(p, kmax=KMAX, g=8):\n    out = []\n    for w in range(24):\n        hi_bot = ((D4[w + 1] + p) & 0xFF) & ~(g - 1)\n        hi_top = ((D4[w] + p) & 0xFF) & ~(g - 1)\n        if hi_bot < kmax * 16 and hi_top != hi_bot:\n"),
])
print("floor5 done")