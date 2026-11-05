; attr.asm - M2.6 P2E attribute writer (2 Nov 2026, scheme P2E approved 13:13Z). render calls it right after COPYBUF (the frame
; is on screen; the 288 window attribute cells are rewritten in roughly 10-16k T). Per frame:
;  1. every window cell (12 rows x 24 byte columns, ATTRWIN) = T, the level tint stored by win_tint (at_tint) - wt_fill
;  2. per byte column whose tallest ray (zbuf; 3 / 2 / 3 rays per byte column of a 24-px group, ADJTAB) is hv >= 64 px (wall
;     nearer than 1.5 cells): the cell rows n .. 11-n = T | BRIGHT, n = cell rows above the wall top (48 - hv/2) / 8:
;     n = 2 for hv 64, 1 for 66..80, 0 from 82 (heights are even; clipped heights >= 104 fill the window)
;  3. per byte column with sprite marks (lowcode.asm dc_mark -> CMIN): rows first .. last = sprite ink | BRIGHT, marks cleared
;     (M2.6 blood 3, 3 Nov 2026: CMX bit 7 set = that ink WITHOUT BRIGHT - the dark red corpse stain, blood.asm ds_inkl 0xA0)
; Walls, floor and ceiling keep one ink (T) so nothing can clash; a sprite recolours exactly the cells that hold its white
; pixels, and the nearest sprite wins a shared cell (vis is drawn far -> near). Oracle: tools/p2e_oracle.py.
attr_write:
        ld a,(at_tint)
        call wt_fill           ; 1. 288 cells = T (kea48.asm win_tint's loop)
        ld hl,ATTRWIN
        ld de,zbuf
        ld ix,CMIN
        ld a,8
aw_g:   push af
        ld b,3
        call aw_col
        ld b,2
        call aw_col
        ld b,3
        call aw_col
        pop af
        dec a
        jr nz,aw_g
; M2.6 muzzle flash (3 Nov 2026): while the pistol shows its fire frame (weapon_frame = 1 for the 5 frames after a shot) the
; two window cells at the muzzle = BRIGHT yellow: cell row 9, byte columns 11..12 (the starburst is rows 72..76 of the 32-px
; gun drawn at byte columns 10..13 - hud_b.asm draw_weapon). Written last, so it wins over sprite and wall cells.
        ld a,(weapon_frame)
        or a
        ret z
        ld hl,ATTRWIN+9*32+11
        ld (hl),0x46
        inc l
        ld (hl),0x46
        ret
; aw_col: B rays of zbuf at DE (DE advances), HL -> this byte column's row-0 cell, IX -> its marks. HL++ / IX += 2 at the end.
aw_col: ld c,0
awm:    ld a,(de)
        inc e                  ; zbuf (64 B at DRAM+0x60) never crosses a page
        cp c
        jr c,awm1
        ld c,a
awm1:   djnz awm               ; C = tallest wall in this byte column (0 = none)
        push de
        ld de,32
        ld a,c
        cp 64
        jr c,aw_spr            ; no near wall in this column
        ld b,0
        cp 82
        jr nc,aw_n             ; top row <= 7: all 12 cell rows
        inc b
        cp 65
        jr nc,aw_n             ; 66..80: rows 1..10
        inc b                  ; 64: rows 2..9
aw_n:   ld c,b                 ; first row n
        ld a,12
        sub b
        sub b
        ld b,a                 ; 12 - 2n cells
        ld a,(at_tint)
        or 0x40                ; T | BRIGHT
        call aw_fill
aw_spr: ld a,(ix+0)            ; 12 - first marked row (0 = no sprite pixels in this column)
        or a
        jr z,aw_next
        ld (ix+0),0
        ld b,a
        ld a,12
        sub b
        ld c,a                 ; first row (0..11)
        ld a,(ix+1)            ; ink << 4 | last row + 1
        ld (ix+1),0
        push af
        and 15
        sub c
        ld b,a                 ; cells first .. last (>= 1)
        pop af
        rrca
        rrca
        rrca
        rrca
        and 15                 ; bit 3 (= CMX bit 7) set: not BRIGHT - M2.6 blood 3 corpse stain
        cp 8
        jr nc,aw_dim
        or 0x40                ; sprite ink | BRIGHT
aw_dim: and 0x47
        call aw_fill
aw_next:
        pop de
        inc hl                 ; next byte column's row-0 cell (0x24 .. 0x3B: one page)
        inc ix
        inc ix
        ret
; aw_fill (B cells of attribute A down the byte column at HL from cell row C; DE = 32) lives in ../common/attrfill.asm since
; M2.6 blood 3 (3 Nov 2026): 13 B moved into the padding before TEX to pay for the 6 B stain decode above (high block gate).
at_tint: defb 7                ; window ink of this level (win_tint)
