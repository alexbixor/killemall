#!/usr/bin/env python3
"""nx_nex.py - build a Spectrum Next .nex file from 16K bank images (library + CLI).

    from nx_nex import build_nex
    build_nex("build/next/test.nex", {5: screen_bytes, 2: code_bytes, 4: tables}, pc=0x8000, sp=0x5F00)

Banks are 16K bank numbers (0..111); each image is padded with zeros to 16384 bytes. No loading screen.
CLI: nx_nex.py out.nex pc_hex sp_hex bank:file [bank:file ...]      e.g.  nx_nex.py build/next/t.nex 8000 5F00 2:build/next/t.bin 5:zero
('zero' = an all-zero bank).  Assembling: pasmo --bin src.asm out.bin out.sym  (pasmo is /usr/bin/pasmo)."""
import pathlib, struct, sys

def build_nex(out, banks, pc=0x8000, sp=0x5F00):
    out = pathlib.Path(out)
    h = bytearray(512)
    h[0:4] = b"Next"; h[4:8] = b"V1.2"
    h[8] = 0                       # RAM required: 0 = 768K, 1 = 1792K
    h[9] = len(banks)              # number of 16K banks
    h[10] = 0; h[11] = 0           # no loading screen, border 0
    struct.pack_into("<H", h, 12, sp); struct.pack_into("<H", h, 14, pc); struct.pack_into("<H", h, 16, 0)
    for b in banks: h[18 + b] = 1
    h[139] = 0; struct.pack_into("<H", h, 140, 0)
    order = [b for b in (5, 2, 0) if b in banks] + sorted(b for b in banks if b not in (5, 2, 0))
    body = b"".join(bytes(banks[b]).ljust(16384, b"\0")[:16384] for b in order)
    out.write_bytes(bytes(h) + body)
    return out

if __name__ == "__main__":
    out, pc, sp = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    banks = {}
    for spec in sys.argv[4:]:
        b, f = spec.split(":", 1)
        banks[int(b)] = bytes(16384) if f == "zero" else pathlib.Path(f).read_bytes()
    p = build_nex(out, banks, pc, sp)
    print("wrote %s (%d bytes, banks %s, pc %04X sp %04X)" % (p, p.stat().st_size, sorted(banks), pc, sp))
