#!/usr/bin/env python3
"""Memory map summary from a pasmo .sym (NAME EQU 0xxxxH): label, address, size to next label; biggest blocks first."""
import re, sys
path = sys.argv[1] if len(sys.argv) > 1 else "build/kea48.sym"
syms = []
for line in open(path):
    m = re.match(r"^(\w+)\s+EQU\s+([0-9A-F]+)H", line.strip(), re.I)
    if m:
        syms.append((int(m.group(2), 16), m.group(1)))
syms = sorted(set(syms))
syms = [s for s in syms if 0x5B00 <= s[0] < 0x10000]
blocks = []
for i, (a, n) in enumerate(syms):
    nxt = syms[i + 1][0] if i + 1 < len(syms) else a
    blocks.append((nxt - a, a, n))
want = sys.argv[2:] if len(sys.argv) > 2 else []
print("labels", len(syms), "lowest", hex(syms[0][0]), "highest", hex(syms[-1][0]), syms[-1][1])
print("--- biggest 40 blocks (size, addr, label)")
for sz, a, n in sorted(blocks, reverse=True)[:40]:
    print(f"{sz:6d} {a:#06x} {n}")
if want:
    print("--- requested")
    d = {n: (a, sz) for sz, a, n in blocks}
    for w in want:
        print(w, d.get(w))
