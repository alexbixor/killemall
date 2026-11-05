#!/usr/bin/env python3
"""t6_wrprobe.py - check ZRCP write-memory syntax + key hold/release on the running game. usage: t6_wrprobe.py [tap]"""
import sys, time, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
z = Zes(tap, port=10162)
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(1.0)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.0)
print("pos", z.rd(SYM["posx"], 4).hex())
print("help write-memory:", z.cmd("help write-memory", 0.3).strip().replace("\n", " | ")[:300])
r = z.cmd("write-memory %d 80 16" % SYM["posx"], 0.2); print("reply:", repr(r[:80]))
time.sleep(0.3); print("pos after wr", z.rd(SYM["posx"], 4).hex())
r = z.cmd("write-memory %d 8016" % SYM["posx"], 0.2); print("reply2:", repr(r[:80]))
time.sleep(0.3); print("pos after wr2", z.rd(SYM["posx"], 4).hex())
f0 = z.rd16(SYM["frames"]); z.hold(["Q"]); time.sleep(1.0); p1 = z.rd(SYM["posx"], 4).hex(); z.release(); time.sleep(1.0)
p2 = z.rd(SYM["posx"], 4).hex(); time.sleep(1.0); p3 = z.rd(SYM["posx"], 4).hex()
print("hold Q 1 s: pos %s -> released: %s -> 1 s later %s (frames %d -> %d)" % (p1, p2, p3, f0, z.rd16(SYM["frames"])))
print("in_bits", z.rd(SYM["in_bits"], 1).hex(), "io ports:", z.cmd("get-ui-io-ports", 0.2).strip()[:60] if "get-ui-io-ports" in z.cmd("help", 0.5) else "n/a")
z.close()
