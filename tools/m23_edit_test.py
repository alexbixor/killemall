#!/usr/bin/env python3
"""m23_edit_test.py - fix test_floor_lines.py: the far wall ahead covers the top floor words of a byte column (solid 0xFF
rows look like a line word) -> compare only words below the wall bottom, w0 = ceil(max zbuf of the 4 rays / 4)."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
p = ROOT / "tools/test_floor_lines.py"; t = p.read_text()
pairs = [
('def line_words(m, bytecol):\n    return [w for w, (lo, hi) in enumerate(floor_words(m, bytecol)) if (lo, hi) == (0xFF, 0xFF)]\n',
 'def w0(m, bytecol):\n    """first floor word below the wall of this byte column: wall rows below the horizon = h/2 (h = max zbuf of its 4 rays)"""\n'
 '    h = max(m.memory[SYM["zbuf"] + 4 * bytecol + i] for i in range(4))\n    return (min(h, 96) + 3) // 4\n'
 'def line_words(m, bytecol):\n    return [w for w, (lo, hi) in enumerate(floor_words(m, bytecol)) if (lo, hi) == (0xFF, 0xFF) and w >= w0(m, bytecol)]\n'
 'def flo(ws, m, bytecol):\n    return [(w, lh) for w, lh in enumerate(ws) if w >= w0(m, bytecol)]\n'),
('        ws = floor_words(m, bc)\n        pure = sum(1 for lo, hi in ws if (lo, hi) in ((0x55, 0xAA), (0xAA, 0x55), (0xFF, 0xFF), (0, 0)))\n',
 '        ws = floor_words(m, bc)[w0(m, bc):]\n        pure = sum(1 for lo, hi in ws if (lo, hi) in ((0x55, 0xAA), (0xAA, 0x55), (0xFF, 0xFF), (0, 0))) + w0(m, bc)\n'),
('    got = line_words(m, bc); want = oracle_lines(p, 4)\n    ws = floor_words(m, bc)\n'
 '    others_ok = all((lo, hi) == (0x55, 0xAA) for w, (lo, hi) in enumerate(ws) if w not in want) if pure == 24 else None\n',
 '    got = line_words(m, bc); want = [w for w in oracle_lines(p, 4) if w >= w0(m, bc)]\n'
 '    others_ok = all((lo, hi) == (0x55, 0xAA) for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None\n'),
('check(bad == 0, "(a) line words == oracle for all 16 phases, checker elsewhere (col pure words %d/24)" % pure)\n',
 'check(bad == 0, "(a) line words == oracle for all 16 phases, checker elsewhere (col %d, wall words %d, pure %d/24)" % (bc, w0(m, bc), pure))\n'),
('check(m.memory[SYM["fl_ph"]] == 0 and line_words(m, bc) == l0, "(b) turning: fl_ph stays 0, lines unchanged")\n',
 'lt = line_words(m, bc); wt = max(w0(m, bc), 3)\n'
 'check(m.memory[SYM["fl_ph"]] == 0 and [w for w in lt if w >= wt] == [w for w in l0 if w >= wt], "(b) turning: fl_ph stays 0, floor lines unchanged (%s vs %s)" % (lt, l0))\n'),
('ws = floor_words(m, bc); want = oracle_lines(0, 4)\n'
 'check(all((lo, hi) == ((0xFF, 0xFF) if w in want else (0, 0)) for w, (lo, hi) in enumerate(ws)), "(d) DETAIL LOW: plain 0x0000 floor, lines still 0xFFFF")\n',
 'ws = flo(floor_words(m, bc), m, bc); want = oracle_lines(0, 4)\n'
 'check(all((lo, hi) == ((0xFF, 0xFF) if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still 0xFFFF")\n'),
('check(line_words(m, bc) == [] and all((lo, hi) == (0x55, 0xAA) for lo, hi in floor_words(m, bc)), "(f) fl_k+1 = 0: no lines, pure checker")\n',
 'check(line_words(m, bc) == [] and all((lo, hi) == (0x55, 0xAA) for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure checker")\n'),
]
for old, new in pairs:
    if new in t: continue
    if t.count(old) != 1: print("count", t.count(old), old[:60]); sys.exit(2)
    t = t.replace(old, new, 1)
p.write_text(t); print("test patched")