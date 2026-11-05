#!/usr/bin/env python3
"""levels128.py - prove the bank-1 level chain on the 128K: start the game, teleport next to the exit, walk into it ->
LEVEL CLEARED -> shim load_level copies level 2 (then 3) from bank 1 (no tape); check level_data[0], level, AY still
playing, paging back to bank 0 after each switch; clearing level 3 -> menu. Output -> build/levels128.out"""
import sys, time, pathlib, os, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import t6_zes
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall128_m2.tap")
SYM = load_sym(str(ROOT / "build/kea128.sym"))
LOG = open(ROOT / "build/levels128.out", "w")
def log(*a): print(*a, file=LOG, flush=True)

# patch the machine argument: t6_zes hard-codes 48k -> rewrite the command list via a small wrapper around Popen
_orig_popen = t6_zes.subprocess.Popen
def popen128(cmd, *a, **k):
    cmd = ["128k" if (i > 0 and cmd[i - 1] == "--machine") else c for i, c in enumerate(cmd)]
    return _orig_popen(cmd, *a, **k)
t6_zes.subprocess.Popen = popen128

def exit_cell(ld):
    cells = ld[9:9 + 1024]
    return [(i % 32, i // 32) for i, c in enumerate(cells) if c == 12]
def pages(z):
    return z.cmd("get-memory-pages").strip()
def ay(z):
    r = z.cmd("get-io-ports")
    m7 = re.search(r"7FFD port: (\w+)", r); vols = re.findall(r"\n\s*0[89A]:\s+([0-9A-F]{2})", r)
    return "7FFD %s vols %s" % (m7.group(1) if m7 else "?", vols)
def state(z, tag):
    ld = z.rd(SYM["level_data"], 9)
    log("%s: level_data id %d start (%d,%d) things %d | level %d health %d PC %04X | %s | %s" % (
        tag, ld[0], ld[5], ld[6], ld[8], z.rd(SYM["level"], 1)[0], z.rd(SYM["health"], 1)[0], z.pc(), pages(z), ay(z)))
def clear_level(z, tag):
    ld = z.rd(SYM["level_data"], 9 + 1024); ex = exit_cell(ld)[0]; cells = ld[9:9 + 1024]
    for dx, dy, ang in ((-1, 0, 0), (1, 0, 128), (0, -1, 64), (0, 1, 192)):
        nx, ny = ex[0] + dx, ex[1] + dy
        if 0 <= nx < 32 and 0 <= ny < 32 and cells[ny * 32 + nx] == 0: break
    log("%s: exit at %s, standing at (%d,%d) facing %d" % (tag, ex, nx, ny, ang))
    z.wr(SYM["posx"], [0x80, nx]); z.wr(SYM["posy"], [0x80, ny]); z.wr(SYM["angle"], [ang]); z.wr(SYM["health"], [100])
    time.sleep(0.5); z.hold(["Q"]); time.sleep(1.5); z.release()
    cur = z.rd(SYM["level_data"], 1)[0]; t0 = time.time()
    while time.time() - t0 < 20 and z.rd(SYM["level_data"], 1)[0] == cur: time.sleep(0.5)
    time.sleep(2.0)

z = Zes(tap, port=10171)
log("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(1.0)
z.keys(["SPACE"], hold=0.2, gap=1.5); time.sleep(1.0)
state(z, "level 1 start")
clear_level(z, "clear 1"); state(z, "after clear 1 (expect id 2 from bank 1)"); z.png(ROOT / "build/kea128_level2.png")
clear_level(z, "clear 2"); state(z, "after clear 2 (expect id 3)"); z.png(ROOT / "build/kea128_level3.png")
clear_level(z, "clear 3"); state(z, "after clear 3 (expect menu)")
log("menu loop (halt -> PC at IM2 vector FDFD):", z.pc() == 0xFDFD)
z.keys(["SPACE"], hold=0.2, gap=1.5); time.sleep(2.0)
state(z, "START again (expect level 1 id 1 copied back from bank 1)")
z.close(); log("done")
