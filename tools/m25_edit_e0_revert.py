#!/usr/bin/env python3
"""m25_edit_e0_revert.py - M2.5 step E part 0 (user 1 Nov 11:3xZ: "ok, go back to one colour"): undo step D (two-tone window).
Restores the step-C versions of src/48k/kea48.asm, tools/make128.py, tools/test_tint.py from build/pre_m25d/src_pre_m25d.tgz
(their only differences to the current files are the step-D edits, verified by diff before copying) and reverts the test_128.py
anchor census 6/9 -> 5/8 (the A6 FLOORINK anchor is gone). Idempotent: a second run reports "already reverted".
usage: .venv/bin/python tools/m25_edit_e0_revert.py"""
import pathlib, subprocess, sys, tarfile, io, difflib
ROOT = pathlib.Path(__file__).resolve().parent.parent
TGZ = ROOT / "build/pre_m25d/src_pre_m25d.tgz"
FILES = ["src/48k/kea48.asm", "tools/make128.py", "tools/test_tint.py"]
STEP_D_MARKERS = {"src/48k/kea48.asm": "FLOORINK", "tools/make128.py": "A6 floor ink", "tools/test_tint.py": "FLOORINK"}

def main():
    tf = tarfile.open(TGZ)
    for rel in FILES:
        cur = (ROOT / rel).read_text()
        old = tf.extractfile(rel).read().decode()
        if STEP_D_MARKERS[rel] not in cur:
            print("%s: already reverted (no %r)" % (rel, STEP_D_MARKERS[rel])); continue
        changed = [l for l in difflib.unified_diff(old.splitlines(), cur.splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        # every changed line must belong to step D (mentions FLOORINK / M2.5D / A6 / floor ink / ceiling ink / wt_rows / 6 rows), else refuse
        keys = ("FLOORINK", "M2.5D", "A6", "floor", "ceil", "wt_rows", "ld c,6", "ld c,12", "import sys", "want_f", "fink", "FAIL: FLOORINK", "bad2", "bad =", "ink %d",
                "ink", "TINTTAB", "window", "cells", "if m:", "missing = [a for a in", "win(m)")        # step-D comment rewrite of win_tint / TINTTAB + make128 A6 block + test_tint win() split (diffs read by hand 1 Nov: 17 / 6 / 18 lines)
        foreign = [l for l in changed if not any(k in l for k in keys)]
        if foreign:
            print("%s: REFUSING - lines not from step D:\n  " % rel + "\n  ".join(foreign[:10])); sys.exit(1)
        (ROOT / rel).write_text(old)
        print("%s: restored step-C version (%d step-D diff lines undone)" % (rel, len(changed)))
    t = ROOT / "tools/test_128.py"
    s = t.read_text()
    pairs = [
        ('check(len(removed) == 6 and all(any(re.match(p, l) for p in exp) for l in removed), "make128: removed lines = 6 anchored originals %r" % removed)\n',
         'check(len(removed) == 5 and all(any(re.match(p, l) for p in exp) for l in removed), "make128: removed lines = 5 anchored originals %r" % removed)\n'),
        ('check(all("T4 128K anchor" in l or l.strip() in ("di", "push hl") for l in added) and len(added) == 9, "make128: %d added lines all anchor-marked" % len(added))\n',
         'check(all("T4 128K anchor" in l or l.strip() in ("di", "push hl") for l in added) and len(added) == 8, "make128: %d added lines all anchor-marked" % len(added))\n'),
        (',\n       r"^FLOORINK\\s+equ\\s+4\\b"]          # M2.5D anchor A6: the 128K floor ink line\n', ']\n'),
    ]
    n = 0
    for old, new in pairs:
        if old in s: s = s.replace(old, new); n += 1
    if n: t.write_text(s); print("tools/test_128.py: anchor census back to 5 removed / 8 added (%d edits)" % n)
    else: print("tools/test_128.py: already reverted")
    for rel in FILES + ["tools/test_128.py"]:
        assert "FLOORINK" not in (ROOT / rel).read_text(), rel
    print("OK: no FLOORINK left in", ", ".join(FILES + ["tools/test_128.py"]))

if __name__ == "__main__":
    main()
