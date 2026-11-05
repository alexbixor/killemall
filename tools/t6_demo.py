#!/usr/bin/env python3
"""t6_demo.py - ~15 s demo MP4 of build/killemall48_m2.tap: menu (cursor moves), START, walk forward, turn, fire, open a
door; frames grabbed over ZRCP every ~0.25 s -> ffmpeg 8 fps. usage: t6_demo.py [tap] [out.mp4]"""
import sys, time, pathlib, os, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
mp4 = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "build/m2_demo.mp4")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
fd = pathlib.Path("/tmp/m2_frames"); fd.mkdir(exist_ok=True)
for f in fd.glob("*.png"): f.unlink()
z = Zes(tap, port=10163)
n = [0]
poslog = open(ROOT / "build/t6_demo_pos.txt", "w")
def shot(k=1):
    for _ in range(k):
        p = z.rd(SYM["posx"], 5)
        z.png(fd / ("f%04d.png" % n[0]))
        poslog.write("%d %d.%03d %d.%03d %d\n" % (n[0], p[1], p[0] * 1000 // 256, p[3], p[2] * 1000 // 256, p[4])); n[0] += 1
def act(keys, hold, shots):
    """hold keys, grabbing `shots` frames meanwhile (0.25 s apart), then release"""
    z.hold(keys)
    for _ in range(shots):
        time.sleep(max(0.0, hold / shots - 0.12)); shot()
    z.release()
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.5)
shot(6)                                            # title + menu, 0.75 s
z.keys(["6"], gap=0.1); shot(3); z.keys(["6"], gap=0.1); shot(3); z.keys(["7"], gap=0.1); shot(2); z.keys(["7"], gap=0.1); shot(3)
z.keys(["SPACE"], hold=0.15, gap=0.5); shot(4)     # START -> game
# level 1: start (3.5,7.5) facing east (angle 0). Walk forward, look around, fire at whatever is there.
act(["Q"], 2.0, 8)                                 # forward
act(["O"], 0.8, 4)                                 # turn left
act(["P"], 1.4, 6)                                 # turn right
act(["SPACE"], 0.3, 2); shot(2); act(["SPACE"], 0.3, 2); shot(2)      # fire twice (M2.3: SPACE)
act(["Q"], 2.0, 8)
# door demo: teleport in front of the door at (9,7)? find the first door cell (8) in the level and face it from an open cell
ld = z.rd(SYM["level_data"], 9 + 1024); cells = ld[9:9 + 1024]
doors = [(i % 32, i // 32) for i, c in enumerate(cells) if c == 8]
for (dx, dy) in doors:
    for ox, oy, ang in ((-1, 0, 0), (1, 0, 128), (0, -1, 64), (0, 1, 192)):
        nx, ny = dx + ox, dy + oy
        if cells[ny * 32 + nx] == 0 and cells[(dy - oy) * 32 + dx - ox] == 0:
            break
    else:
        continue
    break
print("door at (%d,%d), standing (%d,%d) facing %d" % (dx, dy, nx, ny, ang))
z.wr(SYM["posx"], [0x80, nx]); z.wr(SYM["posy"], [0x80, ny]); z.wr(SYM["angle"], [ang]); time.sleep(0.6); shot(3)
act(["Q"], 1.6, 7)                                 # bump -> door opens (snd 2) and walk through
shot(3)
act(["P"], 1.0, 4); shot(3)
z.close()
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "5", "-i", str(fd / "f%04d.png"), "-vf", "format=yuv420p",
                "-c:v", "libx264", "-crf", "20", mp4], check=False)
print("frames %d -> %s (%d bytes)" % (n[0], mp4, pathlib.Path(mp4).stat().st_size if pathlib.Path(mp4).exists() else -1))
