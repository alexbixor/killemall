#!/usr/bin/env python3
"""m24_edit_card3.py - M2.4 card v3: the card of a byte column is ONE chain call over rows k0*8 .. k1*8+7 (the cells are
contiguous), ds_rmin/ds_rmax hold those rows as before, so the original dc_attr (rows rmin/8..rmax/8) is kept; cmask and the
per-cell loop go. Idempotent (rewrites the card block between the markers)."""
import pathlib, re
f = pathlib.Path.home() / "work/killemall/src/common/sprites_f.asm"
s = f.read_text()
start = s.index("; card: mask = bits k0..k1")
end = s.index("; ---- blit the in-span columns")
new = """; card: rows k0*8 .. k1*8+7 of this byte column -> black in one chain call; ds_rmin/ds_rmax = those rows (dc_attr)
        ld a,(dc_k0)
        cp 255
        jp z,dc_l              ; no ink in this byte column: no card
        add a,a
        add a,a
        add a,a                ; r0 = k0*8
        ld c,a
dc_rmin: ld hl,ds_rmin         ; L patched with the byte column
        ld (hl),a
        ld a,(dc_k1)
        add a,a
        add a,a
        add a,a
        or 7                   ; r1 = k1*8+7
        set 4,l
        ld (hl),a
        sub c
        inc a                  ; n = rows (8..96)
        ld b,a
        ld hl,(dc_buf)
        ld a,l
        or c
        ld l,a
        ex de,hl               ; DE = BUF column + r0
        ld a,b
        add a,a
        add a,CHJ and 255
        ld l,a
        ld h,CHJ/256           ; HL -> CHJ[n]
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                 ; HL = chain entry (n rows)
        ld bc,0                ; and 0 / or 0: black, all 8 slots
        call jp_hl
"""
s = s[:start] + new + s[end:]
# init: rmin = 255 / rmax = 0 again (dc_attr convention)
old_init = """        ld hl,ds_rmin          ; ds_cm[16] low bytes then high bytes: 32 B, one page
        ld b,32
        xor a
dc_clr: ld (hl),a
        inc l
        djnz dc_clr
"""
new_init = """        ld hl,ds_rmin
        ld b,16
        ld a,255
dc_clr: ld (hl),a              ; rmin = 255 (no card), rmax = 0
        set 4,l
        ld (hl),0
        res 4,l
        inc l
        djnz dc_clr
"""
assert old_init in s; s = s.replace(old_init, new_init)
# drop cmask
a = s.index("; cmask: A = n"); b = s.index("; dc_attr: paint")
s = s[:a] + s[b:]
# original dc_attr back
a = s.index("; dc_attr: paint"); b = s.index("dc_run: defw 0")
s = s[:a] + """; dc_attr: paint ds_ink into ATTRBUF cells rows rmin/8..rmax/8 of every byte column that received a card (window rows only,
; never the HUD; ATTRCOPY moves the 12 x 16 block to the screen after all sprites)
dc_attr:
        ld hl,ds_rmin
        ld de,ATTRBUF
        ld b,16
da_col: ld a,(hl)
        inc a                  ; 255 -> 0: no card in this byte column
        jr z,da_nextc
        dec a
        rrca
        rrca
        rrca
        and 15                 ; first attribute row
        ld c,a
        set 4,l
        ld a,(hl)
        res 4,l
        rrca
        rrca
        rrca
        and 15                 ; last attribute row
        sub c
        inc a                  ; count of rows
        push bc
        push de
        push hl
        ld b,a
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a                ; 16 * first row
        add a,e
        ld e,a
        ld a,(ds_ink)
da_row: ld (de),a
        ld hl,16
        add hl,de
        ex de,hl
        djnz da_row
        pop hl
        pop de
        pop bc
da_nextc:
        inc l
        inc e
        djnz da_col
        ret
""" + s[b:]
s = s.replace("; visible in-span columns (run lists through ROWTAB, look-ahead) are cleared to black over all 8 pixel slots (SCHAIN,\n; B = 0, C = 0) and dc_attr paints TYPEINK into exactly those cells (mask word ds_cm[bc]: low byte ds_rmin[bc], high byte\n; ds_rmax[bc]).",
              "; visible in-span columns (run lists through ROWTAB, look-ahead) are cleared to black over all 8 pixel slots (one SCHAIN\n; call, B = 0, C = 0) and dc_attr paints TYPEINK into exactly those cells (rows ds_rmin[bc]..ds_rmax[bc]).")
s = s.replace("        ; ds_rmin[16] / ds_rmax[16] = ds_cm low / high bytes -> DRAM (state.asm): 32-byte aligned so bit 4 of the address toggles",
              "        ; ds_rmin[16] then ds_rmax[16] -> DRAM (state.asm, M2.2): 32-byte aligned so bit 4 of the address toggles between them")
f.write_text(s); print("sprites_f.asm card v3 written", len(s))
