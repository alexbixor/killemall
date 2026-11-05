#!/usr/bin/env python3
"""m23_edit_floor4.py - 1-px floor lines: line word 0xFFAA (even row keeps the checker's 0xAA, odd row solid 0xFF) instead
of 0xFFFF (2-px bars that read as a band where the far lines bunch near the horizon). Test + comments follow.
Also: m22_pad_test.py gets PAD_TAP (tape override) so the new launcher mapping is proven against the M2.3 tape."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
def sub(path, pairs):
    p = ROOT / path; t = p.read_text()
    for old, new in pairs:
        if new in t: continue
        if t.count(old) != 1: print("count", t.count(old), path, old[:60]); sys.exit(2)
        t = t.replace(old, new, 1)
    p.write_text(t); print("edited", path)
sub("tools/gen48.py", [
    ('          "        ld hl,65535"]                                  # M2.3: HL = floor line word for the patched pushes\n',
     '          "        ld hl,65450"]                                  # M2.3: HL = 0xFFAA floor line word (odd row solid, even row checker)\n'),
])
sub("src/common/floor.asm", [
    ("; PUSHes; fl_set patches those 24 push opcodes once per frame: D5 = push de (checker word 0x55AA, or 0 on DETAIL LOW),\n; E5 = push hl (line word 0xFFFF). Word w covers window rows 48+2w (E/L) and 49+2w (D/H); its top edge is at perpendicular\n",
     "; PUSHes; fl_set patches those 24 push opcodes once per frame: D5 = push de (checker word 0x55AA, or 0 on DETAIL LOW),\n; E5 = push hl (line word 0xFFAA: odd row solid, even row = checker -> a 1-px line). Word w covers window rows 48+2w (L/E)\n; and 49+2w (H/D); its top edge is at perpendicular\n"),
])
sub("tools/test_floor_lines.py", [
    (" (a) for every phase 0..15 the set of BUF floor words that are 0xFFFF (line) in an open byte column equals the oracle\n",
     " (a) for every phase 0..15 the set of BUF floor words that are (0xAA, 0xFF) (1-px line) in an open byte column equals the oracle\n"),
    ("CHK = (0xAA, 0x55)            # push de, DE = 0x55AA: E lands on the even (lower) row, D on the odd row\n",
     "CHK = (0xAA, 0x55)            # push de, DE = 0x55AA: E lands on the even (lower) row, D on the odd row\nLINE = (0xAA, 0xFF)           # push hl, HL = 0xFFAA: even row keeps the checker, odd row solid\n"),
    ("    return [w for w, (lo, hi) in enumerate(floor_words(m, bytecol)) if (lo, hi) == (0xFF, 0xFF) and w >= w0(m, bytecol)]\n",
     "    return [w for w, (lo, hi) in enumerate(floor_words(m, bytecol)) if (lo, hi) == LINE and w >= w0(m, bytecol)]\n"),
    ("        pure = sum(1 for lo, hi in ws if (lo, hi) in (CHK, (0xFF, 0xFF), (0, 0))) + w0(m, bc)\n",
     "        pure = sum(1 for lo, hi in ws if (lo, hi) in (CHK, LINE, (0, 0))) + w0(m, bc)\n"),
    ('check(all((lo, hi) == ((0xFF, 0xFF) if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still 0xFFFF")\n',
     'check(all((lo, hi) == (LINE if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still (AA,FF)")\n'),
])
sub("tools/m22_pad_test.py", [
    ('TAP = str(ROOT / "build/killemall48_m22.tap")\n', 'TAP = os.environ.get("PAD_TAP", str(ROOT / "build/killemall48_m23.tap"))   # M2.3 default (SPACE fires)\n'),
])
print("floor4 done")