#!/usr/bin/env python3
"""mmc_ls.py - list the root directory (FAT16) of a ZEsarUX tbblue.mmc / SD image. usage: mmc_ls.py image [subdir]"""
import struct, sys
f = open(sys.argv[1], "rb")
f.seek(446); e = f.read(16); lba = struct.unpack_from("<I", e, 8)[0]
f.seek(lba * 512); bs = f.read(512)
bps = struct.unpack_from("<H", bs, 11)[0]; spc = bs[13]; res = struct.unpack_from("<H", bs, 14)[0]; nf = bs[16]
re_ = struct.unpack_from("<H", bs, 17)[0]; fsz = struct.unpack_from("<H", bs, 22)[0]
print("partition lba", lba, "OEM", bs[3:11], "bps", bps, "spc", spc, "reserved", res, "fats", nf, "root entries", re_, "fat size", fsz, "label", bs[43:54], bs[54:62])
root = lba * 512 + (res + nf * fsz) * bps
data0 = root + re_ * 32
def listdir(off, n):
    f.seek(off); rd = f.read(n); out = []
    for i in range(0, len(rd), 32):
        e = rd[i:i + 32]
        if e[0] == 0: break
        if e[0] == 0xE5 or e[11] & 0x08 or e[11] == 0x0F: continue
        nm = e[:8].decode("latin1").strip() + ("." + e[8:11].decode("latin1").strip() if e[8:11].strip() else "")
        clu = struct.unpack_from("<H", e, 26)[0]
        out.append((nm, "DIR" if e[11] & 0x10 else struct.unpack_from("<I", e, 28)[0], clu))
    return out
ents = listdir(root, re_ * 32)
print(len(ents), "root entries:", [(n, s) for n, s, c in ents])
if len(sys.argv) > 2:
    for n, s, c in ents:
        if n.upper() == sys.argv[2].upper() and s == "DIR":
            sub = listdir(data0 + (c - 2) * spc * bps, spc * bps)
            print(sys.argv[2], "->", [(a, b) for a, b, _ in sub])
