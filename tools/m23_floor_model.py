#!/usr/bin/env python3
"""m23_floor_model.py - model of the Z80 floor-line placer (fl_set): 24 floor words (window rows 48+2w, 49+2w), table
D4[w] = round(384 / w) (distance of the top edge of word w in 1/16 cell, w = 0 -> 255), phase p = 0..15 (1/16 cell walked).
Line in word w iff hi-nibble(D4[w] + p) != hi-nibble(D4[w+1] + p) and hi-nibble(D4[w+1] + p) < KMAX (nearest crossed
grid distance k <= KMAX). Prints the line rows per phase so KMAX can be chosen and the Z80 test can reuse the oracle."""
import sys
KMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 5
D4 = [255] + [min(255, round(384 / w)) for w in range(1, 25)]       # index 0..24
def lines(p, kmax=KMAX, g=8):
    out = []
    for w in range(24):
        hi_bot = ((D4[w + 1] + p) & 0xFF) & ~(g - 1)
        hi_top = ((D4[w] + p) & 0xFF) & ~(g - 1)
        if hi_bot < kmax * 16 and hi_top != hi_bot:
            out.append(w)
    return out
if __name__ == "__main__":
    print("D4:", D4)
    for p in range(0, 16, 1):
        ws = lines(p)
        print("phase %2d/16: words %-28s rows %s" % (p, ws, [49 + 2 * w for w in ws]))