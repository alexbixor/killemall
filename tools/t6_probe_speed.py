#!/usr/bin/env python3
"""t6_probe_speed.py - measure ZRCP round-trip costs on port 10170 (fast reader, no fixed sleeps), game fps via `frames`,
50 Hz `ticks`, angle sign of O/P, key latency. Read-only probe, kills only its own emulator."""
import sys, time, pathlib, socket
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym, ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
SYM = load_sym(str(ROOT / "build/kea48.sym"))
tap = str(ROOT / "build/killemall48_m2.tap")

class Fast(Zes):
    def cmd(self, c, wait=0.0):
        self.s.sendall((c + "\n").encode()); out = b""; self.s.settimeout(3.0)
        while not out.rstrip().endswith(b"command>"):
            ch = self.s.recv(65536)
            if not ch: break
            out += ch
        return out.decode(errors="replace").split("command>")[0]
    def rd(self, addr, n):
        r = self.cmd("read-memory %d %d" % (addr, n))
        h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:2 * n]
        return bytes.fromhex(h) if len(h) == 2 * n else b""
    def wr(self, addr, data):
        self.cmd("write-memory %d %s" % (addr, " ".join(str(x) for x in data)))
    def hold(self, keys=(), joy=0):
        self.cmd("set-ui-io-ports " + ports(keys, joy))
    def release(self):
        self.cmd("set-ui-io-ports " + ports())

z = Fast(tap, port=10170, log="/tmp/zes_probe.log")
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"]), flush=True)
time.sleep(0.5)
for n in (5, 128, 6912):
    t0 = time.time(); b = z.rd(16384 if n == 6912 else SYM["posx"], n); dt = time.time() - t0
    print("rd %d bytes: %.1f ms (got %d)" % (n, dt * 1000, len(b)))
t0 = time.time()
for _ in range(10): z.rd(SYM["posx"], 5)
print("10x rd5: %.1f ms each" % ((time.time() - t0) * 100))
# ticks rate
tk0 = z.rd16(SYM["ticks"]); t0 = time.time(); time.sleep(2.0); tk1 = z.rd16(SYM["ticks"]); dt = time.time() - t0
print("ticks/s = %.1f (50 expected)" % (((tk1 - tk0) & 0xFFFF) / dt))
# start the game
z.cmd("set-ui-io-ports " + ports(["SPACE"])); time.sleep(0.15); z.release(); time.sleep(1.0)
p = z.rd(SYM["posx"], 5); print("pos", p.hex(), "level_data id", z.rd(SYM["level_data"], 1).hex())
f0 = z.rd16(SYM["frames"]); t0 = time.time(); time.sleep(2.0); f1 = z.rd16(SYM["frames"]); dt = time.time() - t0
print("game fps = %.2f" % (((f1 - f0) & 0xFFFF) / dt))
# angle sign: hold O 0.3 s
a0 = z.rd(SYM["angle"], 1)[0]; z.hold(["O"]); time.sleep(0.3); z.release(); time.sleep(0.2); a1 = z.rd(SYM["angle"], 1)[0]
print("O (turn left): angle %d -> %d" % (a0, a1))
z.hold(["P"]); time.sleep(0.3); z.release(); time.sleep(0.2); a2 = z.rd(SYM["angle"], 1)[0]
print("P (turn right): angle %d -> %d" % (a1, a2))
# key latency: hold Q and poll posx until it changes
x0 = z.rd16(SYM["posx"]); t0 = time.time(); z.hold(["Q"])
while time.time() - t0 < 2.0:
    if z.rd16(SYM["posx"]) != x0: break
print("Q latency: %.0f ms" % ((time.time() - t0) * 1000)); z.release()
print("things:", z.rd(SYM["things"], 128).hex())
print("state h/a/k/kills/level:", z.rd(SYM["health"], 5).hex())
z.close()
print("closed")
