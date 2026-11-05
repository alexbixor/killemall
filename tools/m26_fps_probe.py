#!/usr/bin/env python3
"""m26_fps_probe.py - WHY is the 128K slower? Same tape flow as run128/m25b_zes but samples BOTH `frames` (main loop) and
`ticks` (50 Hz ISR) over the same wall-clock window, so emulator speed and engine speed separate:
  emu speed  = ticks / (50 * wall s)           (1.00 = ZEsarUX at real speed)
  engine fps = frames * 50 / ticks             (independent of the emulator's wall-clock speed)
usage: m26_fps_probe.py 48k|128k <tap> <sym> [secs]   -> one summary line + per-second samples; exit 0."""
import socket, subprocess, time, os, sys, pathlib, re, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
mach, tap, symf = sys.argv[1], str(ROOT / sys.argv[2]), ROOT / sys.argv[3]
secs = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", symf.read_text(), re.M)}
PORT = 10200 + random.randint(0, 60)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", mach, "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_m26_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(80):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd16(addr):
    r = zrcp(s, "read-memory %d 2" % addr, 0.15).split("command>")[0]
    h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:4]
    return int(h[0:2], 16) | (int(h[2:4], 16) << 8) if len(h) == 4 else -1
t0 = time.time()
while time.time() - t0 < 90 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
time.sleep(1.5)
early = os.environ.get("EARLY")          # EARLY=1: m25b_zes timing (one SPACE, 0.8 s, measure) instead of the run128 key loop
if early:
    zrcp(s, "set-ui-io-ports " + ports(("SPACE",), 0), 0.05); time.sleep(0.15)
    zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.5 + 0.8)
else:
    for k in (("SPACE",), ("ENTER",), ("SPACE",)):
        zrcp(s, "set-ui-io-ports " + ports(k, 0), 0.05); time.sleep(0.25)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.2)
        if rd16(SYM["frames"]) > 0: break
    time.sleep(1.0)
f0, k0, w0 = rd16(SYM["frames"]), rd16(SYM["ticks"]), time.time()
print("%s measure starts at frames=%d ticks=%d (%s timing)" % (mach, f0, k0, "EARLY" if early else "run128"))
rows = []
for i in range(int(secs)):
    time.sleep(1.0)
    f, k, w = rd16(SYM["frames"]), rd16(SYM["ticks"]), time.time()
    rows.append((w - w0, (f - f0) & 0xFFFF, (k - k0) & 0xFFFF))
w, df, dk = rows[-1]
print("%s %s: wall %.2f s, frames +%d, ticks +%d -> emu speed %.2fx, engine %.2f fps @50Hz (wall fps %.2f), %.1f ticks/frame" % (
    mach, os.path.basename(tap), w, df, dk, dk / (50.0 * w), 50.0 * df / dk if dk else 0, df / w, dk / float(df) if df else 0))
print("samples (wall s, frames, ticks):", rows)
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
