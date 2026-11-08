#!/usr/bin/env python3
"""nx_test_hud_digits.py - HF1 (8 Nov 2026): read the HUD band digits back from the LoRes frame and compare them with the game
variables. Lane N6 found that killemall_b.nex drew "094 / 94 / 94" for HEALTH / AMMO / KILLS (hud_field_clear returns A = 94 and
the N4 painters used that A as the value); the N4/N5 oracles compared frames, never values. This oracle decodes the 3x5 font at
rows 89..93 (hud_next.asm hud_font) for the HEALTH (columns 2..13, 3 digits), AMMO (44..51, 2 digits) and KILLS (84..91, 2 digits)
fields and requires them to equal g_health / g_ammo / g_kills, at the start pose and again after a change (ammo after a shot).
Usage: .venv/bin/python tools/nx_test_hud_digits.py build/next/killemall_b.nex [--expect-bug]   -> RESULT PASS / FAIL"""
import sys, time, pathlib
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from nx_run import NexRun
FONT = {0: (0xE0,0xA0,0xA0,0xA0,0xE0), 1: (0x40,0xC0,0x40,0x40,0xE0), 2: (0xE0,0x20,0xE0,0x80,0xE0), 3: (0xE0,0x20,0x60,0x20,0xE0),
        4: (0xA0,0xA0,0xE0,0x20,0x20), 5: (0xE0,0x80,0xE0,0x20,0xE0), 6: (0xE0,0x80,0xE0,0xA0,0xE0), 7: (0xE0,0x20,0x20,0x20,0x20),
        8: (0xE0,0xA0,0xE0,0xA0,0xE0), 9: (0xE0,0xA0,0xE0,0x20,0xE0)}
GLYPH = {v: k for k, v in FONT.items()}
G_HEALTH, G_AMMO, G_KILLS = 0x5DB0, 0x5DB1, 0x5DB3
SCR_BOT, HUD_ROW = 0x6000, 88

def digits(frame, col0, n, band):
    """decode n 3x5 glyphs starting at LoRes column col0, rows 89..93 (frame = 12288 bytes 128x96); band = band colour"""
    out = []
    for d in range(n):
        g = []
        for r in range(5):
            row = frame[(HUD_ROW + 1 + r) * 128: (HUD_ROW + 2 + r) * 128]
            bits = 0
            for c in range(3):
                px = row[col0 + 4 * d + c]
                if px != band: bits |= 0x80 >> c
            g.append(bits)
        out.append(GLYPH.get(tuple(g), None))
    return out

def val(ds):
    if any(x is None for x in ds): return None
    v = 0
    for x in ds: v = v * 10 + x
    return v

def main():
    nex = sys.argv[1]; expect_bug = "--expect-bug" in sys.argv
    checks = []
    def check(ok, msg): checks.append(ok); print(("ok   " if ok else "FAIL ") + msg)
    with NexRun(nex) as r:
        r.wait_pc_in(0x8000, 0xC000, 30); time.sleep(2.0)
        for attempt in range(6):
            f = r.screen(); h, a, k = r.byte(G_HEALTH), r.byte(G_AMMO), r.byte(G_KILLS)
            if len(f) == 12288 and h >= 0: break
            time.sleep(0.5)
        band = f[HUD_ROW * 128]                       # band colour = first pixel of row 88
        dh, da, dk = val(digits(f, 2, 3, band)), val(digits(f, 44, 2, band)), val(digits(f, 84, 2, band))
        print("start pose: vars health %d ammo %d kills %d ; HUD reads health %s ammo %s kills %s (band colour %d)" % (h, a, k, dh, da, dk, band))
        if expect_bug:
            check((dh, da, dk) == (94, 94, 94), "shipped-bug build reads 094 / 94 / 94 (the reproduction)")
        else:
            check(dh == h, "HEALTH digits == g_health (%s vs %d)" % (dh, h))
            check(da == a, "AMMO digits == g_ammo (%s vs %d)" % (da, a))
            check(dk == k, "KILLS digits == g_kills (%s vs %d)" % (dk, k))
            # change a value through the game: write g_health = 37 and invalidate the shadow so the field repaints. Enemies keep
            # hitting the player at the start pose, so compare with the variable read next to the frame grab, not with 37.
            r.wr(G_HEALTH, [37]); r.wr(0x5EC1, [0xFF]); time.sleep(0.6)
            f = r.screen(); h2 = r.byte(G_HEALTH); dh2 = val(digits(f, 2, 3, band))
            check(dh2 == h2 and h2 != 100, "after g_health := 37 + shadow invalidated: HUD reads %s, g_health %d at the grab" % (dh2, h2))
            r.wr(G_AMMO, [8]); r.wr(0x5EC3, [0xFF]); time.sleep(0.6)
            f = r.screen(); a2 = r.byte(G_AMMO); da2 = val(digits(f, 44, 2, band))
            check(da2 == a2 and a2 != 50, "after g_ammo := 8 + shadow invalidated: HUD reads %s, g_ammo %d at the grab" % (da2, a2))
    n = sum(1 for c in checks if not c)
    print("RESULT %s %d checks" % ("PASS" if n == 0 else "FAIL %d" % n, len(checks)))
    return 1 if n else 0

if __name__ == "__main__":
    sys.exit(main())
