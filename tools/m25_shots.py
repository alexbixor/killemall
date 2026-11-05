#!/usr/bin/env python3
"""m25_shots.py - ZEsarUX (real 48K ROM, real timing) run of a tape: menu -> START; live fps at the start view (>= 8);
then staged enemy views: the things table is poked over ZRCP (zombie / imp planted in the corridor ahead at 3 distances,
AI frozen by state 0 and the enemy tick skipped via posting them 'idle' every shot) -> stills build/m25_<tag>_<name>_d<d>.png
and a strip build/m25_<tag>_strip.png (3D window only, x4). usage: m25_shots.py <tap> <tag>"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m25.tap")
tag = sys.argv[2] if len(sys.argv) > 2 else "v1"
SYM = load_sym(str(ROOT / "build/kea48.sym"))
fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += not ok
z = Zes(tap, port=10185, log="/tmp/zes_m25.log")
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(0.8)
def fps(secs=3.0):
    f0 = z.rd16(SYM["frames"]); time.sleep(secs); f1 = z.rd16(SYM["frames"])
    return ((f1 - f0) & 0xFFFF) / secs
f_live = fps(); print("start view, live level: %.1f fps" % f_live)
check(f_live >= 8.0, "fps floor 8 at the start view (got %.1f)" % f_live)
z.png(ROOT / ("build/m25_%s_start.png" % tag))
# staged views: wipe the things table, plant one enemy ahead; player stays at the start (3.5, 7.5, angle 0); corridor east
def plant(typ, d, lat=0.0, state=0):
    z.wr(SYM["things"], [0] * 128)
    x = 3.5 + d; y = 7.5 + lat
    ix, fx = int(x), int((x - int(x)) * 256); iy, fy = int(y), int((y - int(y)) * 256)
    z.wr(SYM["things"], [typ, fx, ix, fy, iy, state, 30, 0])
    z.wr(SYM["posx"], [128, 3]); z.wr(SYM["posy"], [128, 7]); z.wr(SYM["angle"], [0])
shots = []
for typ, name in ((2, "zombie"), (1, "imp")):
    for d in (2.5, 1.5, 0.9):
        plant(typ, d); time.sleep(0.6)
        p = ROOT / ("build/m25_%s_%s_d%d.png" % (tag, name, int(d * 10)))
        z.png(p); shots.append((p, "%s d=%.1f" % (name, d)))
        f = fps(1.5); print("%s d=%.1f: %.1f fps" % (name, d, f))
        check(f >= 6.0, "fps >= 6 with %s at %.1f (got %.1f)" % (name, d, f))
# attack pose + dead pose of the zombie at 1.2
plant(2, 1.2, state=2); time.sleep(0.6); p = ROOT / ("build/m25_%s_zombie_attack.png" % tag); z.png(p); shots.append((p, "zombie attack"))
plant(2, 1.2, state=3); time.sleep(0.6); p = ROOT / ("build/m25_%s_zombie_dead.png" % tag); z.png(p); shots.append((p, "zombie dead"))
z.close()
strip = Image.new("RGB", (len(shots) * 512 + (len(shots) - 1) * 8, 384), (40, 40, 40))
for i, (p, lab) in enumerate(shots):
    im = Image.open(p).convert("RGB").crop((192, 24, 576, 312)).resize((512, 384), Image.NEAREST)
    strip.paste(im, (i * 520, 0))
out = ROOT / ("build/m25_%s_strip.png" % tag); strip.save(out); print("strip", out, strip.size, [lab for _, lab in shots])
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
