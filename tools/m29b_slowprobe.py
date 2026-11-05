#!/usr/bin/env python3
"""m29b_slowprobe.py - does `--emulatorspeed N` (percent) slow the whole emulation so ZRCP save-screen catches every game frame?
48K tape at N %: boot, start the game, hold Q, then save-screen as fast as possible for WALL seconds and compare each saved
screen with the previous one. Prints ticks and frames progressed per wall second and how many distinct screens were caught.
usage: m29b_slowprobe.py [percent] [wall_s]"""
import sys, time, pathlib, subprocess, re, random, socket, os, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
PCT = int(sys.argv[1]) if len(sys.argv) > 1 else 10; WALL = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}
port = 10900 + random.randint(0, 60)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
       "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit",
       "--emulatorspeed", str(PCT), "--machine", "48k", str(ROOT / "build/killemall48_m25.tap")]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_slowprobe.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
t0 = time.time(); v0 = st(); time.sleep(5); v1 = st()
print("boot phase: %s -> %s in 5 s wall (speed %d%%)" % (v0, v1, PCT), flush=True)
while time.time() - t0 < 500 and not (0x8000 <= pc() < 0xC000): time.sleep(1.0)
print("engine reached after %.0f s wall" % (time.time() - t0), flush=True)
time.sleep(2.0)
def tap_k(keys, hold, gap):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
HOLD = 0.25 * 100.0 / PCT; GAP = 1.2 * 100.0 / PCT
for k in (("SPACE",), ("ENTER",), ("SPACE",)):
    tap_k(k, HOLD, GAP); v = st()
    if v and v[1] > 0: break
print("game running: st", st(), "after %.0f s wall" % (time.time() - t0), flush=True)
zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.02)
k0 = st(); w0 = time.time(); last = None; distinct = 0; shots = 0; log = []
while time.time() - w0 < WALL:
    bmp = "/tmp/slowprobe_%03d.bmp" % shots; q("save-screen " + bmp, 0.2); v = st(); shots += 1
    h = hashlib.md5(open(bmp, "rb").read()).hexdigest()[:8] if os.path.exists(bmp) else "none"
    if h != last: distinct += 1
    log.append((round(time.time() - w0, 2), v[0] - k0[0], v[1] - k0[1], h != last)); last = h
zrcp(s, "set-ui-io-ports " + ports(), 0.02)
k1 = st(); dw = time.time() - w0
print("walk: %.1f s wall, ticks +%d (%.1f ticks per wall s = %.0f%% speed), frames +%d, shots %d, distinct screens %d" % (
    dw, k1[0] - k0[0], (k1[0] - k0[0]) / dw, 100.0 * (k1[0] - k0[0]) / dw / 50.0, k1[1] - k0[1], shots, distinct), flush=True)
print("pos: (%.2f, %.2f) -> (%.2f, %.2f)" % (k0[2] / 256.0, k0[3] / 256.0, k1[2] / 256.0, k1[3] / 256.0))
print("first 12 samples (wall s, dticks, dframes, new screen):", log[:12])
q("exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
