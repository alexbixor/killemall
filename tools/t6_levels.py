#!/usr/bin/env python3
"""t6_levels.py - prove the tape level chain in ZEsarUX: start the game, teleport next to the exit cell, walk into it ->
LEVEL CLEARED -> load_level pulls level 2 (then 3) from the tape blocks; check level_data[0], level, posx/posy; then clear
level 3 -> back to the menu. usage: t6_levels.py [tap]"""
import sys, time, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
SYM = load_sym(os.environ.get("SYM", str(ROOT / "build/kea48.sym")))

def exit_cell(ld):
    cells = ld[9:9 + 1024]
    return [(i % 32, i // 32) for i, c in enumerate(cells) if c == 12]

def state(z, tag):
    ld = z.rd(SYM["level_data"], 9)
    print("%s: level_data id %d start (%d,%d) ang %d things %d | level %d pos (%d.%02X,%d.%02X) health %d PC %04X" % (
        tag, ld[0], ld[5], ld[6], ld[7], ld[8], z.rd(SYM["level"], 1)[0], z.rd(SYM["posx"], 2)[1], z.rd(SYM["posx"], 2)[0],
        z.rd(SYM["posy"], 2)[1], z.rd(SYM["posy"], 2)[0], z.rd(SYM["health"], 1)[0], z.pc()))

def clear_level(z, tag):
    ld = z.rd(SYM["level_data"], 9 + 1024)
    ex = exit_cell(ld)[0]
    # find an open neighbour cell of the exit and face it
    cells = ld[9:9 + 1024]
    for dx, dy, ang in ((-1, 0, 0), (1, 0, 128), (0, -1, 64), (0, 1, 192)):
        nx, ny = ex[0] + dx, ex[1] + dy
        if 0 <= nx < 32 and 0 <= ny < 32 and cells[ny * 32 + nx] == 0:
            break
    print("%s: exit at %s, standing at (%d,%d) facing %d" % (tag, ex, nx, ny, ang))
    z.wr(SYM["posx"], [0x80, nx]); z.wr(SYM["posy"], [0x80, ny]); z.wr(SYM["angle"], [ang])
    z.wr(SYM["health"], [100])
    time.sleep(0.5)
    z.hold(["Q"]); time.sleep(1.5); z.release()          # walk forward into the exit (bump -> level_clear)
    t0 = time.time()
    while time.time() - t0 < 60:                          # LEVEL CLEARED 2 s + tape load (ZEsarUX fast load)
        ld = z.rd(SYM["level_data"], 1)
        if ld and ld[0] != (ex, ) and z.rd(SYM["level"], 1)[0] != cur[0]:
            pass
        time.sleep(0.5)
        if z.rd(SYM["level_data"], 1)[0] != cur[0] or time.time() - t0 > 20:
            break
    time.sleep(3.0)

z = Zes(tap, port=10161)
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(1.0)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.0)
state(z, "level 1 start")
cur = z.rd(SYM["level_data"], 1)
clear_level(z, "clear 1"); state(z, "after clear 1"); z.png(ROOT / "build/m2_level2.png")
cur = z.rd(SYM["level_data"], 1)
clear_level(z, "clear 2"); state(z, "after clear 2"); z.png(ROOT / "build/m2_level3.png")
cur = z.rd(SYM["level_data"], 1)
clear_level(z, "clear 3"); state(z, "after clear 3 (expect menu)")
print("menu loop (CPU halted -> PC sampled at the IM2 vector 0xFDFD):", z.pc() == 0xFDFD, " fe_cur", z.rd(SYM["fe_cur"], 1).hex())
z.png(ROOT / "build/m2_menu_after.png")
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(2.0)
state(z, "START again (expect level 1 reloaded from tape: id 1)")
z.close()
