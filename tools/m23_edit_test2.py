#!/usr/bin/env python3
"""m23_edit_test2.py - test_floor_lines (b): with half-cell lines a new line can enter from the bottom edge while walking
back (max word is not a stable tracker). Track lines by nearest-neighbour matching between the two frames (|delta| <= 3
words): forward = every matched line moves down (delta >= 0, some > 0), backward = every matched line moves up."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
p = ROOT / "tools/test_floor_lines.py"; t = p.read_text()
pairs = [
("def line_words(m, bytecol):\n",
 "def matched_deltas(l0, l1):\n    \"\"\"word delta of every line in l1 matched to its nearest line in l0 (new entrants > 3 words away are dropped)\"\"\"\n"
 "    out = []\n    for w in l1:\n        d = min(((abs(w - a), w - a) for a in l0), default=(99, 0))\n        if d[0] <= 3: out.append(d[1])\n    return out\n"
 "def line_words(m, bytecol):\n"),
("call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); moved = max(l) - max(l0)\n"
 "check(moved is not None and moved > 0, \"(b) forward: nearest line moves down the screen (word delta %s)\" % moved)\n",
 "call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); dd = matched_deltas(l0, l)\n"
 "check(dd and all(d >= 0 for d in dd) and any(d > 0 for d in dd), \"(b) forward: lines move down the screen (word deltas %s, %s -> %s)\" % (dd, l0, l))\n"),
("call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); moved = max(l) - max(l0)\n"
 "check(moved < 0,",
 "call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); dd = matched_deltas(l0, l)\n"
 "check(dd and all(d <= 0 for d in dd) and any(d < 0 for d in dd),"),
(" \"(b) backward: nearest line moves up the screen (word delta %s)\" % moved)\n",
 " \"(b) backward: lines move up the screen (word deltas %s, %s -> %s)\" % (dd, l0, l))\n"),
]
for old, new in pairs:
    if new in t: continue
    if t.count(old) != 1: print("count", t.count(old), old[:60]); sys.exit(2)
    t = t.replace(old, new, 1)
p.write_text(t); print("test2 patched")