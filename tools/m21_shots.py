#!/usr/bin/env python3
"""m21_shots.py - ZEsarUX run of build/killemall48_m21.tap: fps at the live start view, then static scenes barrel + imp at
1.5 / 3 / 5 cells -> build/m21_sprites_near.png, _mid.png, _far.png (3x nearest). Port 10180.
M2.1 flicker check: for each static scene the attribute cells of the two sprites (from the Z80-side ds_amask is per sprite, so
we use the screen: cells whose attr == TYPEINK) are sampled 20x over ~1.5 s; a cell flips if its attribute changes between
samples (before ATTRBUF the wall ray loop overwrote sprite cells mid-frame -> visible flicker)."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m21.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
INK = {"barrel": 69, "imp": 67}
z = Zes(tap, port=10180)
try:
    print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
    z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.0)
    def fps(secs=4.0):
        f0 = z.rd16(SYM["frames"]); time.sleep(secs); return (z.rd16(SYM["frames"]) - f0) / secs
    f_live = fps(); print("start view, live level (imp + zombie AI): %.1f fps" % f_live)
    z.png(ROOT / "build/m21_game_live.png")
    # open the corridor x = 7..11 at y = 7 in the runtime map so far scenes have the wall behind the things; freeze the AI
    z.wr(SYM["things_tick"], [0xC9])
    def window_attrs():
        a = z.rd(22528 + 32, 12 * 32)
        return [[a[32 * r + 8 + c] for c in range(16)] for r in range(12)] if len(a) == 384 else None
    for d, name in ((1.5, "near"), (3.0, "mid"), (5.0, "far")):
        z.wr(SYM["things"], [0] * 128)
        cells = SYM["level_data"] + 1 + 8 + 7 * 32
        wx = int(3.5 + d + 1.0)
        z.wr(cells + 7, [1 if x == wx else 0 for x in range(7, 12)])
        bx = 3.5 + d
        def th(typ, x, y, state=0): return [typ, int((x % 1) * 256), int(x), int((y % 1) * 256), int(y), state, 30, 0]
        z.wr(SYM["things"], th(21, bx, 7.5 - 0.45) + th(1, bx, 7.5 + 0.45, 2))     # barrel left, imp (attack pose) right
        z.wr(SYM["posx"], [128, 3]); z.wr(SYM["posy"], [128, 7]); z.wr(SYM["angle"], [0]); z.wr(SYM["health"], [100])
        time.sleep(1.2)
        f = fps(3.0); print("%s d=%.1f: %.1f fps" % (name, d, f))
        z.png(ROOT / ("build/m21_sprites_%s.png" % name))
        nv = z.rd(SYM["nvis"], 1)[0]; vis = z.rd(SYM["vis"], 12)
        print("   nvis %d vis %s" % (nv, list(vis)))
        samples = [s for s in (window_attrs() for _ in range(20)) if s]
        sprite_cells = {(r, c) for s in samples for r in range(12) for c in range(16) if s[r][c] in INK.values()}
        flips = sum(1 for (r, c) in sprite_cells for i in range(1, len(samples)) if samples[i][r][c] != samples[i - 1][r][c])
        n_barrel = sum(1 for s in samples[:1] for r in range(12) for c in range(16) if s[r][c] == INK["barrel"])
        n_imp = sum(1 for s in samples[:1] for r in range(12) for c in range(16) if s[r][c] == INK["imp"])
        print("   attr samples %d: barrel cells %d, imp cells %d, sprite-cell attribute flips between samples: %d" % (len(samples), n_barrel, n_imp, flips))
    z.wr(SYM["things"], [0] * 128); z.wr(cells + 7, [1, 0, 0, 0, 0]); time.sleep(0.8)
    print("start view, walls + weapon only: %.1f fps" % fps(3.0))
finally:
    z.close()
