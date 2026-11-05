#!/usr/bin/env python3
"""mklevelblk.py - make a raw tape block for kea48's load_level from a tools/mapc.py output (count byte + one level
body of 8 + 1024 + 3*n_things bytes): output = id byte (1..3) + body, zero-padded to LEVEL_BLK bytes = the fixed layout
of level_data (byte 0 = 1 for the resident level 1 = mapc's count byte). usage: mklevelblk.py in.bin id out.blk"""
import sys, pathlib
LEVEL_BLK = 1 + 8 + 1024 + 3 * 16          # 1081: id + header + cells + up to 16 things
d = pathlib.Path(sys.argv[1]).read_bytes(); lid = int(sys.argv[2])
assert d[0] == 1 and d[1] == 75 and len(d) <= LEVEL_BLK, "expected mapc.py 48k output with exactly one level (<= 16 things)"
out = (bytes([lid]) + d[1:]).ljust(LEVEL_BLK, b"\0")
pathlib.Path(sys.argv[3]).write_bytes(out)
print("%s: %d bytes (level %d B), id %d, start (%d,%d) angle %d things %d" % (sys.argv[3], len(out), len(d) - 1, lid, d[5], d[6], d[7], d[8]))
