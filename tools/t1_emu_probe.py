#!/usr/bin/env python3
"""t1_emu_probe.py - ZRCP probe: ticks/frames deltas, IM2 table bytes, registers."""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
tap = str(pathlib.Path(sys.argv[1]).resolve()); symf = sys.argv[2]
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(symf).read_text(), re.M)}
PORT = 10150
p = subprocess.Popen([ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
                      "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap],
                     stdout=open("/tmp/zes_t1probe.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
zrcp(s, "", 0.5); time.sleep(13)
def rd(addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.3)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n])
def w16(label): b = rd(SYM[label], 2); return b[0] | b[1] << 8
t0, f0 = w16("ticks"), w16("frames"); time.sleep(2.0); t1, f1 = w16("ticks"), w16("frames")
print("ticks %d -> %d (%d), frames %d -> %d (%d)" % (t0, t1, t1 - t0, f0, f1, f1 - f0))
print("ISRVEC 65021:", rd(65021, 3).hex(), "table 65024..:", rd(65024, 4).hex(), "65279:", rd(65279, 2).hex())
print("isr code:", rd(SYM["isr"], 12).hex())
print("regs:", zrcp(s, "get-registers", 0.3).split("command>")[0].strip().replace("\n", " ")[:300])
if "health" in SYM: print("health/ammo:", rd(SYM["health"], 4).hex(), "weapon_frame", rd(SYM["weapon_frame"], 1).hex(), "nvis", rd(SYM["nvis"], 1).hex())
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
