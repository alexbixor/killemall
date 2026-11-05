; draw_flat.asm - lane M: flat-colour STAND-IN drawers (spec section 10 interface) used by main.asm until the textured
; draw.asm (orchestrator) replaces it (change the include in main.asm). No org (spec section 10); include after nx_vars.inc.
; Every call fills a run of rows of one screen column with a single palette index:
;   plane_add  : rows pl_a..pl_b-1 of column pl_c = floor_colours[pl_tex & 7]   (material*16 + level, manifest.json ids)
;   draw_piece : rows pc_ra..pc_ra+pc_count-1 of column pc_c = wall_material[pc_tex]*16 + (13 - 3*pc_s)   (s 0..3 -> 13,10,7,4)
;   void_fill  : rows vd_a..vd_b-1 of column vd_c = palette index 0
;   planes_reset / planes_flush : nothing (no plane bookkeeping needed for flat colours)
; Row r address (spec section 1): r < 48: 4000h + r*128 ; r >= 48: 6000h + (r-48)*128 ; pixel = row address + column.
; Registers: destroys A, BC, DE, HL (allowed by section 10). Scratch: fc_colour in the drawers' area (DRAW_VARS, nx_vars.inc).

fc_colour   equ DRAW_VARS      ; byte

planes_reset:
        ret
planes_flush:
        ret

; ---------------------------------------------------------------------------------------------------------------
plane_add:
        ld a,(pl_tex)
        and 7
        ld hl,floor_colours
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld b,(hl)               ; B = colour
        ld a,(pl_c)
        ld c,a                  ; C = column
        ld de,(pl_a)            ; E = first row a, D = end row b (pl_b = pl_a + 1)
        ld a,b
        jp fill_col

; ---------------------------------------------------------------------------------------------------------------
draw_piece:
        ld a,(pc_s)
        ld b,a
        add a,a
        add a,b                 ; 3*s
        ld b,a
        ld a,13
        sub b                   ; level = 13 - 3*s
        ld b,a
        ld a,(pc_tex)
        and 0Fh
        ld hl,wall_colours
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld a,(hl)               ; material*16
        or b                    ; + level (level <= 13 fits in the low nibble)
        ld b,a                  ; B = colour
        ld a,(pc_c)
        ld c,a
        ld de,(pc_ra)           ; E = first row ra, D = count (pc_count = pc_ra + 1)
        ld a,d
        add a,e
        ld d,a                  ; D = end row = ra + count (<= 96 by the walker's construction)
        ld a,b
        jp fill_col

; ---------------------------------------------------------------------------------------------------------------
void_fill:
        ld a,(vd_c)
        ld c,a
        ld de,(vd_a)            ; E = first row a, D = end row b (vd_b = vd_a + 1)
        xor a                   ; palette index 0 = void
        ; fall into fill_col

; ---------------------------------------------------------------------------------------------------------------
; fill_col - rows E..D-1 of column C get colour A (E < D <= 96; E >= D draws nothing). The run is split at row 48
;            because the two screen halves are 8 KB apart (spec section 1). destroys A, B, DE, HL
; ---------------------------------------------------------------------------------------------------------------
fill_col:
        ld (fc_colour),a
        ld a,e
        cp d
        ret nc                  ; empty run
        cp 48
        jr nc,fc_bot            ; first row >= 48: whole run in the bottom half
        ld a,d
        cp 49
        jr c,fc_top             ; end row <= 48: whole run in the top half
        push de
        ld d,48                 ; top part: rows E..47
        call fc_top
        pop de
        ld e,48                 ; bottom part: rows 48..D-1
fc_bot:
        ld a,d
        sub e
        ld b,a                  ; B = row count
        ld a,e
        sub 48
        ld l,a                  ; L = r' = row - 48
        srl a
        add a,60h
        ld h,a                  ; H = 60h + (r' >> 1)
        ld a,l
        and 1
        rrca                    ; A = (r' & 1) * 128
        or c
        ld l,a                  ; L = (r' & 1) * 128 + column
        jr fc_fill
fc_top:
        ld a,d
        sub e
        ld b,a                  ; B = row count
        ld a,e
        ld l,a
        srl a
        add a,40h
        ld h,a                  ; H = 40h + (row >> 1)
        ld a,l
        and 1
        rrca
        or c
        ld l,a                  ; L = (row & 1) * 128 + column
fc_fill:
        ld a,(fc_colour)
        ld de,128
fc_loop:
        ld (hl),a
        add hl,de
        djnz fc_loop
        ret

; ---------------------------------------------------------------------------------------------------------------
; colour tables (palette index = material*16 + level; material ids from build/next/assets/manifest.json:
; stone 0, mortar 1, brick 2, wood 3, iron 4, moss 5, flag 6, plaster 7, gold 8, flame 9, blood 10, water 11, rust 12,
; bone 13, dark 14, bluestone 15)
; ---------------------------------------------------------------------------------------------------------------
floor_colours:                  ; floor/ceiling texture id (spec section 7) -> one flat palette index
        db 6*16+8               ; 0 flag        : flag level 8 (mid grey)
        db 7*16+11              ; 1 plaster     : plaster level 11 (beige)
        db 0*16+6               ; 2 vault       : stone level 6 (dark vault stone)
        db 13*16+10             ; 3 tread       : bone level 10
        db 8*16+12              ; 4 altar top   : gold level 12
        db 11*16+9              ; 5 water       : water level 9 (blue)
        db 0*16+11              ; 6 cobble      : stone level 11 (light cobble grey)
        db 10*16+9              ; 7 blood flag  : blood level 9
wall_colours:                   ; wall texture id (spec section 7) -> material*16 (the level 13 - 3*s is added per piece)
        db 0*16                 ; 0 stone
        db 2*16                 ; 1 brick
        db 5*16                 ; 2 moss
        db 4*16                 ; 3 iron
        db 3*16                 ; 4 wood door
        db 13*16                ; 5 dais riser (bone blocks)
        db 8*16                 ; 6 lintel (gold trim, so lintels stand out in the stand-in)
        db 13*16                ; 7 altar face (bone)
        db 15*16                ; 8 blue stone
        db 13*16                ; 9 bone wall
        db 10*16                ; 10 banner (red cloth)
        db 4*16                 ; 11 iron-banded door
        db 9*16                 ; 12 torch bracket (flame)
        db 12*16                ; 13 crumbling stone (rust)
        db 5*16                 ; 14 vines (moss)
        db 14*16                ; 15 black (dark)
