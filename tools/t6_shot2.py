#!/usr/bin/env python3
"""t6_shot2.py - game view with 2 sprites clearly in sight (T1's static scene: barrel (5.0,7.5) + health (5.5,8.3) poked into
the runtime things table, player at the level start 3.5,7.5 angle 0) -> build/m2_game.png + fps there; then the start view
with the live level (imp + zombie AI) -> build/m2_game_live.png + fps. usage: t6_shot2.py [tap]"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
z = Zes(tap, port=10165)
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.0)
def fps():
    f0 = z.rd16(SYM["frames"]); time.sleep(4.0); return (z.rd16(SYM["frames"]) - f0) / 4.0
print("start view, live level (imp + zombie chasing): %.1f fps" % fps()); z.png(ROOT / "build/m2_game_live.png")
z.wr(SYM["things"], [0] * 128)                                   # static scene: no enemies
z.wr(SYM["things"], [21, 0, 5, 128, 7, 0, 30, 0, 16, 128, 5, 0x4D, 8, 0, 30, 0])   # barrel (5.0,7.5), health (5.5,8.3)
z.wr(SYM["posx"], [128, 3]); z.wr(SYM["posy"], [128, 7]); z.wr(SYM["angle"], [0]); z.wr(SYM["health"], [100])
time.sleep(1.5)
print("start view, barrel + health (2 sprites, static): %.1f fps" % fps()); z.png(ROOT / "build/m2_game.png")
z.wr(SYM["things"], [0] * 128); time.sleep(1.0)
print("start view, walls + weapon only: %.1f fps" % fps())
z.close()
