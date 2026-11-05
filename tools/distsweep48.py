#!/usr/bin/env python3
"""distsweep48.py - frame T-states vs distance to the facing wall: the player walks east along y = 7.5 from x = 3.5 towards
the wall at x = 8 (cells 8..11 are the 'A' block) at angle 0; prints render T-states for the given tap/sym pair.
usage: distsweep48.py tap sym"""
import sys, pathlib, re, subprocess, shutil
ROOT = pathlib.Path("/home/ubuntu/work/killemall"); PY = str(ROOT / ".venv/bin/python")
tap, sym = sys.argv[1], sys.argv[2]
shutil.copy(ROOT / "build/kea48.tap", "/tmp/ds_cur.tap"); shutil.copy(ROOT / "build/kea48.sym", "/tmp/ds_cur.sym")
try:
    shutil.copy(tap, ROOT / "build/kea48.tap"); shutil.copy(sym, ROOT / "build/kea48.sym")
    row = []
    for x in [3.5, 4.5, 5.5, 6.5, 7.0, 7.3, 7.6, 7.8]:
        out = subprocess.run([PY, str(ROOT / "tools/test48.py"), str(x), "7.5", "0"], capture_output=True, text=True).stdout
        m = re.search(r"render T-states (\d+)", out)
        row.append((x, int(m.group(1)) if m else -1))
    print(" ".join("x=%.1f(d=%.1f):%d" % (x, 8 - x, t) for x, t in row))
    ts = [t for _, t in row]
    print("min %d max %d ratio max/min %.2f" % (min(ts), max(ts), max(ts) / min(ts)))
finally:
    shutil.copy("/tmp/ds_cur.tap", ROOT / "build/kea48.tap"); shutil.copy("/tmp/ds_cur.sym", ROOT / "build/kea48.sym")
