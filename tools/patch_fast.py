#!/usr/bin/env python3
"""patch_fast.py - speed pass on kea48.asm:
  * ray(): keep the ray-direction accumulators in registers-free form but drop the 24-bit memory shuffles for rdx/rdy
    by storing them once; use 'ld hl,(acc+1)' direct loads (already) -- main win: replace the generic mul8x16 call
    in the side-distance setup with the squares-table multiply done in-line on the 8-bit fraction only (a*b/256 where
    a = frac, b = delta>>?): sideDist = frac * delta / 256 where delta is 16-bit -> two mul8 calls; we keep mul8x16 but
    make it leaner (no push/pop pairs).
  * calc_u: perp*|raydir| needs only the fraction of the product -> drop the high*high term.
  * hcol lookup: use the HTAB pages with a single shift chain via a jump table instead of 5 shift pairs.
"""
import pathlib
p = pathlib.Path("/home/ubuntu/work/killemall/src/48k/kea48.asm"); t = p.read_text()

old_mul = t[t.index("; A = m (0..255), DE = n (0..32767) -> HL = m*n/256"):t.index("; ---------------------------------------------------------------- renderer")]
new_mul = """; A = m (0..255), DE = n (0..32767) -> HL = m*n/256   (two squares-table products, no stack traffic)
mul8x16:
        ld (m16_m),a
        ld (m16_n),de
        ld c,d
        call mul8              ; HL = m*nh
        ld (m16_t),hl
        ld a,(m16_m)
        ld c,0
m16_n   equ $-1
        call mul8              ; HL = m*nl
        ld a,h
        ld hl,(m16_t)
        add a,l
        ld l,a
        ret nc
        inc h
        ret
m16_m:  defb 0
m16_t:  defw 0

"""
t = t.replace(old_mul, new_mul)
# the 'ld c,0 / m16_n equ $-1' trick needs m16_n to hold the low byte of n: store de low byte there instead
t = t.replace("        ld (m16_m),a\n        ld (m16_n),de\n        ld c,d\n", "        ld (m16_m),a\n        ld c,d\n        ld a,e\n        ld (m16_n),a\n        ld a,(m16_m)\n")

# calc_u: the product perp*|r| needs only its fractional byte: frac(a.b * c.d) low byte = (bl*dl)>>8 + ah*dl + bl*ch (mod 256)
old_cu = t[t.index("cu3:    ld (absr),de"):t.index("cu4:    ld hl,fracbase")]
new_cu = """cu3:    ld (absr),de
        ld hl,(perp)
        ld a,l
        ld c,e
        call mul8              ; lo*lo -> take H
        ld a,h
        ld (uacc),a
        ld hl,(perp)
        ld de,(absr)
        ld a,h
        ld c,e
        call mul8              ; hi*lo -> take L
        ld a,l
        ld hl,uacc
        add a,(hl)
        ld (hl),a
        ld hl,(perp)
        ld de,(absr)
        ld a,l
        ld c,d
        call mul8              ; lo*hi -> take L
        ld a,l
        ld hl,uacc
        add a,(hl)
        ld hl,negf
        bit 0,(hl)
        jr z,cu4
        neg
"""
t = t.replace(old_cu, new_cu)
p.write_text(t); print("patched")
