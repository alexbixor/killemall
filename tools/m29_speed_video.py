#!/usr/bin/env python3
"""m29_speed_video.py - M2.9 proof: 48K and 128K walk the SAME distance in the same time (fixed 10 steps/s).
Two headless ZEsarUX instances (real tapes, real emulator speed) are driven over ZRCP: start the game from the menu, then
HOLD Q (forward) for WALK seconds while grabbing the screen ~8 times/s and reading posx/posy/frames/ticks. Frames are
stacked (48K on top, 128K below) with a live caption and encoded with real wall-clock durations -> build/m29_speed.mp4.
usage: m29_speed_video.py [walk_s]   (default 2.0).  Prints distance walked (cells) and steps/s per machine; exit 0."""
import sys, time, pathlib, shutil, subprocess, re, random, threading
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from run48 import zrcp, scr_to_png, ZES
import t6_zes
from fe_shot import ports

ROOT = pathlib.Path(__file__).resolve().parent.parent
WALK = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
MACH = {"48k": ("build/killemall48_m25.tap", "build/kea48.sym"), "128k": ("build/killemall128_m2.tap", "build/kea128.sym")}

class Z(t6_zes.Zes):
    def __init__(self, mach, tap, port):
        self.mach = mach
        import subprocess, socket, os
        tap = str(pathlib.Path(tap).resolve())
        cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", mach, "--nosplash", "--nowelcomemessage",
               "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port),
               "--quickexit", tap]
        self.p = subprocess.Popen(cmd, stdout=open("/tmp/zes_m29_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
        self.s = None
        for _ in range(80):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=1); break
            except OSError:
                time.sleep(0.25)
        if self.s is None:
            self.p.kill(); raise SystemExit("no ZRCP " + mach)
        zrcp(self.s, "", 0.5)

def sym(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / path).read_text(), re.M)}

def run(mach, out):
    tap, symf = MACH[mach]; S = sym(symf)
    z = Z(mach, ROOT / tap, 10300 + random.randint(0, 80))
    t = z.wait_running(90); time.sleep(1.5)
    for k in (("SPACE",), ("ENTER",), ("SPACE",)):            # menu item 0 = START
        z.keys(k, hold=0.25, gap=1.2)
        if z.rd16(S["frames"]) > 0: break
    time.sleep(1.0)
    def st():
        b = z.rd(S["posx"], 4); f = z.rd16(S["frames"]); k = z.rd16(S["ticks"])
        return (b[0] | b[1] << 8, b[2] | b[3] << 8, f, k) if len(b) == 4 else (0, 0, f, k)
    frames = []
    x0, y0, f0, k0 = st(); w0 = time.time()
    z.hold(("Q",))                                             # forward
    while True:
        w = time.time() - w0
        if w > WALK: break
        scr = z.grab(); x, y, f, k = st()
        frames.append((time.time() - w0, scr, x, y, f, k))
    z.release()
    x1, y1, f1, k1 = st(); w1 = time.time() - w0
    scr = z.grab(); frames.append((w1, scr, x1, y1, f1, k1))
    z.cmd("exit-emulator", 0.3); z.s.close()
    try: z.p.wait(timeout=5)
    except subprocess.TimeoutExpired: z.p.kill()
    out[mach] = dict(frames=frames, x0=x0, y0=y0, f0=f0, k0=k0, x1=x1, y1=y1, f1=f1, k1=k1, w=w1)

res = {}
th = [threading.Thread(target=run, args=(m, res)) for m in MACH]
for t in th: t.start()
for t in th: t.join()

def dist(r):
    return (((r["x1"] - r["x0"]) ** 2 + (r["y1"] - r["y0"]) ** 2) ** 0.5) / 256.0
summary = {}
for m, r in res.items():
    dk = (r["k1"] - r["k0"]) & 0xFFFF; df = (r["f1"] - r["f0"]) & 0xFFFF
    summary[m] = (dist(r), dk / 50.0, df, dk)
    print("%s: walked %.2f cells in %.2f s of Spectrum time (%.2f s wall), %d frames drawn, %d ticks -> %.2f cells/s, %.1f fps, steps/s %.1f" % (
        m, dist(r), dk / 50.0, r["w"], df, dk, dist(r) / (dk / 50.0) if dk else 0, 50.0 * df / dk if dk else 0, (dist(r) / 0.15) / (dk / 50.0) if dk else 0))
    print("  samples (ticks since start, cells walked, pos x.xx y.yy):", " ".join("%d:%.2f(%.2f,%.2f)" % ((e[5] - r["k0"]) & 0xFFFF,
          (((e[2] - r["x0"]) ** 2 + (e[3] - r["y0"]) ** 2) ** 0.5) / 256.0, e[2] / 256.0, e[3] / 256.0) for e in r["frames"]))

# video: stack 48K over 128K, nearest-time frame of each at a common 10 Hz timeline
fd = ROOT / "build/m29_speed_frames"; shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
SC = 3
def nearest(fr, t):
    return min(fr, key=lambda e: abs(e[0] - t))
T = max(res[m]["w"] for m in res); n = 0; lst = []
t = 0.0
while t <= T + 1e-6:
    img = Image.new("RGB", (256 * SC, 2 * 192 * SC + 3 * 22), (20, 20, 20)); d = ImageDraw.Draw(img)
    y = 0
    for m in ("48k", "128k"):
        e = nearest(res[m]["frames"], t)
        tmp = fd / "tmp.png"; scr_to_png(e[1], str(tmp))
        im = Image.open(tmp).resize((256 * SC, 192 * SC), Image.NEAREST)
        dcells = (((e[2] - res[m]["x0"]) ** 2 + (e[3] - res[m]["y0"]) ** 2) ** 0.5) / 256.0
        d.rectangle([0, y, 256 * SC, y + 22], fill=(0, 0, 0))
        d.text((6, y + 4), "%s  t=%.1fs  walked %.2f cells  frames %d" % (m.upper(), t, dcells, (e[4] - res[m]["f0"]) & 0xFFFF), fill=(255, 255, 255))
        img.paste(im, (0, y + 22)); y += 22 + 192 * SC
    d.rectangle([0, y, 256 * SC, y + 22], fill=(0, 0, 0))
    d.text((6, y + 4), "M2.9 fixed time step: hold forward %.1f s on both machines, same distance" % WALK, fill=(255, 255, 0))
    p = fd / ("f%04d.png" % n); img.save(p); lst.append(p); n += 1; t += 0.1
with open(fd / "list.txt", "w") as f:
    for p in lst: f.write("file '%s'\nduration 0.1\n" % p.name)
    f.write("file '%s'\nduration 1.5\n" % lst[-1].name)
mp4 = ROOT / "build/m29_speed.mp4"
r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(fd / "list.txt"), "-vf", "format=yuv420p",
                    "-r", "25", str(mp4)], capture_output=True, text=True)
print("mp4 %s %s bytes, %d frames, ffmpeg rc %d %s" % (mp4, mp4.stat().st_size if mp4.exists() else 0, n, r.returncode, r.stderr.strip()[:200]))
