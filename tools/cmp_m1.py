#!/usr/bin/env python3
"""cmp_m1.py - render the same viewpoints with the M1 tap (rebuilt from build/kea48_m1_backup.asm + build/gen_m1_backup)
and the current build/kea48.tap on the Python Z80 core and report attribute cells / window pixels that differ.
usage: cmp_m1.py "px py ang" ...   (writes nothing under build/ except restoring kea48.tap/.sym as they were)"""
import subprocess, pathlib, shutil, sys, filecmp
ROOT = pathlib.Path("/home/ubuntu/work/killemall"); PY = str(ROOT / ".venv/bin/python")
views = sys.argv[1:] or ["3.5 7.5 0", "7.3 7.5 0", "25.5 3.5 40", "1.3 1.3 32"]

def pix(scr, x, y):
    base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2); return (scr[base + (x >> 3)] >> (7 - (x & 7))) & 1

def dumps(tag):
    out = {}
    for v in views:
        subprocess.run([PY, str(ROOT / "tools/test48.py")] + v.split(), check=True, stdout=subprocess.DEVNULL)
        out[v] = (ROOT / "build/test48_scr.bin").read_bytes()
    return out

shutil.copy(ROOT / "build/kea48.tap", "/tmp/kea48_cur.tap"); shutil.copy(ROOT / "build/kea48.sym", "/tmp/kea48_cur.sym")
try:
    m1b = pathlib.Path("/tmp/m1b"); shutil.rmtree(m1b, ignore_errors=True); m1b.mkdir()
    shutil.copytree(ROOT / "build/gen_m1_backup", m1b / "gen"); shutil.copy(ROOT / "build/kea48_m1_backup.asm", m1b / "kea48.asm")
    subprocess.run(["pasmo", "--tapbas", "kea48.asm", "m1.tap", "m1.sym"], cwd=m1b, check=True)
    print("M1 rebuild identical to killemall48_m1.tap:", filecmp.cmp(m1b / "m1.tap", ROOT / "build/killemall48_m1.tap", shallow=False))
    shutil.copy(m1b / "m1.tap", ROOT / "build/kea48.tap"); shutil.copy(m1b / "m1.sym", ROOT / "build/kea48.sym")
    m1 = dumps("m1")
    shutil.copy("/tmp/kea48_cur.tap", ROOT / "build/kea48.tap"); shutil.copy("/tmp/kea48_cur.sym", ROOT / "build/kea48.sym")
    cur = dumps("cur")
    for v in views:
        a, b = m1[v], cur[v]
        da = sum(1 for r in range(1, 13) for c in range(8, 24) if a[0x1800 + 32 * r + c] != b[0x1800 + 32 * r + c])
        dp = sum(1 for y in range(8, 104) for x in range(64, 192) if pix(a, x, y) != pix(b, x, y))
        dout = sum(1 for i in range(0, 6144) if a[i] != b[i] and not (8 <= (i & 31) < 24))
        print("view %-12s attr cells differing %3d/192 ; window pixels differing %5d/12288 ; pixel bytes outside window cols differing %d" % (v, da, dp, dout))
finally:
    shutil.copy("/tmp/kea48_cur.tap", ROOT / "build/kea48.tap"); shutil.copy("/tmp/kea48_cur.sym", ROOT / "build/kea48.sym")
