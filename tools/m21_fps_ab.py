#!/usr/bin/env python3
"""m21_fps_ab.py - back-to-back ZEsarUX fps of the M2 and M2.1 tapes with the identical protocol (load, SPACE, 2 s, frames over 4 s)."""
import sys, time, pathlib
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
from t6_zes import Zes
ROOT = pathlib.Path("/home/ubuntu/work/killemall")
import re
def load_sym(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", p.read_text(), re.M)}
for rnd in range(2):
    for label, tap, symf in (("M2  ", "build/killemall48_m2.tap", "build/kea48_pre_m21.sym"), ("M2.1", "build/killemall48_m21.tap", "build/kea48.sym")):
        SYM = load_sym(ROOT / symf)
        z = Zes(str(ROOT / tap), port=10180)
        try:
            time.sleep(3.0); z.keys(["SPACE"], hold=0.15, gap=1.0); time.sleep(2.0)
            f0 = z.rd16(SYM["frames"]); time.sleep(4.0); f1 = z.rd16(SYM["frames"])
            print("%s run %d: start view live %.1f fps" % (label, rnd, (f1 - f0) / 4.0), flush=True)
        finally:
            z.close()
