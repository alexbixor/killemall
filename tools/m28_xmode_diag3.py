#!/usr/bin/env python3
"""m28_xmode_diag3.py - X11 mode: does the Z80 actually SEE the X keys that get-ui-io-ports shows? Probe = the menu's own
key memory fe_prev (b0 up, b1 down, b2 select) and fe_cur (highlighted row) while XTEST keys are held, then the same via
ZRCP set-ui-io-ports. Appends to build/m28_hostkey.out."""
import os, re, sys, time, pathlib, socket, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / "build/killemall48_m25.tap"); DISP = ":80"; PORT = 10182
out = open(ROOT / "build/m28_hostkey.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); out.write(s + "\n"); out.flush()
log("== m28_xmode_diag3 %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists("/tmp/.X11-unix/X" + DISP[1:]): break
    time.sleep(0.1)
env = dict(os.environ, DISPLAY=DISP)
def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_xdiag3.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); xvfb.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(a, n):
    r = zrcp(s, "read-memory %d %d" % (a, n), 0.3); h = "".join(c for c in r if c in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
def io():
    r = zrcp(s, "get-ui-io-ports", 0.2); m = re.search(r"\b([0-9A-Fa-f]{18})\b", r); return m.group(1).upper() if m else r.strip()[:30]
def state(tag):
    log("  %-28s io %s fe_prev %02X fe_cur %d in_break %d frames %d" % (tag, io(), rd(SYM["fe_prev"], 1)[0], rd(SYM["fe_cur"], 1)[0],
        rd(SYM["in_break"], 1)[0], rd(SYM["frames"], 2)[0] | rd(SYM["frames"], 2)[1] << 8))
t0 = time.time()
while time.time() - t0 < 90 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
log("menu after %.1f s" % (time.time() - t0))
ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]
wid = ids[-1] if ids else ""
xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "200", "150"); time.sleep(0.3)
state("idle")
xdo("keydown", "q"); time.sleep(0.3); state("XTEST q held (menu up)"); xdo("keyup", "q"); time.sleep(0.3); state("after q")
xdo("keydown", "a"); time.sleep(0.3); state("XTEST a held (menu down)"); xdo("keyup", "a"); time.sleep(0.3); state("after a")
xdo("keydown", "space"); time.sleep(0.3); state("XTEST space held"); time.sleep(0.3); state("XTEST space still held"); xdo("keyup", "space"); time.sleep(1.5); state("after space")
if (rd(SYM["frames"], 2)[0] | rd(SYM["frames"], 2)[1] << 8) == 0:
    zrcp(s, "set-ui-io-ports " + ports(["Q"]), 0.05); time.sleep(0.3); state("ZRCP Q held"); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(0.3); state("after ZRCP Q")
    zrcp(s, "set-ui-io-ports " + ports(["SPACE"]), 0.05); time.sleep(0.3); state("ZRCP SPACE held"); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.5); state("after ZRCP SPACE")
try: zrcp(s, "exit-emulator", 0.3)
except Exception: pass
try: p.wait(5)
except subprocess.TimeoutExpired: p.kill()
xvfb.kill()
log("== done")
