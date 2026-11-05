#!/usr/bin/env python3
"""m28_xmode_diag.py - why did the game not START in m28_hostkey_test (X11 mode)? Measures the emulation speed in --vo xwindows
under Xvfb (ticks = 50 Hz ISR counter), then tries START via (a) XTEST SPACE held 1.5 s, (b) ZRCP set-ui-io-ports SPACE.
Appends to build/m28_hostkey.out."""
import os, re, sys, time, pathlib, socket, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / "build/killemall48_m25.tap"); DISP = ":78"; PORT = 10179
out = open(ROOT / "build/m28_hostkey.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); out.write(s + "\n"); out.flush()
log("== m28_xmode_diag %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists("/tmp/.X11-unix/X" + DISP[1:]): break
    time.sleep(0.1)
env = dict(os.environ, DISPLAY=DISP)
def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
vo = os.environ.get("VO", "xwindows")
cmd = [ZES, "--noconfigfile", "--vo", vo, "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_xdiag.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); xvfb.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd16(a):
    r = zrcp(s, "read-memory %d 2" % a, 0.3); h = "".join(c for c in r if c in "0123456789ABCDEFabcdef")[:4]
    b = bytes.fromhex(h) if len(h) == 4 else b"\0\0"; return b[0] | (b[1] << 8)
t0 = time.time()
while time.time() - t0 < 90 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
log("vo=%s menu after %.1f s" % (vo, time.time() - t0))
a = rd16(SYM["ticks"]); time.sleep(2.0); b = rd16(SYM["ticks"])
log("emulation speed in the menu: %d ticks in 2.0 s = %.1f Hz (50 = real time)" % (b - a, (b - a) / 2.0))
ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]
wid = ids[-1] if ids else ""
xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "200", "150"); xdo("click", "1"); time.sleep(0.3)
log("X window %s focused=%s" % (wid, xdo("getwindowfocus").stdout.strip()))
xdo("keydown", "space"); time.sleep(0.3); mx = zrcp(s, "get-ui-io-ports", 0.2); time.sleep(1.2); xdo("keyup", "space"); time.sleep(1.5)
m = re.search(r"\b([0-9A-Fa-f]{18})\b", mx)
log("XTEST SPACE 1.5 s: ports while held %s -> frames %d posx %.2f" % (m.group(1) if m else mx.strip()[:40], rd16(SYM["frames"]), rd16(SYM["posx"]) / 256))
a = rd16(SYM["ticks"]); time.sleep(2.0); b = rd16(SYM["ticks"]); log("speed now: %.1f Hz" % ((b - a) / 2.0))
if rd16(SYM["frames"]) == 0:
    zrcp(s, "set-ui-io-ports " + ports(["SPACE"]), 0.05); time.sleep(0.3); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.5)
    log("ZRCP SPACE 0.3 s: frames %d posx %.2f" % (rd16(SYM["frames"]), rd16(SYM["posx"]) / 256))
if rd16(SYM["frames"]) > 0:
    a = rd16(SYM["frames"]); time.sleep(2.0); b = rd16(SYM["frames"]); log("in-game render speed: %.1f fps" % ((b - a) / 2.0))
    for k in ("q", "z", "x"):
        px, py = rd16(SYM["posx"]), rd16(SYM["posy"]); xdo("keydown", k); time.sleep(0.6); xdo("keyup", k); time.sleep(0.3)
        log("XTEST %s 0.6 s: posx %+.3f posy %+.3f" % (k.upper(), (rd16(SYM["posx"]) - px) / 256, (rd16(SYM["posy"]) - py) / 256))
try: zrcp(s, "exit-emulator", 0.3)
except Exception: pass
try: p.wait(5)
except subprocess.TimeoutExpired: p.kill()
xvfb.kill()
log("== done")
