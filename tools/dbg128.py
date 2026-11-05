#!/usr/bin/env python3
"""dbg128.py - trace the 128K tape load in ZEsarUX: every 1 s log PC/SP/pages/7FFD/BANKM; at the end dump the screen's
text rows (ROM report) and key memory. Output -> build/dbg128.out"""
import socket, subprocess, time, os, sys, pathlib, re, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10200 + random.randint(0, 40)
TAP = str(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/killemall128_m2.tap"))
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
LOG = open(ROOT / "build/dbg128.out", "w")
def log(*a): print(*a, file=LOG, flush=True)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_dbg128.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); log("no ZRCP"); sys.exit(1)
zrcp(s, "", 0.5)
def rd(addr, n, wait=0.3):
    r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
def st():
    r = zrcp(s, "get-registers", 0.15).split("command>")[0].strip().replace("\n", " ")
    pg = zrcp(s, "get-memory-pages", 0.15).split("command>")[0].strip()
    io = zrcp(s, "get-io-ports", 0.15).split("command>")[0]
    m = re.search(r"7FFD port: (\w+)", io)
    return "%s | %s | 7FFD %s BANKM %s" % (r[:62], pg, m.group(1) if m else "?", rd(23388, 1, 0.1).hex())
t0 = time.time()
FAST = float(os.environ.get("FAST", "0"))      # seconds of fast polling (registers only) at the start
while time.time() - t0 < FAST:
    r = zrcp(s, "get-registers", 0.0).split("command>")[0].strip().replace("\n", " ")
    log("t=%5.2f %s" % (time.time() - t0, r[:50]))
while time.time() - t0 < SECS:
    log("t=%4.1f %s" % (time.time() - t0, st()))
    time.sleep(1.0)
scr = rd(16384, 6912, 1.5)
if len(scr) == 6912:
    scr_to_png(scr, str(ROOT / "build/dbg128.png"))
    # text rows 0..23 as 32-char strings by matching ROM font is heavy; dump row-16..23 pixel density instead
    for row in range(24):
        dens = sum(bin(scr[((row * 8 + k) & 0xC0) << 5 | ((k & 7) << 8) | ((row & 7) << 5) | bx]).count("1") for k in range(8) for bx in range(32))
        log("row %2d pixels %d" % (row, dens))
log("stub@24576", rd(24576, 18).hex(), "| 49152:", rd(49152, 16).hex(), "| 32768:", rd(32768, 8).hex(), "| 27904:", rd(27904, 8).hex())
log("ERR_NR 23610", rd(23610, 1).hex(), "PPC 23621", rd(23621, 2).hex(), "RAMTOP 23730", rd(23730, 2).hex(), "FLAGS 23611", rd(23611, 1).hex())
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
