#!/usr/bin/env python3
"""t1_fix_e1.py - clean ROWTAB top computation in sprites_e.asm."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/sprites_e.asm"
s = P.read_text()
i0 = s.index("        ld a,(ds_hv)\n        srl a\n        ld l,a\n        ld h,0\n        ld bc,48")
i1 = s.index("        ex de,hl               ; DE = acc (top), HL = step")
new = """        ld (ds_step),de
        ld a,(ds_hv)
        srl a
        ld d,a
        ld e,0                 ; DE = (hv/2) << 8
        ld hl,48*256
        or a
        sbc hl,de              ; HL = top 8.8 (s16)
        ex de,hl               ; DE = acc (top)
        ld hl,(ds_step)
"""
s = s[:i0] + new + s[i1 + len("        ex de,hl               ; DE = acc (top), HL = step\n        ld (ds_step),hl\n"):]
P.write_text(s)
print("ok", len(s.splitlines()))
