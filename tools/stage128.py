#!/usr/bin/env python3
"""stage128.py - loader stage test (lane T4 debugging). Builds build/stage128.tap = BASIC: CLEAR 27903 / LOAD ""CODE (stub) /
RANDOMIZE USR 24576 / PRINT "DONE" / STOP, + stub block + headerless bank1.bin, runs it on the 128k machine and reads
physical bank 1 (ZRCP memory zone 0 = 128K RAM, address = bank*16384+offset) to see whether bank1.bin landed.
Output -> build/stage128.out"""
import socket, subprocess, time, os, sys, pathlib, re, random, struct
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
import mktap128 as M
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10400 + random.randint(0, 40)
LOG = open(ROOT / "build/stage128.out", "w")
def log(*a): print(*a, file=LOG, flush=True)
bank1 = (ROOT / "build/bank1.bin").read_bytes()
stub = bytearray(M.STUB); stub[M.STUB_LEN_AT:M.STUB_LEN_AT + 2] = struct.pack("<H", len(bank1))
prog = M.line(10, M.tok("CLEAR") + M.num(M.CLEAR)) + M.line(20, M.tok("LOAD") + b'""' + M.tok("CODE"))
prog += M.line(30, M.tok("RANDOMIZE", "USR") + M.num(M.STUB_AT)) + M.line(40, M.tok("PRINT") + b'"DONE"') + M.line(50, M.tok("STOP"))
tape = M.header(0, "stage", len(prog), 10, len(prog)) + M.tap_block(0xFF, prog)
tape += M.header(3, "page", len(stub), M.STUB_AT, 32768) + M.tap_block(0xFF, bytes(stub)) + M.tap_block(0xFF, bank1)
(ROOT / "build/stage128.tap").write_bytes(tape)
TAP = str(ROOT / "build/stage128.tap")
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", TAP]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_stage128.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
t0 = time.time()
for i in range(12):
    log("t=%4.1f %s" % (time.time() - t0, st())); time.sleep(1.0)
log("stub@24576", rd(24576, 34).hex())
log("mapped 49152:", rd(49152, 16).hex(), "| ERR_NR", rd(23610, 1).hex(), "RAMTOP", rd(23730, 2).hex())
log("zone0:", zrcp(s, "set-memory-zone 0", 0.3).split("command>")[0].strip()[:60])
for bank in range(8):
    log("bank %d @0: %s" % (bank, rd(bank * 16384, 16).hex()))
log("bank 5 @6144 attr:", rd(5 * 16384 + 6144, 8).hex())
zrcp(s, "set-memory-zone -1", 0.2)
scr = rd(16384, 6912, 1.5)
if len(scr) == 6912: scr_to_png(scr, str(ROOT / "build/stage128.png")); log("png build/stage128.png")
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
