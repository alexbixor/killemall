#!/usr/bin/env python3
"""m28_strafe_probe.py - reproduce "strafe is not working" (user 3 Nov ~17:00Z) on the REAL 48K tape in ZEsarUX: menu -> START,
then hold each movement key 0.6 s and read posx/posy/angle before and after. Keys: Q fwd, A back, O/P turn, Z/X strafe.
Also reads in_read's result live (in_bits) while Z is held. Writes build/m28_strafe_probe.out"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m25.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
out = open(ROOT / "build/m28_strafe_probe.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); out.write(s + "\n"); out.flush()
log("== m28_strafe_probe %s %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), tap))
z = Zes(tap, port=10152, log="/tmp/zes_strafe.log")
z.wait_running()
time.sleep(1.5)
z.keys(["SPACE"], hold=0.25, gap=1.5)              # START GAME
def pos():
    px = z.rd16(SYM["posx"]); py = z.rd16(SYM["posy"]); an = z.rd(SYM["angle"], 1)[0]
    return px, py, an
def show(tag, a, b):
    log("%-10s posx %.3f -> %.3f (d %+.3f)  posy %.3f -> %.3f (d %+.3f)  angle %d -> %d" % (
        tag, a[0] / 256, b[0] / 256, (b[0] - a[0]) / 256, a[1] / 256, b[1] / 256, (b[1] - a[1]) / 256, a[2], b[2]))
log("frames %d, health %d" % (z.rd16(SYM["frames"]), z.rd(SYM["health"], 1)[0]))
for key in ("Q", "A", "O", "P", "Z", "X"):
    a = pos(); z.hold([key]); time.sleep(0.15)
    ib = z.rd(SYM["in_bits"], 1)[0] if "in_bits" in SYM else -1
    time.sleep(0.45); z.release(); time.sleep(0.15); b = pos()
    show(key, a, b); log("   in_bits while %s held: %s" % (key, "%02X" % ib if ib >= 0 else "n/a"))
z.png(ROOT / "build/m28_strafe_probe.png")
z.close()
log("== done")
