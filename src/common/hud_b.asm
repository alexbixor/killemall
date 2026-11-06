; hud_b.asm (T1) - print_char, hud_weapon, draw_weapon (32x24 weapon sprite into the back buffer).
; print_char: A = char, DE = screen address (ROM font); DE advances one cell. Preserves HL, BC.
print_char:
        push hl
        push bc
        IF DEFINED FLIP
        ld (hud_dirty),a       ; lane F rule F6: A = character >= 32, never 0
        ENDIF
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,ROMFONT
        add hl,bc
        ld b,8
        push de
pc_l:   ld a,(hl)
        ld (de),a
        inc hl
        inc d
        djnz pc_l
        pop de
        inc e
        pop bc
        pop hl
        ret
; hud_weapon: A = 0 idle, 1 fire frame (contract label; the game sets weapon_frame directly too)
hud_weapon:
        ld (weapon_frame),a
        ret
; draw_weapon: sprite id 14 + weapon_frame (32 wide = 4 byte columns x 24 rows, T5 layout: per byte column 24 mask
; then 24 pixel bytes) into BUF byte columns 10..13 (M2.5C: centre of 24), rows 72..95: buf = (buf AND mask) OR pix.
draw_weapon:
        ld a,(weapon_frame)
        add a,14
        add a,a
        ld l,a
        ld h,0
        ld de,spr_table
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc de                 ; skip db H
        ld hl,BUF+10*96+72     ; byte column 10, row 72 (M2.5C stride 96)
        ld b,4
dw_col: push bc
        push hl
        ld b,24
dw_r:   ld a,(de)
        and (hl)
        ld c,a
        push de
        ld a,e
        add a,24
        ld e,a
        jr nc,$+3
        inc d
        ld a,(de)
        or c
        ld (hl),a
        pop de
        inc de
        inc hl
        djnz dw_r
        ld a,e
        add a,24
        ld e,a
        jr nc,$+3
        inc d                  ; skip the pixel bytes of this column
        pop hl
        ld a,l
        add a,96               ; M2.5C: next byte column
        ld l,a
        jr nc,$+3
        inc h
        pop bc
        djnz dw_col
        ret
; M2.2: HUD strings/vars live in hud.asm (dashboard); labels/pills in dash_data.asm (low block)
