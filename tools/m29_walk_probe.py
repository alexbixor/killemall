#!/usr/bin/env python3
"""m29_walk_probe.py - fine-grained walk probe: hold Q (forward) and sample posx/posy/ticks/frames every ~0.1 s WITHOUT
screen grabs, so the step rate over time is visible. usage: m29_walk_probe.py 48k|128k [hold_s] [pre_s]
pre_s = seconds to wait after the game starts before holding Q (default 1.0)."""
import sys, time, pathlib, re, random, subprocess, socket, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
mach = sys.argv[1]; HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0; PRE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
tap, symf = {"48k": ("build/killemall48_m25.tap", "build/kea48.sym"), "128k": ("build/killemall128_m2.tap", "build/kea128.sym"), "next": (None, "build/kea128.sym")}[mach]
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / symf).read_text(), re.M)}
port = 10400 + random.randint(0, 80)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit"]
if mach == "next":          # M2.9b: Spectrum Next via the real NextZXOS boot (m29_nextboot), .nex copied onto a scratch SD image
    import shutil
    MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"; MMC = ROOT / "build/tbblue_probe.mmc"; shutil.copyfile(MMC_SRC, MMC)
    cmd += ["--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked", "--enable-mmc", "--mmc-file", str(MMC),
            "--enable-divmmc-ports", "--copy-file-to-mmc", str(ROOT / "build/killemall128.nex"), "killemall.nex"]
else:
    cmd += ["--machine", mach, str(ROOT / tap)]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_m29p_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.08)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b""
def st():
    b = rd(S["ticks"], 8)      # ticks(2) frames(2) posx(2) posy(2) are consecutive in both builds
    if len(b) < 8: return None
    return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8)
assert S["frames"] == S["ticks"] + 2 and S["posx"] == S["ticks"] + 4 and S["posy"] == S["ticks"] + 6, "layout changed"
t0 = time.time()
if mach == "next":
    from m29_nextboot import boot_to_game
    def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
    def tapk(keys, hold=0.2, gap=0.5):
        zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    boot_to_game(q, tapk, pc, log=lambda m: None)
else:
    while time.time() - t0 < 90 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
time.sleep(1.5)
for k in (("SPACE",), ("ENTER",), ("SPACE",)):
    zrcp(s, "set-ui-io-ports " + ports(k, 0), 0.05); time.sleep(0.25)
    zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.2)
    v = st()
    if v and v[1] > 0: break
time.sleep(PRE)
rows = []
k0, f0, x0, y0 = st(); w0 = time.time()
zrcp(s, "set-ui-io-ports " + ports(("Q",), 0), 0.02)
while time.time() - w0 < HOLD:
    v = st()
    if v: rows.append((time.time() - w0,) + v)
zrcp(s, "set-ui-io-ports " + ports(), 0.02)
v = st(); rows.append((time.time() - w0,) + v)
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
print("%s start: ticks %d frames %d pos (%.2f, %.2f); hold Q %.1f s after %.1f s pre-wait" % (mach, k0, f0, x0 / 256, y0 / 256, HOLD, PRE))
prev = None
for w, k, f, x, y in rows:
    d = (((x - x0) ** 2 + (y - y0) ** 2) ** 0.5) / 256.0
    dk = (k - k0) & 0xFFFF
    rate = ""
    if prev and dk > prev[0]:
        rate = " %.1f steps/s in window" % (((d - prev[1]) / 0.15) / ((dk - prev[0]) / 50.0))
    print("  wall %.2f ticks %3d frames %3d pos (%.2f, %.2f) walked %.2f cells = %.1f steps%s" % (w, dk, (f - f0) & 0xFFFF, x / 256, y / 256, d, d / 0.15, rate))
    prev = (dk, d)
