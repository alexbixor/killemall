#!/usr/bin/env python3
"""bp128.py - run the 128K tape with a ZRCP breakpoint at PC=24576 (stub) and PC=32768 (engine) to see whether the
loader ever reaches them; dump registers/paging/BANKM/stub bytes at the hit. Output -> build/bp128.out"""
import socket, subprocess, time, os, sys, pathlib, re, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10300 + random.randint(0, 40)
TAP = str(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/killemall128_m2.tap"))
BPS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["PC=6000H", "PC=8000H"]
LOG = open(ROOT / "build/bp128.out", "w")
def log(*a): print(*a, file=LOG, flush=True)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_bp128.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
    return "%s | %s | 7FFD %s BANKM %s" % (r[:70], pg, m.group(1) if m else "?", rd(23388, 1, 0.1).hex())
log("enable-breakpoints ->", zrcp(s, "enable-breakpoints", 0.3).split("command>")[0].strip()[:80])
for i, c in enumerate(BPS):
    log("set-breakpoint %d %s ->" % (i + 1, c), zrcp(s, "set-breakpoint %d %s" % (i + 1, c), 0.3).split("command>")[0].strip()[:80])
log("get-breakpoints ->", zrcp(s, "get-breakpoints", 0.3).split("command>")[0].strip()[:160].replace("\n", " / "))
t0 = time.time(); hits = 0
while time.time() - t0 < float(os.environ.get("SECS", "40")):
    r = zrcp(s, "get-registers", 0.1).split("command>")[0]
    m = re.search(r"PC=([0-9a-fA-F]{4})", r)
    if m and int(m.group(1), 16) in (0x6000, 0x8000):
        hits += 1
        log("HIT t=%.1f %s" % (time.time() - t0, st()))
        log("  stub@24576", rd(24576, 34).hex(), "| 49152:", rd(49152, 8).hex(), "| 32768:", rd(32768, 8).hex())
        log("  ERR_NR", rd(23610, 1).hex(), "RAMTOP", rd(23730, 2).hex(), "SP area", rd(0xFF40, 16).hex())
        if hits >= 2: break
        zrcp(s, "exit-cpu-step", 0.3); time.sleep(0.5)
    time.sleep(0.2)
log("final:", st()); log("hits", hits)
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
