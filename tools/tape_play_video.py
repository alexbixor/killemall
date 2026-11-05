#!/usr/bin/env python3
"""tape_play_video.py - play a Kill'em all tape (48K or 128K edition) in a headless ZEsarUX of the matching machine, drive it
through the menu into the game and along a scripted key path, grab the rendered screen (ZRCP save-screen, all layers) as fast as
the control port allows, and assemble a real-time MP4 with a caption (machine, elapsed Spectrum time, frames, measured fps).
usage: tape_play_video.py 48k|128k <tape> <out.mp4> ["Q:2,P:0.8,Q:2,M:0.3,..."]  (key:seconds; '+' combines; '-' = no key)
Only the emulator this script starts is touched; it is closed at the end."""
import sys, time, pathlib, subprocess, re, random, os, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from run48 import zrcp, ZES
from fe_shot import ports

ROOT = pathlib.Path(__file__).resolve().parent.parent
mach, tap, out = sys.argv[1], str((ROOT / sys.argv[2]).resolve()), ROOT / sys.argv[3]
script = sys.argv[4] if len(sys.argv) > 4 else "Q:2.0,P:0.7,Q:1.5,M:0.2,-:0.6,M:0.2,-:0.6,O:0.7,Q:2.0,M:0.2,-:0.8"
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H",
       (ROOT / ("build/kea48.sym" if mach == "48k" else "build/kea128.sym")).read_text(), re.M)}
LABEL = {"48k": "ZX Spectrum 48K edition (tape)", "128k": "ZX Spectrum 128K edition (tape, AY music)"}[mach]
port = 10600 + random.randint(0, 150)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", mach, "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit", tap]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_tpv_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(160):
    try: s = socket = __import__("socket").create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); raise SystemExit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(addr, n):
    h = "".join(ch for ch in q("read-memory %d %d" % (addr, n), 0.06) if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b""
def st():
    b = rd(SYM["ticks"], 8)           # ticks, frames, posx, posy are consecutive words in both editions
    return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8) if len(b) == 8 else None
def tapk(keys, hold=0.25, gap=1.2):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
tmp = pathlib.Path("/tmp/tpv_%s" % mach); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
def shot(i):
    bmp = tmp / ("s%03d.bmp" % i); q("save-screen " + str(bmp), 0.22)
    return bmp if bmp.exists() else None

t0 = time.time()
while time.time() - t0 < 90 and pc() < 0x8000: time.sleep(0.5)   # tape loaded, game code (front end) running
print("%s: engine running after %.1f s (PC %04x)" % (mach, time.time() - t0, pc()), flush=True)
time.sleep(2.0)
frames = []; i = 0
def grab(t):
    global i
    b = shot(i); v = st(); i += 1
    if b and v: frames.append((t, b, v))
w0 = time.time()
grab(0.0)                                   # title / menu
for k in (("SPACE",), ("ENTER",), ("SPACE",)):  # menu -> START (the game's frames counter starts moving)
    tapk(k); grab(time.time() - w0); v = st()
    if v and v[1] > 0: break
time.sleep(0.8); grab(time.time() - w0)
k0 = st(); wk = time.time()
for step in script.split(","):
    keys, secs = step.split(":"); secs = float(secs)
    keyset = () if keys == "-" else tuple(keys.split("+"))
    zrcp(s, "set-ui-io-ports " + ports(keyset), 0.02); te = time.time() + secs
    while time.time() < te: grab(time.time() - w0)
zrcp(s, "set-ui-io-ports " + ports(), 0.02); grab(time.time() - w0)
k1 = st()
q("exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
dk = (k1[0] - k0[0]) & 0xFFFF; df = (k1[1] - k0[1]) & 0xFFFF
fps = 50.0 * df / dk if dk else 0
print("%s: %d grabs; in-game: %d frames in %d ticks (%.2f s Spectrum time) = %.1f fps; walked from (%.2f, %.2f) to (%.2f, %.2f)" % (
    mach, len(frames), df, dk, dk / 50.0, fps, k0[2] / 256.0, k0[3] / 256.0, k1[2] / 256.0, k1[3] / 256.0), flush=True)
fd = out.with_suffix(""); shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
names = []
frames = [e for e in frames if Image.open(e[1]).convert('L').getextrema()[1] > 0]   # drop all-black grabs (emulator not yet drawing)
first_game = next((j for j, e in enumerate(frames) if e[0] >= wk - w0), 0)
for n, (t, b, v) in enumerate(frames):
    im = Image.open(b).convert("RGB"); im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    cap = Image.new("RGB", (im.width, 40), (0, 0, 0)); d = ImageDraw.Draw(cap)
    d.text((6, 4), LABEL, fill=(255, 255, 255))
    if n < first_game:
        d.text((6, 22), "t=%4.1fs   menu -> START" % t, fill=(255, 255, 0))
    else:
        dk_ = (v[0] - k0[0]) & 0xFFFF; df_ = (v[1] - k0[1]) & 0xFFFF
        d.text((6, 22), "t=%4.1fs   game frames %3d in %4d ticks = %4.1f fps   pos (%.1f, %.1f)" % (
            t, df_, dk_, 50.0 * df_ / dk_ if dk_ else 0, v[2] / 256.0, v[3] / 256.0), fill=(255, 255, 0))
    pan = Image.new("RGB", (im.width, im.height + 40), (0, 0, 0)); pan.paste(cap, (0, 0)); pan.paste(im, (0, 40))
    nm = fd / ("f%04d.png" % n); pan.save(nm); names.append((t, nm))
with open(fd / "list.txt", "w") as f:
    for j, (t, nm) in enumerate(names):
        dur = (names[j + 1][0] - t) if j + 1 < len(names) else 1.5
        f.write("file '%s'\nduration %.3f\n" % (nm.name, max(0.04, dur)))
    f.write("file '%s'\nduration 1.5\n" % names[-1][1].name)
r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(fd / "list.txt"),
                    "-vf", "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2", "-r", "25", str(out)], capture_output=True, text=True)
print("mp4 %s %d bytes, %d grabs over %.1f s wall, ffmpeg rc %d %s" % (out, out.stat().st_size if out.exists() else 0, len(names),
      names[-1][0], r.returncode, r.stderr.strip()[:200]), flush=True)
