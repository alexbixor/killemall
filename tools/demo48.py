#!/usr/bin/env python3
"""demo48.py - run kea48.tap in headless ZEsarUX, poke the player's angle step by step (a slow 360 turn), grab the
screen each step through ZRCP read-memory, and write a PNG of the start view plus an MP4 of the turn.
usage: demo48.py build/kea48.tap out.png out.mp4 [steps=32] [px py angle]
  px py angle (optional): poke the player position (cell units, 8.8 fixed) and angle before measuring, so that the
  fps number is taken at that viewpoint instead of the level start.
env: LOADWAIT (s to wait for the tape to load, default 8), FRAMES_DIR (where the per-step PNGs go, default /tmp/kea_frames),
     SYM (symbol file, default build/kea48.sym - must match the tap!)
"""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
PORT = 10130
SYMFILE = os.environ.get("SYM", "/home/ubuntu/work/killemall/build/kea48.sym")
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(SYMFILE).read_text(), re.M)}

def grab(s):
    r = zrcp(s, "read-memory 16384 6912", 1.2)
    hexs = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(hexs[:13824]) if len(hexs) >= 13824 else b""

def main():
    tap = str(pathlib.Path(sys.argv[1]).resolve()); png = str(pathlib.Path(sys.argv[2]).resolve()); mp4 = str(pathlib.Path(sys.argv[3]).resolve())
    steps = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    view = (float(sys.argv[5]), float(sys.argv[6]), int(sys.argv[7])) if len(sys.argv) > 7 else None
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_demo48.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5); time.sleep(float(os.environ.get("LOADWAIT", "8")))
    print("write-memory help:", zrcp(s, "help write-memory", 0.3).split("command>")[0].strip().replace("\n", " | ")[:200])
    if view:
        px, py, ang = view
        ix, fx = int(px), int((px - int(px)) * 256); iy, fy = int(py), int((py - int(py)) * 256)
        zrcp(s, "write-memory %d %02X %02X" % (SYM["posx"], fx, ix), 0.05)
        zrcp(s, "write-memory %d %02X %02X" % (SYM["posy"], fy, iy), 0.05)
        zrcp(s, "write-memory %d %02X" % (SYM["angle"], ang & 255), 0.05)
        print("viewpoint poked: pos (%.3f, %.3f) angle %d" % (ix + fx / 256.0, iy + fy / 256.0, ang & 255))
        time.sleep(1.0)
    frames_dir = pathlib.Path(os.environ.get("FRAMES_DIR", "/tmp/kea_frames")); frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("*.png"): f.unlink()
    t0 = time.time()
    scr = grab(s)
    if scr: scr_to_png(scr, png); print("saved", png)
    # read the frame counter twice, 4 s apart -> real fps in the emulator
    def frames_count():
        r = zrcp(s, "read-memory %d 2" % SYM["frames"], 0.3)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        return int(h[2:4] + h[0:2], 16) if len(h) >= 4 else -1
    f0 = frames_count(); time.sleep(4.0); f1 = frames_count()
    print("emulator fps over 4 s: %.1f (frames %d -> %d)" % ((f1 - f0) / 4.0, f0, f1))
    base_ang = view[2] if view else 0
    for i in range(steps):
        ang = (base_ang + i * 256 // steps) & 255
        zrcp(s, "write-memory %d %02X" % (SYM["angle"], ang), 0.05)
        time.sleep(0.45)
        scr = grab(s)
        if scr: scr_to_png(scr, str(frames_dir / ("f%04d.png" % i)))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    n = len(list(frames_dir.glob("*.png")))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "8", "-i", str(frames_dir / "f%04d.png"),
                    "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", mp4], check=False)
    print("mp4", mp4, "frames", n, "elapsed %.0fs" % (time.time() - t0))

if __name__ == "__main__":
    main()
