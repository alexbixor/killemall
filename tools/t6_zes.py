#!/usr/bin/env python3
"""t6_zes.py - T6 helper: drive headless ZEsarUX 48K over ZRCP (start tap, key taps via set-ui-io-ports, screen grabs,
memory reads, symbol lookup). Import: from t6_zes import Zes, load_sym"""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]
KEY = {ch: (r, b) for r, row in enumerate(ROWS) for b, ch in enumerate(row)}
KEY.update({"CAPS": (0, 0), "ENTER": (6, 0), "SPACE": (7, 0), "SYM": (7, 1)})

def load_sym(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(path).read_text(), re.M)}

def ports(keys=(), joy=0):
    rows = [0xFF] * 8
    for k in keys:
        r, b = KEY[k]; rows[r] &= ~(1 << b) & 0xFF
    return "".join("%02X" % v for v in rows) + "%02X" % joy

class Zes:
    def __init__(self, tap, port=10150, log="/tmp/zes_t6.log", realvideo=False):
        tap = str(pathlib.Path(tap).resolve())
        cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
               "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port),
               "--quickexit", tap]
        self.p = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
        self.s = None
        for _ in range(80):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=1); break
            except OSError:
                time.sleep(0.25)
        if self.s is None:
            self.p.kill(); raise SystemExit("no ZRCP")
        zrcp(self.s, "", 0.5)
    def cmd(self, c, wait=0.3):
        return zrcp(self.s, c, wait).split("command>")[0]
    def pc(self):
        m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(self.s, "get-registers", 0.2))
        return int(m.group(1), 16) if m else -1
    def wait_running(self, limit=60, lo=0x8000):
        """poll until PC >= lo (code running after the tape loaded)"""
        t0 = time.time()
        while time.time() - t0 < limit:
            if self.pc() >= lo: return time.time() - t0
            time.sleep(0.5)
        return -1
    def rd(self, addr, n):
        r = self.cmd("read-memory %d %d" % (addr, n), 0.3 + n / 20000.0)
        h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:2 * n]
        return bytes.fromhex(h) if len(h) == 2 * n else b""
    def rd16(self, addr):
        b = self.rd(addr, 2); return b[0] | (b[1] << 8) if len(b) == 2 else -1
    def wr(self, addr, data):
        self.cmd("write-memory %d %s" % (addr, " ".join("%dH" % x if False else str(x) for x in data)), 0.05)   # ZRCP values are DECIMAL (space-separated)
    def grab(self):
        return self.rd(16384, 6912)
    def png(self, path):
        scr = self.grab()
        if scr: scr_to_png(scr, str(path))
        return scr
    def keys(self, keys=(), joy=0, hold=0.12, gap=0.25):
        self.cmd("set-ui-io-ports " + ports(keys, joy), 0.05); time.sleep(hold)
        self.cmd("set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def hold(self, keys=(), joy=0):
        self.cmd("set-ui-io-ports " + ports(keys, joy), 0.05)
    def release(self):
        self.cmd("set-ui-io-ports " + ports(), 0.05)
    def close(self):
        try: zrcp(self.s, "exit-emulator", 0.3); self.s.close()
        except Exception: pass
        try: self.p.wait(timeout=5)
        except subprocess.TimeoutExpired: self.p.kill()
