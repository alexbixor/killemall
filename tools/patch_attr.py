#!/usr/bin/env python3
"""patch_attr.py - per-cell attributes for the 48K renderer: ceiling cells black, wall-band cells wall ink (+BRIGHT near),
floor cells a depth gradient (blue far, cyan, white near).  One-off source patch of src/48k/kea48.asm."""
import pathlib
p = pathlib.Path("/home/ubuntu/work/killemall/src/48k/kea48.asm"); t = p.read_text()
old = """ra_far: ld a,7
ra_w:   ld c,a
        ld hl,ATTRWIN
        ld a,(bytecol)
        add a,l
        ld l,a
        ld a,c
        ld de,32
        ld b,12
ra_l:   ld (hl),a
        add hl,de
        djnz ra_l
"""
new = """ra_far: ld a,7
ra_w:   ld c,a
        ld a,(topr)
        rrca
        rrca
        rrca
        and 15
        ld d,a
        ld a,(botr)
        dec a
        rrca
        rrca
        rrca
        and 15
        ld e,a
        ld hl,ATTRWIN
        ld a,(bytecol)
        add a,l
        ld l,a
        ld b,0
ra_l:   ld a,b
        cp d
        jr c,ra_c
        cp e
        jr z,ra_wl
        jr c,ra_wl
        cp 8
        ld a,1
        jr c,ra_put
        ld a,b
        cp 10
        ld a,5
        jr c,ra_put
        ld a,7
        jr ra_put
ra_wl:  ld a,c
        jr ra_put
ra_c:   xor a
ra_put: ld (hl),a
        ld a,l
        add a,32
        ld l,a
        jr nc,ra_n
        inc h
ra_n:   inc b
        ld a,b
        cp 12
        jr c,ra_l
"""
assert old in t
t = t.replace(old, new)
p.write_text(t)
print("patched")
