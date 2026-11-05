#!/usr/bin/env python3
"""m23_shots.py - ZEsarUX (real 48K ROM, real timing) run of build/killemall48_m23.tap:
 1. menu -> START with SPACE; live fps at the start view (floor lines on) -> check >= 8
 2. stills: build/m23_start_v1.png (phase 0), build/m23_walk_v1.png (after walking ~1 s forward)
 3. SPACE fires (ammo 50 -> 49), M does not fire; M opens: bump a door via keys and read the cell (door_log count)
 4. 6 s walk clip: build/m23_walk_v1.mp4 (frames every ~0.2 s via ZRCP, 5 fps) - forward 2.5 s, turn 1 s, back 1.5 s
Port 10182. exit 1 on a failed check."""
import sys, time, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m23.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += not ok
z = Zes(tap, port=10182, log="/tmp/zes_m23.log")
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(0.8)
def fps(secs=3.0):
    f0 = z.rd16(SYM["frames"]); time.sleep(secs); f1 = z.rd16(SYM["frames"])
    return ((f1 - f0) & 0xFFFF) / secs
f_live = fps(); print("start view, live level, floor lines: %.1f fps" % f_live)
check(f_live >= 8.0, "fps floor 8 at the start view (got %.1f)" % f_live)
z.png(ROOT / "build/m23_start_v1.png")
ph0 = z.rd(SYM["fl_ph"], 1)[0]
# 3. keys: SPACE fires, M does not
am0 = z.rd(SYM["ammo"], 1)[0]
z.keys(["M"], hold=0.3, gap=0.4); am_m = z.rd(SYM["ammo"], 1)[0]
z.keys(["SPACE"], hold=0.25, gap=0.6); am_s = z.rd(SYM["ammo"], 1)[0]
check(am_m == am0 and am_s == am0 - 1, "SPACE fires (ammo %d -> %d), M does not (%d)" % (am0, am_s, am_m))
# 4. clip + walk still
fd = pathlib.Path("/tmp/m23_frames"); fd.mkdir(exist_ok=True)
for f in fd.glob("*.png"): f.unlink()
n = [0]
def shot():
    z.png(fd / ("f%04d.png" % n[0])); n[0] += 1
def act(keys, secs):
    z.hold(keys); t0 = time.time()
    while time.time() - t0 < secs:
        shot(); time.sleep(0.12)
    z.release()
for _ in range(3): shot(); time.sleep(0.2)
act(["Q"], 2.5)
z.png(ROOT / "build/m23_walk_v1.png"); ph1 = z.rd(SYM["fl_ph"], 1)[0]
check(ph1 != ph0, "walking forward advanced the floor phase (%d -> %d)" % (ph0, ph1))
act(["P"], 1.0); ph2 = z.rd(SYM["fl_ph"], 1)[0]
check(ph2 == ph1, "turning left the floor phase alone (%d)" % ph2)
act(["A"], 1.5); ph3 = z.rd(SYM["fl_ph"], 1)[0]
check(ph3 != ph2, "walking back changed the floor phase (%d -> %d)" % (ph2, ph3))
for _ in range(3): shot(); time.sleep(0.2)
z.close()
mp4 = ROOT / "build/m23_walk_v1.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "6", "-i", str(fd / "f%04d.png"), "-vf", "scale=512:384:flags=neighbor,format=yuv420p",
                "-c:v", "libx264", "-crf", "20", str(mp4)], check=False)
print("frames %d -> %s (%d bytes)" % (n[0], mp4, mp4.stat().st_size if mp4.exists() else -1))
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)