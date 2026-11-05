#!/usr/bin/env python3
"""nx_run.py - run a .nex headless in ZEsarUX (Spectrum Next / TBBlue, true 28 MHz) and talk to it over ZRCP.

    from nx_run import NexRun
    with NexRun("build/next/test.nex") as r:
        r.wait_pc_in(0x8000, 0xC000)              # program running
        r.wait_byte(0x5800, 1, timeout=30)        # e.g. a 'done' flag
        print(r.w16(0x5800)); scr = r.screen()    # 12288 bytes: 128x96 palette indices (LoRes layer)
        r.png(scr, "build/next/t.png")            # palette from build/next/assets/palette.bin if present, else RRRGGGBB
        print(r.nextreg(0x07), r.q("get-cpu-turbo-speed"))

Loads the .nex with --snap (direct, no NextZXOS boot: ~1 s instead of ~40 s). Needs an absolute path (ZEsarUX chdir's
into its own folder). Flags that lift the default 14 MHz cap are included (calibration proven 4 Nov: 32 ticks ~ 28 MHz).
CLI: nx_run.py file.nex [seconds] -> prints PC samples, dumps build/next/last_screen.png"""
import sys, time, pathlib, re, random, subprocess, socket, os
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run48 import zrcp, ZES
ROOT = HERE.parent

class NexRun:
    def __init__(self, nex, log=None, extra=()):
        self.nex = str(pathlib.Path(nex).resolve()); self.extra = list(extra); self.p = None; self.s = None
        self.log = log or "/tmp/zes_nx_run_%d_%d.log" % (os.getpid(), random.randint(0, 9999))
    def __enter__(self):
        port = 10600 + random.randint(0, 200)
        cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
               "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit",
               "--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
               "--allowturbotbbluerom", "--tbblue-max-turbo-everywhere", "8", "--tbblue-max-turbo-rom", "8",
               "--snap", self.nex] + self.extra
        self.p = subprocess.Popen(cmd, stdout=open(self.log, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
        for _ in range(120):
            try: self.s = socket.create_connection(("127.0.0.1", port), timeout=1); break
            except OSError: time.sleep(0.25)
        if self.s is None: self.p.kill(); raise RuntimeError("no ZRCP connection (see %s)" % self.log)
        zrcp(self.s, "", 0.5)
        return self
    def __exit__(self, *a):
        try: zrcp(self.s, "exit-emulator", 0.3); self.s.close()
        except Exception: pass
        try: self.p.wait(timeout=5)
        except subprocess.TimeoutExpired: self.p.kill()
    def q(self, c, w=0.3): return zrcp(self.s, c, w).split("command>")[0].strip()
    def pc(self):
        m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(self.s, "get-registers", 0.15)); return int(m.group(1), 16) if m else -1
    def regs(self): return zrcp(self.s, "get-registers", 0.15).split("command>")[0]
    def rd(self, addr, n):
        out = b""
        while n > 0:
            k = min(n, 2048)
            r = zrcp(self.s, "read-memory %d %d" % (addr, k), 0.2)
            h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * k]
            if len(h) != 2 * k: return b""
            out += bytes.fromhex(h); addr += k; n -= k
        return out
    def w16(self, a):
        b = self.rd(a, 2); return (b[0] | (b[1] << 8)) if len(b) == 2 else -1
    def byte(self, a):
        b = self.rd(a, 1); return b[0] if b else -1
    def wr(self, addr, data):
        zrcp(self.s, "write-memory %d %s" % (addr, " ".join("%02X" % b for b in data)), 0.1)
    def nextreg(self, r): return self.q("tbblue-get-register %d" % r, 0.2)
    def screen(self):
        top = self.rd(0x4000, 6144); bot = self.rd(0x6000, 6144)
        return top + bot if len(top) == 6144 and len(bot) == 6144 else b""
    def wait_pc_in(self, lo, hi, timeout=20):
        t = time.time()
        while time.time() - t < timeout:
            if lo <= self.pc() < hi: return True
            time.sleep(0.2)
        return False
    def wait_byte(self, addr, value, timeout=30):
        t = time.time()
        while time.time() - t < timeout:
            if self.byte(addr) == value: return True
            time.sleep(0.2)
        return False
    def keys(self, keys, hold=0.2, gap=0.3):
        from fe_shot import ports
        zrcp(self.s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(self.s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    @staticmethod
    def palette():
        p = ROOT / "build/next/assets/palette.bin"
        if p.exists() and p.stat().st_size == 512:
            b = p.read_bytes(); pal = []
            for i in range(256):
                b0, b1 = b[2 * i], b[2 * i + 1]
                r, g, bl = (b0 >> 5) & 7, (b0 >> 2) & 7, ((b0 & 3) << 1) | (b1 & 1)
                pal.append((r * 255 // 7, g * 255 // 7, bl * 255 // 7))
            return pal
        return [(((c >> 5) & 7) * 255 // 7, ((c >> 2) & 7) * 255 // 7, (c & 3) * 85) for c in range(256)]
    @staticmethod
    def png(scr, path, scale=4, pal=None):
        from PIL import Image
        pal = pal or NexRun.palette()
        im = Image.new("RGB", (128, 96)); px = im.load()
        for y in range(96):
            for x in range(128): px[x, y] = pal[scr[y * 128 + x]]
        im.resize((128 * scale, 96 * scale), Image.NEAREST).save(path); return im

if __name__ == "__main__":
    nex = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    with NexRun(nex) as r:
        t = time.time()
        while time.time() - t < secs:
            print("%5.1fs PC=%04X" % (time.time() - t, r.pc())); time.sleep(0.5)
        print("nextreg 7:", r.nextreg(7), "15h:", r.nextreg(0x15), "turbo:", r.q("get-cpu-turbo-speed"))
        scr = r.screen()
        if scr: NexRun.png(scr, ROOT / "build/next/last_screen.png"); print("wrote build/next/last_screen.png")
