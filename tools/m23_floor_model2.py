#!/usr/bin/env python3
"""m23_floor_model2.py - variant model: grid spacing G (16 = 1 cell, 8 = half cell) and far limit LIM (1/16 cell): a line in
word w iff (D4[w+1]+p) // G != (D4[w]+p) // G and D4[w+1]+p < LIM. Prints rows per phase for a few variants."""
from m23_floor_model import D4
def lines(p, G, LIM):
    return [w for w in range(24) if ((D4[w + 1] + p) // G) != ((D4[w] + p) // G) and (D4[w + 1] + p) < LIM]
for G, LIM in ((16, 64), (8, 48), (8, 56), (8, 64)):
    print("== spacing %s cell, lines nearer than %.1f cells" % ("1" if G == 16 else "1/2", LIM / 16))
    for p in (0, 4, 8, 12):
        ws = lines(p, G, LIM); print("  phase %2d: rows %s" % (p, [49 + 2 * w for w in ws]))