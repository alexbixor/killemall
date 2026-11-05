#!/usr/bin/env python3
"""m_hw_diag.py (lane M) - why did the right button look stuck and BREAK not pause in m_mouse_hw.py? Polls in_bits/in_break/
fe_mode/PC at ~15 Hz through button press/release and a CAPS+SPACE hold, 128K tape with mouse ON, xwindows under Xvfb."""
import os, re, sys, time, pathlib, socket, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / "build/killemall128_m.tap"); DISP = ":82"; PORT = 10182
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea128.sym").read_text(), re.M)}
subprocess.run(["pkill", "-f", "Xvfb %s" % DISP], capture_output=True)
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
env = dict(os.environ, DISPLAY=DISP)
def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enablekempstonmouse", "--kempstonmouse-sens", "1", "--zoom", "3",
       "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_mdiag.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.1)); return int(m.group(1), 16) if m else -1
def rd(addr, n=1):
    h = "".join(c for c in q("read-memory %d %d" % (addr, n), 0.05) if c in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
def rd8(name): return rd(SYM[name])[0]
def wr8(name, v): q("write-memory %d %d" % (SYM[name], v), 0.1)
def tapk(keys, hold=0.25, gap=1.0):
    q("set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); q("set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
def snap(tag):
    print("%-28s t=%5.2f in_bits %02X in_break %d fe_mode %d fe_count %d fe_cur %d mouse_btn %02X ammo %d PC %04X io %s" % (
        tag, time.time() - t0, rd8("in_bits"), rd8("in_break"), rd8("fe_mode"), rd8("fe_count"), rd8("fe_cur"), rd8("mouse_btn"), rd8("ammo"), pc(),
        (re.search(r"\b([0-9A-Fa-f]{18})\b", q("get-ui-io-ports", 0.1)) or [None, "?"])[1]), flush=True)
t0 = time.time()
while time.time() - t0 < 120 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]; wid = ids[-1]
xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "384", "288"); time.sleep(0.3)
wr8("opt_mouse", 1); tapk(("SPACE",), 0.3, 2.5)
snap("in game")
xdo("mousedown", "3")
for i in range(8): snap("right held"); time.sleep(0.1)
xdo("mouseup", "3")
for i in range(8): snap("right released"); time.sleep(0.1)
xdo("mousemove_relative", "--", "5", "0")
for i in range(4): snap("after a 5 px move"); time.sleep(0.1)
xdo("mousedown", "1"); time.sleep(0.3); snap("left held"); xdo("mouseup", "1"); time.sleep(0.3); snap("left released")
xdo("mousemove_relative", "--", "5", "0"); time.sleep(0.3); snap("after a 5 px move")
q("set-ui-io-ports " + ports(("CAPS", "SPACE")), 0.05)
for i in range(8): snap("CAPS+SPACE held (zrcp)"); time.sleep(0.1)
q("set-ui-io-ports " + ports(), 0.05)
for i in range(6): snap("released"); time.sleep(0.2)
# keyboard route 2: XTEST keys
xdo("keydown", "shift"); xdo("keydown", "space")
for i in range(6): snap("XTEST shift+space held"); time.sleep(0.1)
xdo("keyup", "space"); xdo("keyup", "shift")
for i in range(4): snap("XTEST released"); time.sleep(0.2)
try: q("exit-emulator", 0.3)
except Exception: pass
try: p.wait(5)
except subprocess.TimeoutExpired: p.kill()
xvfb.kill()
