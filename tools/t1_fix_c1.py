#!/usr/bin/env python3
"""t1_fix_c1.py - simplify the visibility test at the end of thing_xform2 and fix the product range check."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/sprites_c.asm"
s = P.read_text()
i0 = s.index("        ld c,a                 ; visible if c0 < 64")
i1 = s.index("thv:    defb 0")
new = """        bit 7,a
        jr nz,tx2n
        cp 64
        ret nc                 ; left edge beyond the right border
        jp vis_add
tx2n:   ld c,a
        ld a,(tnc)
        add a,c                ; c0 + nc (s8, no overflow: c0 >= -95, nc <= 64)
        ret z
        ret m                  ; right edge still left of column 0
        jp vis_add
"""
s = s[:i0] + new + s[i1:]
s = s.replace("        ld a,e\n        cp 8\n        ret nc                 ; product >= 2^19 -> |cx-32| > 400\n",
              "        ld a,e\n        cp 2\n        ret nc                 ; product >= 2^17 -> |cx-32| >= 96: off screen\n")
P.write_text(s)
print("ok", len(s.splitlines()))
