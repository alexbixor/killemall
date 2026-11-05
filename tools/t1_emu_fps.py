#!/usr/bin/env python3
"""t1_emu_fps.py - ZEsarUX fps at a viewpoint with two things poked into the runtime table (barrel 1.5 cells ahead, health).
usage: t1_emu_fps.py <tap> <sym> [clear]   (clear = remove all things first)"""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
tap = str(pathlib.Path(sys.argv[1]).resolve()); symf = sys.argv[2]
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(symf).read_text(), re.M)}
PORT = 10140
p = subprocess.Popen([ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
                      "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap],
                     stdout=open("/tmp/zes_t1fps.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
zrcp(s, "", 0.5); time.sleep(13)
def wm(addr, data): zrcp(s, "write-memory %d %s" % (addr, " ".join("%02X" % b for b in data)), 0.05)
wm(SYM["things"], bytes(128))                              # no enemies: static scene
if len(sys.argv) < 4:
    wm(SYM["things"], bytes([21, 0, 5, 128, 7, 0, 30, 0, 16, 128, 5, 0x4D, 8, 0, 30, 0]))   # barrel (5.0,7.5), health (5.5,8.3)
wm(SYM["posx"], bytes([128, 3])); wm(SYM["posy"], bytes([128, 7])); wm(SYM["angle"], bytes([0]))
time.sleep(1.0)
def frames():
    r = zrcp(s, "read-memory %d 2" % SYM["frames"], 0.3)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return int(h[2:4] + h[0:2], 16)
f0 = frames(); time.sleep(4.0); f1 = frames()
print("emulator fps over 4 s: %.1f (frames %d -> %d) %s" % ((f1 - f0) / 4.0, f0, f1, "2 sprites" if len(sys.argv) < 4 else "no things"))
r = zrcp(s, "read-memory 16384 6912", 1.2)
hexs = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
if len(hexs) >= 13824: scr_to_png(bytes.fromhex(hexs[:13824]), "build/t1_emu_%s.png" % ("2spr" if len(sys.argv) < 4 else "walls")); print("png saved")
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
