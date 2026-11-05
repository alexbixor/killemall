#!/usr/bin/env python3
"""dump48.py - ASCII dump of the window pixels (every 2nd row) and the window attributes from a dumped screen."""
import pathlib, sys
scr = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/work/killemall/build/test48_scr.bin").read_bytes()

def pix(x, y):
    base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
    return (scr[base + (x >> 3)] >> (7 - (x & 7))) & 1

for y in range(8, 104, 2):
    print("%3d %s" % (y, "".join("#" if pix(x, y) else "." for x in range(64, 192))))
print("attrs (rows 1..12, cols 8..23):")
for r in range(1, 13):
    print(" ".join("%02x" % scr[0x1800 + 32 * r + c] for c in range(8, 24)))
