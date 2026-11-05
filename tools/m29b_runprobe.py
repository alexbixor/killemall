#!/usr/bin/env python3
"""m29b_runprobe.py - can ZRCP cpu-step mode give frame-exact captures? 48K tape: start the game, hold Q, enter-cpu-step,
then repeat `run N` (N opcodes) + save-screen + read frames/ticks. If the saved screens change between runs, the display
is rendered in this mode and a slow-motion capture can use it. usage: m29b_runprobe.py [48k|128k] [N]"""
import sys, time, pathlib, subprocess, re, random, socket, os, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
mach = sys.argv[1] if len(sys.argv) > 1 else "48k"; N = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
tap, symf = {"48k": ("build/killemall48_m25.tap", "build/kea48.sym"), "128k": ("build/killemall128_m2.tap", "build/kea128.sym")}[mach]
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / symf).read_text(), re.M)}
port = 10800 + random.randint(0, 60)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
       "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit", "--machine", mach, str(ROOT / tap)]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_runprobe.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(160):
    try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); raise SystemExit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.15)); return int(m.group(1), 16) if m else -1
def rd(addr, n):
    h = "".join(ch for ch in q("read-memory %d %d" % (addr, n), 0.1) if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
def st():
    b = rd(S["ticks"], 8)
    return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8) if len(b) == 8 else None
def tap_k(keys, hold=0.25, gap=1.2):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
t0 = time.time()
while time.time() - t0 < 90 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
time.sleep(1.5)
for k in (("SPACE",), ("ENTER",), ("SPACE",)):
    tap_k(k); v = st()
    if v and v[1] > 0: break
print("game running: st", st(), flush=True)
zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.02); time.sleep(0.3)
print("enter-cpu-step:", q("enter-cpu-step").strip()[:60], "pc %04x" % pc(), "st", st(), flush=True)
last = None
for i in range(14):
    t2 = time.time(); r = q("run %d" % N, 0.05); t3 = time.time()
    bmp = "/tmp/runprobe_%02d.bmp" % i; q("save-screen " + bmp, 0.25)
    h = hashlib.md5(open(bmp, "rb").read()).hexdigest()[:8] if os.path.exists(bmp) else "none"
    print("run %2d: %.2f s wall, pc %04x st %s screen %s %s" % (i, t3 - t2, pc(), st(), h, "same" if h == last else "CHANGED"), flush=True)
    last = h
zrcp(s, "set-ui-io-ports " + ports(), 0.02)
q("exit-cpu-step"); time.sleep(0.5); print("after exit: pc %04x st %s" % (pc(), st()))
q("exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
