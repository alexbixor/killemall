#!/usr/bin/env python3
"""m25b_zes.py - ZEsarUX (real 48K ROM, real timing) run of the M2.5 step B tape: menu -> START; live fps at the start view
(>= 8); still of the live start view (ceiling dots + mirrored lines) -> build/m25b_zes_start.png; a short forward walk with a
grab every 0.25 s -> build/m25b_zes_walk_<n>.png (proves the ceiling lines flow with the floor lines on the real ROM/timing).
usage: m25b_zes.py [tap]   exit 1 on a failed check."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m25.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += not ok
z = Zes(tap, port=10187, log="/tmp/zes_m25b.log")
print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(0.8)
def fps(secs=3.0):
    f0 = z.rd16(SYM["frames"]); time.sleep(secs); f1 = z.rd16(SYM["frames"])
    return ((f1 - f0) & 0xFFFF) / secs
f_live = fps(); print("start view, live level: %.1f fps" % f_live)
check(f_live >= 8.0, "fps floor 8 at the start view (got %.1f)" % f_live)
z.png(ROOT / "build/m25b_zes_start.png")
# the live frame straight from the SCREEN (the back buffer is being rewritten while we read it): the window's left byte
# column (screen x 64..71 = byte 8) rows 8..103; the left edge of the start view is open corridor (far wall small, no sprite).
# A screen column grab is one frame (COPYBUF copies a column in one burst) -> rows are consistent inside a column.
def scr_col(byte=4):
    scr = z.grab(); out = []
    for y in range(8, 104):
        out.append(scr[((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + byte])
    return out                           # index = window row 0..95
# wall span per byte column from the live zbuf (static view -> stable): rows 48-h/2 .. 47+h/2 are wall, the rest is open
zb = z.rd(SYM["zbuf"], 64)
best = None
RAYS_OF = ([0, 1, 2], [3, 4], [5, 6, 7])                          # M2.5C: rays of byte column bc
def lat_c(r): return 0x01 if r % 4 == 2 else 0x00                                         # M2.5E ceiling lattice: dot rows 46-4k (x=7)
def lat_f(r): return ((0x01 if ((r - 49) // 2) % 2 == 0 else 0x10) if r % 2 else 0x00)    # floor: odd row 49+2w, x=7 (even w) / x=3 (odd w)
for bc in range(24):
    h = min(max(zb[8 * (bc // 3) + r] for r in RAYS_OF[bc % 3]), 96); top, bot = 48 - h // 2, 48 + h // 2
    col = scr_col(4 + bc)
    dots = sum(1 for r in range(0, top) if col[r] == lat_c(r))
    fdots = sum(1 for r in range(bot, 96) if col[r] == lat_f(r))                            # live zombies: a sprite-covered column loses
    if best is None or dots + fdots > best[0]: best = (dots + fdots, dots, bc, top, bot, col)
_, dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
wrong = [r for r in range(0, top) if col[r] != (0xFF if r in lines_c else lat_c(r))]
wrong_f = [r for r in range(bot, 96) if col[r] != (0xFF if r in lines_f else lat_f(r))]
print("screen byte col %d (wall rows %d..%d): ceiling lattice rows %d/%d, ceiling line rows %s, floor line rows %s, off-pattern rows ceiling %s floor %s" % (4 + bc, top, bot - 1, dots, top, lines_c, lines_f, wrong, wrong_f))
check(top >= 8 and len(wrong) <= 2, "live screen col %d: the open ceiling rows are the lattice or lines (%d lattice + %d lines of %d rows, %d off)" % (4 + bc, dots, len(lines_c), top, len(wrong)))
check(len(wrong_f) <= 2, "live screen col %d: the open floor rows are the lattice (0x01/0x10 on odd rows, diamonds) or lines (%d off)" % (4 + bc, len(wrong_f)))
mirror = sorted(46 - 2 * ((r - 49) // 2) for r in lines_f if r % 2 == 1 and 46 - 2 * ((r - 49) // 2) < top)   # floor odd row 49+2w <-> ceiling even row 46-2w
lc = sorted(r for r in lines_c if 49 + (46 - r) >= bot)
if lc != mirror: print("  column dump rows 0..95:", " ".join("%02X" % v for v in col))
check(lc == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s (open part)" % (lc, mirror))
# walk forward 1.2 s, grabbing 4 frames
z.hold(["Q"])
for n in range(4):
    time.sleep(0.25)
    z.png(ROOT / ("build/m25b_zes_walk_%d.png" % n))
z.release(); time.sleep(0.2)
fph = z.rd(SYM["fl_ph"], 1)[0]
print("after walk: fl_ph %d" % fph)
check(fph != 0, "walking advanced the line phase (fl_ph %d)" % fph)
z.close()
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
