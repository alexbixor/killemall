#!/usr/bin/env python3
"""m26_prescaled_budget.py - E2 design numbers: pre-scaled banked sprites for the 128K edition.
For each candidate size list, the bytes needed for 2 planes (pixels + mask) of every enemy frame (8) and item (6) at every
size, byte-aligned width + 1 spare byte (run-time shift by table), and the blit cost estimate per instance at a given hv.
Engine facts (sprites_e/f.asm, m25e_sprite_mock2.py): drawn height hd = enemy_h(hv) = hv - hv//4 + hv//16; art 16x24 (2:3) so
width = hd*2/3 px; items use the same scaler with their own aspect (16x16 -> square, height hd//2 ... approximated as hd*2/3).
Blit cost model (table shift, per output byte): 2 planes x (ld a,(de) 7 + ld l,a 4 + ld a,(hl) 7 + or c 4 + ...) ~ 70 T +
screen RMW 22 T + pointers 12 T = ~105 T; per row 30 T overhead. Today's measured cost: zombie at 1.0 cell +68k T."""
import math
def enemy_h(hv): return hv - hv // 4 + hv // 16
def frame_bytes(hv, aspect=2 / 3.0, spare=1):
    hd = enemy_h(hv); w = max(1, int(round(hd * aspect)))
    wb = (w + 7) // 8 + spare
    return hd, w, wb, wb * hd * 2
def blit_cost(hv, aspect=2 / 3.0):
    hd, w, wb, _ = frame_bytes(hv, aspect)
    return wb * hd * 105 + hd * 30
for name, sizes in (("12 sizes", [12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96]),
                    ("16 sizes", [12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 96, 112, 128]),
                    ("20 sizes", [12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 80, 88, 96, 112, 128])):
    enemy = sum(frame_bytes(hv)[3] for hv in sizes) * 8
    items = sum(frame_bytes(hv, 2 / 3.0)[3] for hv in sizes if hv <= 64) * 6
    print("%s: enemies 8 frames %d B, items 6 (<=hv64) %d B, total %d B = %.1f banks of 16K (+4 KB shift tables)" % (
        name, enemy, items, enemy + items, (enemy + items + 4096) / 16384.0))
print("per size (hv -> drawn h, w px, bytes/row incl spare, bytes 2 planes, est blit T, vs today):")
today = {24: 9000, 40: 21000, 64: 42000, 96: 68000}      # m25e_sprite_cost: 2.5 cells +9k? (not measured) ; 1.5 cells +42k; 1.0 cell +68k
for hv in (16, 24, 32, 40, 48, 64, 80, 96, 128):
    hd, w, wb, b = frame_bytes(hv)
    print("  hv %3d -> h %3d w %3d px, %d B/row, %4d B, blit ~%6d T%s" % (hv, hd, w, wb, b, blit_cost(hv), (" (today +%dk)" % (today[hv] // 1000)) if hv in today else ""))
