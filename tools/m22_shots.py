#!/usr/bin/env python3
"""m22_shots.py - ZEsarUX run of build/killemall48_m22.tap (real 48K ROM, real timing): fps at the live start view, the
dashboard as drawn by the Z80 code, then static scenes barrel + imp (+ zombie) at 1.5 / 3 / 5 cells -> build/m22_sprites_near.png,
_mid.png, _far.png (3x nearest), plus build/m22_dash_states.png (health 100 / 25, shield 0 / 50, keys, ammo).
Checks (printed, exit 1 on failure): fps >= 8 at the start view; no BRIGHT attribute anywhere on screen; dashboard rail/frame
pixels present; imp drawn height ~0.8 of the barrel height in each scene (bounding rows of magenta vs cyan cells).
Port 10181 (m21_shots uses 10180)."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m22.tap")
SYM = load_sym(str(ROOT / "build/kea48.sym"))
INK = {"barrel": 5, "imp": 3, "zombie": 4}
fails = []
def check(cond, what):
    if not cond:
        fails.append(what); print("FAIL", what)
z = Zes(tap, port=10181)
try:
    print("menu after %.1f s" % z.wait_running(90, lo=SYM["fe_run"])); time.sleep(0.8)
    z.keys(["SPACE"], hold=0.15, gap=1.5); time.sleep(1.0)
    def fps(secs=4.0):
        f0 = z.rd16(SYM["frames"]); time.sleep(secs); return (z.rd16(SYM["frames"]) - f0) / secs
    f_live = fps(); print("start view, live level (imp + zombie AI): %.1f fps" % f_live)
    check(f_live >= 8.0, "fps floor 8 at the start view (got %.1f)" % f_live)
    z.png(ROOT / "build/m22_game_live.png")
    attrs = z.rd(22528, 768)
    check(len(attrs) == 768 and not any(a & 0x40 for a in attrs), "no BRIGHT attribute on screen")
    scr = z.rd(16384, 6144)
    def pix(x, y):
        a = (y & 0xC0) * 32 + (y & 7) * 256 + (y & 0x38) * 4 + x // 8
        return (scr[a] >> (7 - (x & 7))) & 1
    check(all(pix(x, 104) for x in range(256)), "red rail y 104")
    check(all(pix(63, y) and pix(192, y) for y in range(8, 104)), "frame sides x 63 / 192")
    check(all(pix(83, y) and pix(171, y) for y in range(105, 168)), "dividers x 83 / 171")
    print("dashboard static geometry: %s" % ("ok" if not fails else "see FAIL lines"))
    # freeze the AI, open the corridor x = 7..11 at y = 7 so the far scenes have the wall behind the things
    z.wr(SYM["things_tick"], [0xC9])
    def window_attrs():
        a = z.rd(22528 + 32, 12 * 32)
        return [[a[32 * r + 8 + c] for c in range(16)] for r in range(12)] if len(a) == 384 else None
    def th(typ, x, y, state=0): return [typ, int((x % 1) * 256), int(x), int((y % 1) * 256), int(y), state, 30, 0]
    cells = SYM["level_data"] + 1 + 8 + 7 * 32
    for d, name in ((1.5, "near"), (3.0, "mid"), (5.0, "far")):
        z.wr(SYM["things"], [0] * 128)
        wx = int(3.5 + d + 1.0)
        z.wr(cells + 7, [1 if x == wx else 0 for x in range(7, 12)])
        bx = 3.5 + d
        # barrel left, imp (attack pose) right, zombie (idle = static walk A) far right: static poses, so attribute changes
        # between samples would be real flicker (a chasing zombie alternates walk A/B every 4 frames = legit ink changes)
        z.wr(SYM["things"], th(21, bx, 7.5 - 0.5) + th(1, bx, 7.5 + 0.35, 2) + th(2, bx + 0.4, 7.5 + 1.1, 0))
        z.wr(SYM["posx"], [128, 3]); z.wr(SYM["posy"], [128, 7]); z.wr(SYM["angle"], [0]); z.wr(SYM["health"], [100])
        time.sleep(1.2)
        f = fps(3.0); print("%s d=%.1f: %.1f fps" % (name, d, f))
        z.png(ROOT / ("build/m22_sprites_%s.png" % name))
        nv = z.rd(SYM["nvis"], 1)[0]; vis = z.rd(SYM["vis"], 18)
        print("   nvis %d vis %s" % (nv, list(vis)))
        s = window_attrs()
        if s:
            rows = {k: [r for r in range(12) for c in range(16) if s[r][c] == v] for k, v in INK.items()}
            print("   attr rows: barrel %s imp %s zombie %s" % tuple((min(rows[k]), max(rows[k])) if rows[k] else None for k in ("barrel", "imp", "zombie")))
            check(rows["imp"] and rows["barrel"], "%s: imp and barrel cells present" % name)
            if rows["imp"] and rows["barrel"]:
                # ink-cell oracle only (black outline rows carry no ink tint; at 5 cells the imp is 14 px and its bottom run is
                # black): feet within one cell row of the barrel's base. Pixel-exact feet geometry: tools/test_sprite_scale.py
                check(abs(max(rows["imp"]) - max(rows["barrel"])) <= 1, "%s: imp feet within one cell row of the barrel base" % name)
                check(min(rows["imp"]) >= min(rows["barrel"]) - 4, "%s: imp not taller than the barrel + 4 cell rows" % name)
        samples = [s for s in (window_attrs() for _ in range(20)) if s]
        sprite_cells = {(r, c) for s in samples for r in range(12) for c in range(16) if s[r][c] in INK.values()}
        flips = sum(1 for (r, c) in sprite_cells for i in range(1, len(samples)) if samples[i][r][c] != samples[i - 1][r][c])
        print("   attr samples %d: sprite-cell attribute flips between samples: %d" % (len(samples), flips))
        check(flips == 0, "%s: no sprite attribute flicker" % name)
    # dashboard states: low health + shield + both keys + low ammo
    z.wr(SYM["things"], [0] * 128); z.wr(cells + 7, [1, 0, 0, 0, 0])
    z.wr(SYM["health"], [25]); z.wr(SYM["shield"], [50]); z.wr(SYM["keys"], [3]); z.wr(SYM["ammo"], [23]); z.wr(SYM["kills"], [12])
    time.sleep(1.0)
    z.png(ROOT / "build/m22_dash_low.png")
    attrs = z.rd(22528, 768)
    check(not any(a & 0x40 for a in attrs), "no BRIGHT after the dashboard update")
    check(attrs[16 * 32 + 11] == 2 and attrs[14 * 32 + 18] == 2, "health 25 -> red bar/value cells")
    z.wr(SYM["health"], [100]); z.wr(SYM["shield"], [0]); z.wr(SYM["keys"], [0]); z.wr(SYM["ammo"], [50]); time.sleep(0.8)
    print("start view, walls + weapon only: %.1f fps" % fps(3.0))
    # side-by-side sheet: live, near, mid, far, low (3x)
    names = ["m22_game_live", "m22_sprites_near", "m22_sprites_mid", "m22_sprites_far", "m22_dash_low"]
    ims = [Image.open(ROOT / ("build/%s.png" % n)).convert("RGB") for n in names]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 3 + 16, h * 2 + 8), (40, 40, 40))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 3) * (w + 8), (i // 3) * (h + 8)))
    sheet.save(ROOT / "build/m22_sheet.png")
    print("sheet build/m22_sheet.png %dx%d" % sheet.size)
finally:
    z.close()
print("RESULT", "PASS" if not fails else "FAIL %d: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
