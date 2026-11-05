#!/usr/bin/env python3
"""t1_emu_sample.py - sample ticks/frames/health/IFF every 0.4 s from load (finds when the ISR stops)."""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
tap = str(pathlib.Path(sys.argv[1]).resolve()); symf = sys.argv[2]
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(symf).read_text(), re.M)}
PORT = 10160
p = subprocess.Popen([ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
                      "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap],
                     stdout=open("/tmp/zes_t1s.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
zrcp(s, "", 0.5); time.sleep(float(os.environ.get("LOADWAIT", "7")))
def rd(addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.2)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n])
def w16(label): b = rd(SYM[label], 2); return b[0] | b[1] << 8
for i in range(int(os.environ.get("N", "16"))):
    regs = zrcp(s, "get-registers", 0.2).split("command>")[0]
    pc = re.search(r"PC=(\w+)", regs); iff = re.search(r"(IFF\S*)", regs)
    extra = ""
    if "health" in SYM: extra = "health %d imp0 state %d" % (rd(SYM["health"], 1)[0], rd(SYM["things"] + 5, 1)[0])
    print("%5.1fs ticks %5d frames %4d pc %s %s %s" % (i * 0.4, w16("ticks"), w16("frames"), pc.group(1) if pc else "?", iff.group(1) if iff else "", extra))
    time.sleep(0.4)
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
