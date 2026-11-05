#!/usr/bin/env python3
"""patch_m11_rdband.py - one-shot: tighten the rd_band entry (masks kept in IX across calc_u, texture page via push/pop, jp band)."""
import pathlib
p = pathlib.Path("/home/ubuntu/work/killemall/src/48k/kea48.asm"); t = p.read_text()
def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)
start = t.index("rd_band:\n"); end = t.index("; texture u (times 16) from wall hit position")
new = '''rd_band:
        ld a,(hcol)
        or a
        ret z
; band routine for this height, slot masks for this ray, texture page (BANDTAB, SLOTM, TEXPG share one page)
        ld h,BANDTAB/256
        ld l,a
        ld e,(hl)
        inc l
        ld d,(hl)
        ld (band_jp+1),de
        ld a,(sub4)
        add a,SLOTM and 255
        ld l,a
        ld a,(hl)              ; slot bits 192 >> 2p
        ld c,a
        cpl
        ld ixh,a               ; floor mask = not slot (kept in IXH across calc_u)
        ld a,(side)
        rrca
        sbc a,a
        and 85
        cpl                    ; 255 lit side / 170 dark side
        and c
        ld ixl,a               ; texel mask = slot bits masked by the shade
        ld a,(code)
        and 15
        add a,TEXPG and 255
        ld l,a
        ld h,(hl)
        push hl                ; H = texture page
        call calc_u            ; A = u*16
        pop hl
        ld l,a                 ; HL = texture column
        ld a,(bytecol)
        rrca
        ld e,a
        and 7
        add a,BUF/256
        ld d,a
        ld a,e
        and 128
        ld e,a
        ld a,(topr)
        add a,e
        ld e,a                 ; DE = buffer address of the band's top row
        ld c,ixh               ; floor mask for rows below the horizon
band_jp:
        jp 0

'''
t = t[:start] + new + t[end:]
rep("tex_hi:     defb 0\ncmask_v:    defb 0\ntexm_v:     defb 0\n", "")
p.write_text(t); print("ok")
