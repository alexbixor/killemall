#!/usr/bin/env python3
"""t1_fix_f2.py - two bugs: NCTAB low byte was a memory load; dc_buf low byte (0/128) lost when adding r0."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
C = ROOT / "src/common/sprites_c.asm"
t = C.read_text()
old = "        ld a,(NCTAB and 255)\n"
assert old in t
t = t.replace(old, "        ld a,NCTAB and 255\n")
C.write_text(t)
F = ROOT / "src/common/sprites_f.asm"
t = F.read_text()
old = """        ld c,a
        ld a,b
        sub c
        jr z,dc_run_l          ; no rows
        ld hl,(dc_buf)
        ld l,c
        ex de,hl               ; DE = BUF column + r0
        add a,a
        add a,CHJ and 255
"""
assert old in t
new = """        ld c,a
        ld a,b
        sub c
        jr z,dc_run_l          ; no rows
        ld b,a                 ; B = n rows
        ld hl,(dc_buf)
        ld a,l
        or c
        ld l,a
        ex de,hl               ; DE = BUF column + r0
        ld a,b
        add a,a
        add a,CHJ and 255
"""
t = t.replace(old, new)
F.write_text(t)
print("ok")
