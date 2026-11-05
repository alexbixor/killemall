#!/usr/bin/env python3
"""m21_fps_wall_ab.py - back-to-back ZEsarUX face-to-wall fps (1.3,1.3,32) of the M2 and M2.1 tapes, same protocol as t6_e2e."""
import sys, time, pathlib, re
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
from t6_zes import Zes
ROOT = pathlib.Path("/home/ubuntu/work/killemall")
def load_sym(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", p.read_text(), re.M)}
for rnd in range(2):
    for label, tap, symf in (("M2  ", "build/killemall48_m2.tap", "build/kea48_pre_m21.sym"), ("M2.1", "build/killemall48_m21.tap", "build/kea48.sym")):
        SYM = load_sym(ROOT / symf)
        z = Zes(str(ROOT / tap), port=10180)
        try:
            time.sleep(3.0); z.keys(["SPACE"], hold=0.15, gap=1.0); time.sleep(2.0)
            z.wr(SYM["posx"], [0x4D, 0x01]); z.wr(SYM["posy"], [0x4D, 0x01]); z.wr(SYM["angle"], [32]); time.sleep(1.0)
            f0 = z.rd16(SYM["frames"]); time.sleep(4.0); f1 = z.rd16(SYM["frames"])
            print("%s run %d: face-to-wall %.1f fps" % (label, rnd, (f1 - f0) / 4.0), flush=True)
        finally:
            z.close()
