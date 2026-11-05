#!/usr/bin/env python3
"""t6_e2e.py - end-to-end run of build/killemall48_m2.tap in headless ZEsarUX 48K:
 title grab (menu over the title, after load) -> build/m2_title.png / m2_menu.png; SPACE -> START -> build/m2_game.png;
 fps over 4 s from `frames`; 24 random-moment grabs tearing check; frame grabs for the MP4 (walk, fire, door).
usage: t6_e2e.py [tap]   env: SYM (default build/kea48.sym)"""
import sys, time, random, pathlib, os, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
SYM = load_sym(os.environ.get("SYM", str(ROOT / "build/kea48.sym")))
title = (ROOT / "build/title.scr").read_bytes()
z = Zes(tap, port=10160)
t0 = time.time()
dt = z.wait_running(90, lo=SYM["fe_run"])          # menu loop runs inside frontend (>= fe_run)
print("code running (PC in menu) after %.1f s" % dt)
time.sleep(1.5)
scr = z.png(ROOT / "build/m2_menu.png")
print("menu grab: title pixel rows 0..127 intact:", scr[:4096] == title[:4096], " attr rows 0..15 intact:", scr[6144:6144 + 512] == title[6144:6144 + 512])
print("frames counter while in menu (must stay 0):", z.rd16(SYM["frames"]), " fe_cur", z.rd(SYM["fe_cur"], 1).hex(), " opt bytes", z.rd(SYM["opt_music"], 5).hex())
# move down/up once to prove the menu reacts (6 = down, 7 = up), then back to START
z.keys(["6"]); c1 = z.rd(SYM["fe_cur"], 1).hex(); z.keys(["7"]); c2 = z.rd(SYM["fe_cur"], 1).hex()
print("menu cursor after down/up: %s -> %s" % (c1, c2))
z.keys(["SPACE"], hold=0.15, gap=1.0)                 # START GAME
time.sleep(2.0)
f0 = z.rd16(SYM["frames"]); time.sleep(4.0); f1 = z.rd16(SYM["frames"])
print("game started: frames %d -> %d over 4 s = %.1f fps (start view, live, 2 sprites + imp/zombie AI)" % (f0, f1, (f1 - f0) / 4.0))
z.png(ROOT / "build/m2_game.png"); print("saved build/m2_game.png")
print("hud: health/ammo/keys/kills", z.rd(SYM["health"], 4).hex(), "level", z.rd(SYM["level"], 1).hex())
# tearing: 24 random-moment grabs of the window (rows 8..103, byte cols 8..23)
res = []
for i in range(24):
    time.sleep(random.uniform(0.05, 0.35))
    s = z.grab()
    cols = [0] * 16
    for y in range(8, 104):
        base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + 8
        for c in range(16):
            if s[base + c]: cols[c] += 1
    res.append((sum(cols), sum(1 for c in cols if c == 0)))
print("tearing: grabs %d, nonzero bytes min/max %d/%d, grabs with a blank byte column %d, grabs < 40%% set %d" %
      (len(res), min(r[0] for r in res), max(r[0] for r in res), sum(1 for r in res if r[1] > 0), sum(1 for r in res if r[0] < 0.4 * 1536)))
# face-to-wall fps: poke the player in front of a wall (walls-only view)
z.wr(SYM["posx"], [0x4D, 0x01]); z.wr(SYM["posy"], [0x4D, 0x01]); z.wr(SYM["angle"], [32]); time.sleep(1.0)
f0 = z.rd16(SYM["frames"]); time.sleep(4.0); f1 = z.rd16(SYM["frames"])
print("face-to-wall (1.3,1.3,32): %.1f fps" % ((f1 - f0) / 4.0))
z.png(ROOT / "build/m2_wall.png")
# BREAK -> pause menu -> resume
z.keys(["CAPS", "SPACE"], hold=0.3, gap=1.0); z.png(ROOT / "build/m2_pause.png")
print("pause menu: PC %04X in frontend: %s" % (z.pc(), SYM["fe_begin"] <= z.pc() < SYM["fe_end"]))
z.keys(["SPACE"], hold=0.15, gap=1.0)
print("after RESUME: PC %04X in game: %s" % (z.pc(), not (SYM["fe_begin"] <= z.pc() < SYM["fe_end"])))
z.png(ROOT / "build/m2_resume.png")
z.close()
print("elapsed %.0f s" % (time.time() - t0))
