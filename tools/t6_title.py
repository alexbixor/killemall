#!/usr/bin/env python3
"""t6_title.py - load a tape in ZEsarUX 48K with a breakpoint at PC=32768 (start): grab the screen at that moment (must be
the title screen: proves the SCREEN$ block loaded and survived the code load), then continue and grab again.
usage: t6_title.py tap out_title.png [out_running.png]"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import t6_zes
from t6_zes import Zes

class ZesBP(Zes):
    def __init__(self, tap, port):
        self.extra = ["--enable-breakpoints", "--set-breakpoint", "1", "PC=8000H"]
        super().__init__(tap, port=port)

# inject the extra args: patch the class constructor through a tiny wrapper around subprocess.Popen
import subprocess
_orig = subprocess.Popen
def _popen(cmd, *a, **k):
    if cmd and str(cmd[0]).endswith("zesarux"):
        cmd = cmd[:1] + ["--enable-breakpoints", "--set-breakpoint", "1", "PC=8000H"] + cmd[1:]
    return _orig(cmd, *a, **k)
subprocess.Popen = _popen

def main():
    tap, out = sys.argv[1], sys.argv[2]
    z = Zes(tap, port=10151)
    t0 = time.time(); title = pathlib.Path("build/title.scr").read_bytes(); got = False
    while time.time() - t0 < 90:
        if z.pc() == 0x8000:
            got = True; break
        time.sleep(0.3)
    print("breakpoint at start reached: %s after %.1f s" % (got, time.time() - t0))
    scr = z.png(out)
    eq_pix = scr[:6144] == title[:6144]; eq_attr = scr[6144:] == title[6144:]
    print("screen at start == title.scr: pixels %s attrs %s -> %s" % (eq_pix, eq_attr, out))
    z.cmd("disable-breakpoints", 0.2); z.cmd("exit-cpu-step", 0.3)
    time.sleep(2.5)
    print("PC now %04X" % z.pc())
    if len(sys.argv) > 3:
        z.png(sys.argv[3]); print("saved", sys.argv[3])
    z.close()
    print("RESULT", "PASS" if got and eq_pix and eq_attr else "FAIL")

if __name__ == "__main__":
    main()
