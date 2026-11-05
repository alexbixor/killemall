#!/usr/bin/env python3
"""t6_quit.py - BREAK -> pause menu -> QUIT TO MENU (cursor up = wrap to last item) -> menu over the frozen view -> START
-> new game (stats reset, level 1). usage: t6_quit.py [tap]"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
z = Zes(tap, port=10164)
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.5)
z.wr(SYM["health"], [37]); z.wr(SYM["kills"], [5]); z.hold(["Q"]); time.sleep(0.8); z.release(); time.sleep(0.5)
print("in game: health %d kills %d pos %s" % (z.rd(SYM["health"], 1)[0], z.rd(SYM["kills"], 1)[0], z.rd(SYM["posx"], 4).hex()))
z.keys(["CAPS", "SPACE"], hold=0.3, gap=1.0)
print("pause: fe_mode %s fe_cur %s" % (z.rd(SYM["fe_mode"], 1).hex(), z.rd(SYM["fe_cur"], 1).hex()))
z.keys(["7"], gap=0.4)                                   # up from RESUME wraps to the last item = QUIT TO MENU
print("after up: fe_cur %s (expect 07)" % z.rd(SYM["fe_cur"], 1).hex())
z.keys(["SPACE"], hold=0.15, gap=1.5)
print("after QUIT: fe_mode %s PC %04X frames %d" % (z.rd(SYM["fe_mode"], 1).hex(), z.pc(), z.rd16(SYM["frames"])))
z.png(ROOT / "build/m2_menu_quit.png")
f0 = z.rd16(SYM["frames"]); time.sleep(1.0); print("frames frozen in menu:", f0 == z.rd16(SYM["frames"]))
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.5)
print("START again: health %d kills %d level %d level_data id %d pos %s fps-ish frames %d" % (
    z.rd(SYM["health"], 1)[0], z.rd(SYM["kills"], 1)[0], z.rd(SYM["level"], 1)[0], z.rd(SYM["level_data"], 1)[0], z.rd(SYM["posx"], 4).hex(), z.rd16(SYM["frames"])))
print("SP reset check: get-registers", z.cmd("get-registers", 0.3).strip()[:40])
z.close()
