#!/usr/bin/env python3
"""patch_band.py - switch kea48.asm to the clear-once + masked-band renderer (one-off source transform)."""
import pathlib, re
p = pathlib.Path("/home/ubuntu/work/killemall/src/48k/kea48.asm"); t = p.read_text()

# 1. render(): clear the window before the column loop
old = "        xor a\n        ld (col),a\ncol_loop:\n"
new = """        ld hl,SCRWIN
        ld b,0
        ld de,43605
        call CLEARW
        xor a
        ld (col),a
col_loop:
"""
assert old in t; t = t.replace(old, new)

# 2. replace everything from 'rt_skip:' up to (not including) '; texture u' with the band draw
start = t.index("rt_skip:\n"); end = t.index("; texture u (times 16)")
band = """rt_skip:
        ld a,(sub4)
        or a
        jr nz,rd_band
; first ray of the byte: attributes for this byte column (ceiling black, wall ink, floor gradient)
        ld a,(side)
        cp 2
        jr z,ra_far
        ld a,(code)
        and 15
        ld l,a
        ld h,0
        ld de,CODEINK
        add hl,de
        ld c,(hl)
        ld hl,(perp)
        ld a,h
        cp 3
        ld a,c
        jr nc,ra_w
        or 64
        jr ra_w
ra_far: ld a,7
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
rd_band:
        ld a,(hcol)
        or a
        ret z
; screen address of (topr, bytecol)
        ld a,(topr)
        add a,a
        ld l,a
        ld h,0
        ld de,SCRADDR
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(bytecol)
        add a,8
        add a,e
        ld e,a
        push de
; poke RET at BANDROW[botr], remember
        ld a,(botr)
        add a,a
        ld l,a
        ld h,0
        ld de,BANDROW
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(de)
        ld (poke_byte),a
        ld (poke_addr),de
        ld a,201
        ld (de),a
; entry BANDROW[topr]
        ld a,(topr)
        add a,a
        ld l,a
        ld h,0
        ld de,BANDROW
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (band_jp+1),de
; alt set: HL' = v accumulator (u*16 in H', 0 in L'), BC' = step
        exx
        ld hl,(tex_ptr)
        ld h,l
        ld l,0
        ld bc,(step_w)
        exx
        pop hl
        ld a,(tex_ptr+1)
        ld d,a
        ld a,(mask_b)
        ld c,a
band_jp:
        call 0
        ld a,(poke_byte)
        ld hl,(poke_addr)
        ld (hl),a
        ret

"""
t = t[:start] + band + t[end:]

# 3. calc_u result: store u*16 in tex_ptr low byte (already done by caller: ld (tex_ptr),a) - keep.
# 4. remove now-unused seg_call block
s2 = t.index("; run unrolled column code from row (seg_start)"); e2 = t.index("; DDA exits")
t = t[:s2] + t[e2:]
# 5. drop unused variables
for v in ["scr_ptr:    defw 0\n", "seg_start:  defb 0\n", "seg_end:    defb 0\n"]:
    t = t.replace(v, "")
# tex_ptr must stay 2 bytes: low = u*16, high = page
p.write_text(t); print("patched; jr range check follows at assembly")
