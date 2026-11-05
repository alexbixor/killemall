#!/usr/bin/env python3
"""m26_pad_audit.py - where is there really free space in each image? For every page-aligned label (defs padding before it) count
the zero bytes immediately before it in the assembled code; plus the high-block gap and the low-block tail. Both .sym/.tap."""
import re, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
def sym(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", p.read_text(), re.M)}
def code_of(tap):
    """pasmo --tap/--tapbas: blocks = [len lo hi][flag][data...][parity]; the CODE header (type 3) carries start; return (start, bytes)."""
    b = tap.read_bytes(); i = 0; blocks = []
    while i + 2 <= len(b):
        n = b[i] | b[i + 1] << 8; blocks.append(b[i + 2:i + 2 + n]); i += 2 + n
    out = []
    for k, blk in enumerate(blocks):
        if blk[0] == 0 and blk[1] == 3:        # header, CODE
            start = blk[14] | blk[15] << 8; length = blk[12] | blk[13] << 8
            data = blocks[k + 1][1:1 + length]; out.append((start, data))
    return out
for name in ("kea48", "kea128"):
    S = sym(ROOT / ("build/%s.sym" % name)); blocks = code_of(ROOT / ("build/%s.tap" % name))
    print("==", name, "code blocks:", [(hex(s), len(d)) for s, d in blocks])
    img = {}
    for s, d in blocks:
        for j, v in enumerate(d): img[s + j] = v
    lo, hi = min(img), max(img)
    print("   image %04X..%04X; hi_end %04X gap to 0xFDF0 = %d B; low_end %04X free to 0x8000 = %d B" % (lo, hi, S["hi_end"], 0xFDF0 - S["hi_end"], S.get("low_end", 0), 0x8000 - S.get("low_end", 0x8000)))
    by_addr = sorted((a, l) for l, a in S.items() if lo <= a <= hi + 1)
    for a, l in by_addr:
        if a & 255 == 0 or l in ("COLBASE", "HTABN", "TEX", "BANDTAB", "SOLIDPG"):
            z = 0; p = a - 1
            while p in img and img[p] == 0 and z < 4096: z += 1; p -= 1
            prev = [(pa, pl) for pa, pl in by_addr if pa < a][-1] if any(pa < a for pa, pl in by_addr) else (0, "?")
            if z >= 8: print("   %-12s %04X  zero bytes before it: %4d  (previous label %s %04X)" % (l, a, z, prev[1], prev[0]))
