#!/usr/bin/env python3
"""patch_m11_rh2.py - fix the height lookup: HTABN[i] = height for dist i/64 -> index = perp8.8 >> 2 (perp < 4 -> i < 256);
HTABF[i] = height for dist i/8 -> index = perp8.8 >> 5 (perp < 32).  Bit-exact with the M1 srl/rr chains, fewer T-states."""
import pathlib
p = pathlib.Path("/home/ubuntu/work/killemall/src/48k/kea48.asm"); t = p.read_text()
start = t.index("; wall height from perpendicular distance"); end = t.index("rh_set: ld (hcol),a")
new = '''; wall height from perpendicular distance: hcol = even height 2..96, or a clipped virtual height (104..192) when perp < 1
        ld a,(side)
        cp 2
        jr nz,rh1
        xor a
        jr rh_set
rh1:    ld hl,(perp)
        ld a,h
        cp 4
        jr nc,rh2
        ld a,l                 ; index = perp >> 2 = h*64 + l/4  (dist = index/64)
        rrca
        rrca
        and 63
        ld l,a
        ld a,h
        rrca
        rrca
        or l
        ld l,a
        ld h,HTABN/256
        ld a,(hl)
        jr rh_set
rh2:    cp 32
        jr nc,rh3
        ld a,l                 ; index = perp >> 5 = h*8 + l/32  (dist = index/8)
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        add a,a
        add a,a
        add a,a
        or l
        ld l,a
        ld h,HTABF/256
        ld a,(hl)
        jr rh_set
rh3:    ld a,2
'''
t = t[:start] + new + t[end:]
p.write_text(t); print("ok")
