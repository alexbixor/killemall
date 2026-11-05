#!/usr/bin/env python3
"""t1_fix_b1.py - replace the messy cos7/sin7 derivation in sprites_b.asm with a clean one."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/sprites_b.asm"
s = P.read_text()
if "half_s8" in s:
    raise SystemExit("already")
i0 = s.index("draw_things:\n") + len("draw_things:\n")
i1 = s.index("        xor a\n        ld (nvis),a\n")
new = """        ld hl,(angidx)
        ld de,COSTAB
        add hl,de
        call half_s8
        ld (cos7),a
        ld hl,(angidx)
        ld de,SINTAB
        add hl,de
        call half_s8
        ld (sin7),a
"""
s = s[:i0] + new + s[i1:]
s = s.replace("cos7:   defb 0\n", """; half_s8: HL -> s16 word (256 = 1.0) -> A = word/2 as s8 (128 = 1.0 clamped to 127)
half_s8:
        ld a,(hl)
        inc hl
        ld d,(hl)
        sra d
        rra
        bit 7,a
        ret z
        inc d
        dec d
        ret nz                 ; negative: fine
        ld a,127               ; +128 -> clamp
        ret
cos7:   defb 0
""", 1)
P.write_text(s)
print("ok", len(s.splitlines()))
