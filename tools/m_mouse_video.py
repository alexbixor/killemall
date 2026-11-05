#!/usr/bin/env python3
"""m_mouse_video.py (lane M, 5 Nov 2026) - oracle D: build/night/M_mouse.mp4. ZEsarUX 128K (--enablekempstonmouse) with a real
X window under Xvfb (recipe: tools/m_mouse_hw.py); the 128K mouse tape boots to the menu, MOUSE is switched ON, the game starts
in level 01's start room; the mouse then sweeps right one full turn (angle +256 = 1024 counts), left one full turn, and a left
click fires (ammo 50 -> 49). Frames = ZRCP save-screen grabs (all layers) as fast as the control port allows, like
tools/tape_play_video.py; the caption carries the elapsed time, angle, the mouse counter and the ammo.
ZEsarUX's Kempston mouse X in --vo xwindows is the pointer position inside the window / zoom (3 px per count, mod 256; M_hw.out
probe: outside the window nothing counts, and run 1 of this script proved re-centring warps cancel the motion). So one
full turn = 1024 counts = 3072 px = 4 sweeps of 768 px across the Spectrum screen area, each followed by a warp of exactly
-768 px = 256 counts = invisible to the game (same counter value). The pointer starts at the left edge BEFORE START is
pressed (fe_exit re-bases mouse_last), so the first frame does not jump.
usage: timeout 500 .venv/bin/python tools/m_mouse_video.py > build/night/M_video.out 2>&1"""
import os, re, sys, time, pathlib, socket, subprocess, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / "build/killemall128_m.tap"); DISP = ":83"; PORT = 10183; OUT = ROOT / "build/night/M_mouse.mp4"
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea128.sym").read_text(), re.M)}
def log(*a): print(" ".join(str(x) for x in a), flush=True)
subprocess.run(["pkill", "-f", "Xvfb %s" % DISP], capture_output=True)
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists("/tmp/.X11-unix/X" + DISP[1:]): break
    time.sleep(0.1)
env = dict(os.environ, DISPLAY=DISP)
def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enablekempstonmouse", "--kempstonmouse-sens", "1", "--zoom", "3",
       "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), TAP]
log("== m_mouse_video %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_mvid.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); xvfb.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(addr, n=1):
    h = "".join(c for c in q("read-memory %d %d" % (addr, n), 0.06) if c in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b""
def st():
    b = rd(SYM["ticks"], 9)                       # ticks, frames, posx, posy words + angle byte are consecutive
    a = rd(SYM["ammo"]); l = rd(SYM["mouse_last"])
    if len(b) == 9 and a and l:
        return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8, b[8], a[0], l[0])
    return None
def tapk(keys, hold=0.25, gap=1.0):
    q("set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); q("set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
tmp = pathlib.Path("/tmp/m_vid"); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
frames = []; i = [0]
def shot():
    bmp = tmp / ("s%03d.bmp" % i[0]); q("save-screen " + str(bmp), 0.2); return bmp if bmp.exists() else None
def grab(phase):
    b = shot(); v = st(); i[0] += 1
    if b and v: frames.append((time.time() - w0, b, v, phase))
try:
    t0 = time.time()
    while time.time() - t0 < 120 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
    log("menu after %.1f s" % (time.time() - t0))
    ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]; wid = ids[-1]
    xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "144", "300"); time.sleep(0.5)   # left edge of the screen area
    w0 = time.time()
    grab("menu"); grab("menu")
    tapk(("Q",), 0.25, 0.8); grab("menu: cursor on MOUSE")
    tapk(("SPACE",), 0.25, 0.8); grab("menu: MOUSE -> ON"); grab("menu: MOUSE -> ON")
    tapk(("A",), 0.25, 0.8); grab("menu: START")
    tapk(("SPACE",), 0.3, 1.5)
    te = time.time() + 1.5
    while time.time() < te: grab("game: start room, level 01")
    def settled():                                   # wait until the emulator has consumed every queued pointer event
        v0 = st()[6]
        for _ in range(20):
            time.sleep(0.08); v1 = st()[6]
            if v1 == v0: return v1
            v0 = v1
        return v0
    def sweep(sign, label, sweeps=4, px=768, step=24):
        # 24 px = 8 counts every 40 ms (one xdotool process per 8 steps, chained with its own sleep): never more than a few
        # counts per emulator frame, so the 8-bit dx the game reads can never exceed 128 and flip sign (run 3 of this script
        # drove the steps faster than the emulator drained its X queue -> coalesced jumps > 128 counts -> wrong direction).
        a0 = st()[4]
        for n in range(sweeps):
            for k in range(px // step // 8):
                args = []
                for _ in range(8): args += ["mousemove_relative", "--", str(sign * step), "0", "sleep", "0.04"]
                xdo(*args); grab("%s %d/%d" % (label, n + 1, sweeps))
            settled()
            xdo("mousemove_relative", "--", str(-sign * px), "0")      # warp back exactly 256 counts: the game sees no change
            settled()
            v = st(); log("  %s sweep %d: angle %d counter %d pointer %s" % (label[:17], n + 1, v[4], v[6], xdo("getmouselocation").stdout.split()[0]))
        return (st()[4] - a0) & 0xFF
    turned_r = sweep(+1, "mouse sweep RIGHT (one full turn)")
    te = time.time() + 1.0
    while time.time() < te: grab("after the right sweep")
    xdo("mousemove_relative", "--", "768", "0"); settled()             # to the right edge (256 counts = invisible), sweep left from there
    turned_l = sweep(-1, "mouse sweep LEFT (one full turn)")
    te = time.time() + 1.0
    while time.time() < te: grab("after the left sweep")
    am0 = st()[5]
    xdo("mousedown", "1"); time.sleep(0.12); xdo("mouseup", "1")
    te = time.time() + 2.0
    while time.time() < te: grab("LEFT CLICK = FIRE")
    am1 = st()[5]
    log("right sweep: angle moved %d (mod 256; 0 = exactly one turn), left sweep: %d; click: ammo %d -> %d; %d grabs" % (turned_r, turned_l, am0, am1, len(frames)))
finally:
    try: q("exit-emulator", 0.3); s.close()
    except Exception: pass
    try: p.wait(5)
    except subprocess.TimeoutExpired: p.kill()
    xvfb.kill()
# assemble
fd = OUT.with_suffix(""); shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
frames = [e for e in frames if Image.open(e[1]).convert("L").getextrema()[1] > 0]
names = []
for n, (t, b, v, phase) in enumerate(frames):
    im = Image.open(b).convert("RGB"); im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    cap = Image.new("RGB", (im.width, 56), (0, 0, 0)); d = ImageDraw.Draw(cap)
    d.text((6, 4), "KILL'EM ALL 128K  -  MOUSE LOOK (Kempston / Next PS/2)   MOUSE: ON, 1/4 angle unit per count", fill=(255, 255, 255))
    d.text((6, 20), "t=%5.1fs   %s" % (t, phase), fill=(255, 255, 0))
    d.text((6, 36), "angle %3d (256 = 360 deg)   mouse X counter %3d   ammo %2d   frames %d   pos (%.1f, %.1f)" % (
        v[4], v[6], v[5], v[1], v[2] / 256.0, v[3] / 256.0), fill=(0, 255, 255))
    pan = Image.new("RGB", (im.width, im.height + 56), (0, 0, 0)); pan.paste(cap, (0, 0)); pan.paste(im, (0, 56))
    nm = fd / ("f%04d.png" % n); pan.save(nm); names.append((t, nm))
with open(fd / "list.txt", "w") as f:
    for j, (t, nm) in enumerate(names):
        dur = (names[j + 1][0] - t) if j + 1 < len(names) else 1.5
        f.write("file '%s'\nduration %.3f\n" % (nm.name, max(0.04, dur)))
    f.write("file '%s'\nduration 1.5\n" % names[-1][1].name)
r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(fd / "list.txt"),
                    "-vf", "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2", "-r", "25", str(OUT)], capture_output=True, text=True)
log("mp4 %s %d bytes, %d frames over %.1f s, ffmpeg rc %d %s" % (OUT.relative_to(ROOT), OUT.stat().st_size if OUT.exists() else 0, len(names),
    names[-1][0], r.returncode, r.stderr.strip()[:200]))
