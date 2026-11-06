; sprites_next.asm - lane N2 (5 Nov 2026): software sprites with ZBUF occlusion in the LoRes frame (spec v0.2 section 7, brief
; section 3) + the weapon + the per-frame glue game_frame. Included by main_b.asm. Variables: main_b_vars.inc.
; game_frame: walk_frame_b (engine, lane N1/N1D; ZBUF = 128 words of depth Q8 at 1A00h) then, unless g_draw_off = 1:
;   page 8K banks 26/27 (sprite data, tools/nx_sprites_b.py) into slots 6/7, build VIS_B from THINGS_B (far -> near), draw
;   every entry, the weapon (rows 64..87), the HUD band (hud_next.asm), then restore slot 6 = WALL_BANK0, slot 7 = FLOOR_BANK.
; Projection of a thing at (tx, ty) Q8 (the rules tools/nx_test_game_b.py models in Python):
;   dx = tx - px ; dy = ty - py ; cull |dx| >= 16 cells or |dy| >= 16 cells
;   depth = smul_shr(dx, dirx, 8) + smul_shr(dy, diry, 8)      (each term sign * ((|a|*|b|) >> 8), as walk_b's smul_shr)
;   lat   = smul_shr(dx, plx, 8)  + smul_shr(dy, ply, 8)
;   skip depth < 64 or depth > 4095 ; R = 2*RECIP[depth]
;   h = min(96, (3*R) >> 5)  (= 24 rows of art at the wall scale 32*R/256) ; w = min(64, R >> 4) (16 columns)
;   mag = (|lat| * R) >> 11 ; cx = 64 + mag (lat >= 0) or 64 - mag ; c0 = cx - (w >> 1) ; skip if mag > 255, c0 >= 128 or c0 + w <= 0
;   feet = min(96, (12288 + 22*R + 127) >> 8)  (the walker's ROW(y_floor(d)) for eye 22) ; top = feet - h
;   VIS_B entry (depth, c0, w, h, feet, thing) inserted far -> near (depth descending), 16 max (the farther ones are kept)
;   art id: enemies SPRBASE_B[type] + (state 0: 0 ; 1: (ticks >> 4) & 1 ; 2: 2 ; 3: 3), items ITSPR_B[type - 16]
;   lane N3: ids 30..34 (boss) live in 8K bank 30 (16K bank 15, nx_sprites_b.py --out2, nx_build.py --sprites2) at C000h +
;   (id-30)*512: draw_sprite_b pages slot 6 = SPR_BANK2 for such an entry and back to SPR_BANK0 after it (ids < 18 use bank 26).
;   column c in [max(c0, 0), min(c0 + w, 128)): drawn iff ZBUF[c] > depth ; u = ((c - c0) * RECIP[w]) >> 12 (0..15)
;   row r in [max(top, 0), min(feet, 96)): v = ((r - top) * ((RECIP[h] * 24) >> 5)) >> 11 (0..23) ; pixel = art[u*32 + v] ; 0 = skip
; Z80N: mul d,e = db 0EDh,030h ; add hl,a = db 0EDh,031h ; nextreg r,v = db 0EDh,091h,r,v ; nextreg r,a = db 0EDh,092h,r

game_frame:
        call walk_frame_b
        ld a,(g_draw_off)
        or a
        ret nz
        db 0EDh,091h,56h,SPR_BANK0      ; slot 6 = 8K bank 26 (sprite ids 0..13)
        db 0EDh,091h,57h,SPR_BANK1      ; slot 7 = 8K bank 27 (pistol, ids 18..29)
        call build_vis
        ld a,(g_draw_mask)              ; bit 0 sprites, bit 1 weapon, bit 2 HUD (7 = all; the oracles mask parts)
        bit 0,a
        call nz,draw_vis
        ld a,(g_draw_mask)
        bit 1,a
        call nz,draw_weapon
        ld a,(g_draw_mask)
        bit 2,a
        call nz,hud_draw
        db 0EDh,091h,56h,WALL_BANK0     ; restore the engine's paging (drawers re-page slot 6 per piece, slot 7 = floors)
        db 0EDh,091h,57h,FLOOR_BANK
        ; tool hook (tools/nx_game_video.py): g_hold = 1 freezes here with the finished frame on screen (single-buffered
        ; LoRes: the next walk_frame_b overwrites the sprites, N2_QUESTIONS.md); the ticks spent held accumulate in g_hold_tk.
        ld a,(g_hold)
        or a
        ret z
        ld hl,(ticks)
        ld (g_tmp),hl
        ld a,1
        ld (g_held),a
gf_hold:
        ld a,(g_hold)
        or a
        jr nz,gf_hold
        xor a
        ld (g_held),a
        ld hl,(ticks)
        ld de,(g_tmp)
        or a
        sbc hl,de
        ld de,(g_hold_tk)
        add hl,de
        ld (g_hold_tk),hl
        ret

; ---------------------------------------------------------------- vis list
build_vis:
        xor a
        ld (g_nvis),a
        ld ix,THINGS_B
        ld b,NTHINGS_B
        ld c,0                          ; thing index
bv_l:   push bc
        ld a,(ix+0)
        or a
        jr z,bv_next
        ld a,c
        ld (sp_idx),a
        call thing_xform
bv_next:
        ld de,8
        add ix,de
        pop bc
        inc c
        djnz bv_l
        ret

thing_xform:
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(px)
        or a
        sbc hl,de
        ld (sp_dx),hl
        ld a,h
        add a,16
        cp 32
        ret nc                          ; |dx| >= 16 cells
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(py)
        or a
        sbc hl,de
        ld (sp_dy),hl
        ld a,h
        add a,16
        cp 32
        ret nc
        ; depth = smul_shr(dx, dirx, 8) + smul_shr(dy, diry, 8)
        ld hl,(sp_dx)
        ld de,(dirx)
        call smul8
        push hl
        ld hl,(sp_dy)
        ld de,(diry)
        call smul8
        pop de
        add hl,de
        ld (sp_depth),hl
        bit 7,h
        ret nz                          ; behind
        ld a,h
        cp 10h
        ret nc                          ; > 4095
        or a
        jr nz,tx_d_ok
        ld a,l
        cp 64
        ret c                           ; nearer than 0.25 cell
tx_d_ok:
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        add hl,hl                       ; R = 2*RECIP[depth] (<= 2048)
        ld (sp_r),hl
        ; w = min(64, R >> 4)
        ld a,h
        add a,a
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 0Fh
        or c
        ld c,a                          ; A = R >> 4 (R <= 2048 -> <= 128)
        ld a,h
        cp 4
        jr c,tx_w1
        ld c,64
        jr tx_w_ok
tx_w1:  ld a,c
        cp 65
        jr c,tx_w_ok
        ld c,64
tx_w_ok:
        ld a,c
        ld (sp_w),a
        ; h = min(96, (3*R) >> 5)
        ld hl,(sp_r)
        ld d,h
        ld e,l
        add hl,hl
        add hl,de                       ; 3*R (<= 6144)
        ld a,h
        cp 0Ch
        jr nc,tx_h96
        add hl,hl
        add hl,hl
        add hl,hl                       ; (3R) << 3 -> high byte = (3R) >> 5
        ld a,h
        cp 97
        jr c,tx_h_ok
tx_h96: ld a,96
tx_h_ok:
        ld (sp_h),a
        ; feet = min(96, (12288 + 22*R + 127) >> 8)
        ld hl,(sp_r)
        ld d,l
        ld e,22
        db 0EDh,030h                    ; DE = 22*R.lo
        ld a,(sp_r+1)
        ld c,a                          ; R.hi (<= 8)
        add a,a                         ; 2
        ld b,a
        add a,a                         ; 4
        add a,b                         ; 6
        ld b,a
        add a,a                         ; 12
        add a,b                         ; 18
        add a,c
        add a,c
        add a,c
        add a,c                         ; 22*R.hi (<= 176)
        add a,d
        ld h,a
        ld l,e                          ; HL = 22*R (<= 45056)
        ld de,12288+127
        add hl,de
        jr c,tx_f96
        ld a,h
        cp 97
        jr c,tx_f_ok
tx_f96: ld a,96
tx_f_ok:
        ld (sp_feet),a
        ; lat = smul_shr(dx, plx, 8) + smul_shr(dy, ply, 8)
        ld hl,(sp_dx)
        ld de,(plx)
        call smul8
        push hl
        ld hl,(sp_dy)
        ld de,(ply)
        call smul8
        pop de
        add hl,de
        ld (sp_lat),hl
        xor a
        bit 7,h
        jr z,tx_lat_pos
        call wb_neg_hl
        ld a,1
tx_lat_pos:
        ld (sp_sign),a
        ld (um_a),hl                    ; |lat|
        ld hl,(sp_r)
        ld (um_b),hl
        call umul16                     ; um_r1:um_r0 = |lat| * R
        ld a,(um_r1+1)
        or a
        ret nz                          ; mag >= 2^21 >> 11
        ld a,(um_r1)
        cp 8
        ret nc                          ; mag >= 256: off screen
        rrca
        rrca
        rrca
        and 0E0h
        ld c,a                          ; (r1.lo << 5) & 0FFh
        ld a,(um_r0+1)
        rrca
        rrca
        rrca
        and 1Fh
        or c
        ld l,a
        ld h,0                          ; HL = mag (0..255)
        ld a,(sp_sign)
        or a
        jr z,tx_cx_pos
        call wb_neg_hl
tx_cx_pos:
        ld de,64
        add hl,de                       ; cx
        ld a,(sp_w)
        srl a
        ld e,a
        ld d,0
        or a
        sbc hl,de                       ; c0 = cx - w/2 (s16)
        ld (sp_c0),hl
        bit 7,h
        jr nz,tx_c0_neg
        ld a,h
        or a
        ret nz
        ld a,l
        cp 128
        ret nc                          ; c0 >= 128: right of the screen
        jr vis_add_b
tx_c0_neg:
        ld a,(sp_w)
        ld e,a
        ld d,0
        add hl,de                       ; c0 + w
        bit 7,h
        ret nz
        ld a,h
        or l
        ret z                           ; c0 + w <= 0: left of the screen
        ; fall into vis_add_b
; vis_add_b: insert (sp_depth, sp_c0, sp_w, sp_h, sp_feet, sp_idx) keeping VIS_B sorted by depth descending (far first)
vis_add_b:
        ld a,(g_nvis)
        cp VISMAX_B
        ret nc
        ld hl,VIS_B
        ld c,a                          ; entries after the insertion point
        or a
        jr z,va_put
va_f:   ld e,(hl)
        inc hl
        ld d,(hl)
        dec hl                          ; DE = entry depth
        push hl
        ld hl,(sp_depth)
        or a
        sbc hl,de                       ; new depth - entry depth
        pop hl
        jr nc,va_shift                  ; new depth >= entry depth: insert before this entry
        ld de,8
        add hl,de
        dec c
        jr nz,va_f
        jr va_put
va_shift:                               ; move the C entries from HL (8*C bytes) up by 8 bytes
        push hl
        ld a,c
        add a,a
        add a,a
        add a,a                         ; A = 8*C (<= 120)
        ld c,a
        ld b,0                          ; BC = bytes to move
        dec a
        ld e,a
        ld d,0
        add hl,de                       ; HL = last source byte
        ld d,h
        ld e,l
        ld a,e
        add a,8
        ld e,a
        jr nc,va_sh2
        inc d
va_sh2: lddr                            ; DE = last dest byte
        pop hl
va_put: ld a,(sp_depth)
        ld (hl),a
        inc hl
        ld a,(sp_depth+1)
        ld (hl),a
        inc hl
        ld a,(sp_c0)
        ld (hl),a
        inc hl
        ld a,(sp_c0+1)
        ld (hl),a
        inc hl
        ld a,(sp_w)
        ld (hl),a
        inc hl
        ld a,(sp_h)
        ld (hl),a
        inc hl
        ld a,(sp_feet)
        ld (hl),a
        inc hl
        ld a,(sp_idx)
        ld (hl),a
        ld hl,g_nvis
        inc (hl)
        ret

; smul8: HL = sign(HL)*sign(DE) * ((|HL| * |DE|) >> 8) with |HL| < 4096, |DE| <= 256. destroys A, BC, DE
smul8:
        ld c,0
        bit 7,h
        jr z,sm_a_pos
        call wb_neg_hl
        inc c
sm_a_pos:
        bit 7,d
        jr z,sm_b_pos
        ex de,hl
        call wb_neg_hl
        ex de,hl
        inc c
sm_b_pos:
        ld a,d
        or a
        jr z,sm_b_small
        ; |DE| = 256: result = |HL|
        jr sm_sign
sm_b_small:
        ld b,h                          ; B = a.hi (< 16)
        ld a,e                          ; A = b (< 256)
        ld d,l
        ld e,a
        push af
        db 0EDh,030h                    ; DE = a.lo * b
        pop af
        ld l,d                          ; (a.lo*b) >> 8
        ld h,0
        ld d,b
        ld e,a
        db 0EDh,030h                    ; DE = a.hi * b (< 4096)
        add hl,de
sm_sign:
        bit 0,c
        ret z
        jp wb_neg_hl

; umul16: um_r1:um_r0 = um_a * um_b (unsigned 16 x 16 -> 32). destroys A, DE, HL
umul16:
        ld a,(um_a)
        ld d,a
        ld a,(um_b)
        ld e,a
        db 0EDh,030h
        ld (um_r0),de
        ld a,(um_a+1)
        ld d,a
        ld a,(um_b+1)
        ld e,a
        db 0EDh,030h
        ld (um_r1),de
        ld a,(um_a)
        ld d,a
        ld a,(um_b+1)
        ld e,a
        db 0EDh,030h
        call um_mid
        ld a,(um_a+1)
        ld d,a
        ld a,(um_b)
        ld e,a
        db 0EDh,030h
um_mid: ld hl,(um_r0)                   ; um_r1:um_r0 += DE << 8
        ld a,h
        add a,e
        ld h,a
        ld (um_r0),hl
        ld hl,(um_r1)
        ld a,l
        adc a,d
        ld l,a
        ld a,h
        adc a,0
        ld h,a
        ld (um_r1),hl
        ret

; ---------------------------------------------------------------- drawing
draw_vis:
        ld a,(g_nvis)
        or a
        ret z
        ld b,a
        ld hl,VIS_B
dv_l:   push bc
        push hl
        call draw_sprite_b
        pop hl
        ld bc,8
        add hl,bc
        pop bc
        djnz dv_l
        ret

draw_sprite_b:
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (sd_depth),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (sd_c0),de
        ld a,(hl)
        inc hl
        ld (sd_w),a
        ld a,(hl)
        inc hl
        ld (sd_h),a
        ld a,(hl)
        inc hl
        ld (sd_feet),a
        ld a,(hl)                       ; thing index -> art address
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,THINGS_B
        add hl,de
        push hl
        pop ix
        ld a,(ix+0)
        cp 16
        jr nc,ds_item
        ld hl,SPRBASE_B
        db 0EDh,031h                    ; add hl,a
        ld c,(hl)
        ld a,(ix+5)
        cp 2
        jr nc,ds_state_add              ; 2 attack, 3 dead: base + state
        or a
        jr z,ds_art_id                  ; idle: base (A = 0)
        ld a,(ticks)                    ; chase: walk A/B every 16 ticks
        rrca
        rrca
        rrca
        rrca
        and 1
ds_state_add:
        add a,c
        jr ds_art_a
ds_art_id:
        ld a,c
        jr ds_art_a
ds_item:
        sub 16
        ld hl,ITSPR_B
        db 0EDh,031h
        ld a,(hl)
ds_art_a:
        cp 30
        jr c,ds_art_ok
        sub 30                          ; lane N3: boss ids 30..34 in 8K bank 30 at C000h + (id-30)*512 (slot 6 re-paged)
        add a,a
        add a,0C0h
        ld h,a
        ld l,0
        db 0EDh,091h,56h,SPR_BANK2
        call ds_art_set
        db 0EDh,091h,56h,SPR_BANK0      ; back to the ids 0..13 bank for the next entry (draw_vis walks on)
        ret
ds_art_ok:
        cp 18
        jr nc,ds_art_hi
        ld l,0                          ; C000h + id*512
        add a,a
        add a,0C0h
        ld h,a
        jr ds_art_set
ds_art_hi:
        sub 18
        add a,a
        add a,0E8h                      ; E800h + (id-18)*512
        ld h,a
        ld l,0
ds_art_set:
        ld (sd_art),hl
        ; ustep = RECIP[w] ; vstep = (RECIP[h] * 24) >> 5
        ld a,(sd_w)
        ld l,a
        ld h,0
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (sd_ustep),de
        ld a,(sd_h)
        ld l,a
        ld h,0
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (um_a),de
        ld hl,24
        ld (um_b),hl
        call umul16                     ; um_r1:um_r0 = RECIP[h]*24 (< 2^21)
        ld hl,(um_r0)
        ld a,(um_r1)
        ld b,5
ds_vs:  srl a
        rr h
        rr l
        djnz ds_vs
        ld (sd_vstep),hl
        ; rows: top = feet - h ; rstart = max(top, 0) ; rend = feet (<= 96) ; vacc0 = (rstart - top) * vstep
        ld a,(sd_feet)
        ld l,a
        ld h,0
        ld a,(sd_h)
        ld e,a
        ld d,0
        or a
        sbc hl,de                       ; HL = top (s16)
        ld (sd_top),hl
        ld c,0                          ; rows clipped above
        bit 7,h
        jr z,ds_top_ok
        xor a
        sub l
        ld c,a                          ; -top (< h <= 96)
        ld l,0
ds_top_ok:
        ld a,l
        ld (sd_rstart),a
        ld a,(sd_feet)
        sub l
        ret z
        ret c
        ld (sd_nrows),a
        ld a,c
        ld (um_a),a
        xor a
        ld (um_a+1),a
        ld hl,(sd_vstep)
        ld (um_b),hl
        call umul16
        ld hl,(um_r0)
        ld (sd_vacc0),hl
        ; columns: cstart = max(c0, 0) ; cend = min(c0 + w, 128) ; uacc = (cstart - c0) * ustep
        ld hl,(sd_c0)
        ld c,0
        bit 7,h
        jr z,ds_c0_ok
        xor a
        sub l
        ld c,a                          ; columns clipped on the left (< w)
        ld hl,0
ds_c0_ok:
        ld a,l
        ld (sd_c),a
        ld hl,(sd_c0)
        ld a,(sd_w)
        ld e,a
        ld d,0
        add hl,de
        ld a,h
        or a
        jr nz,ds_cend128
        ld a,l
        cp 129
        jr c,ds_cend_ok
ds_cend128:
        ld a,128
ds_cend_ok:
        ld (sd_cend),a
        ld a,c
        ld (um_a),a
        xor a
        ld (um_a+1),a
        ld hl,(sd_ustep)
        ld (um_b),hl
        call umul16
        ld hl,(um_r0)
        ld (sd_uacc),hl
ds_col_loop:
        ld a,(sd_c)
        ld c,a
        ld a,(sd_cend)
        cp c
        ret z
        ret c
        ; ZBUF[c] > depth ?
        ld a,c
        add a,a
        ld l,a
        ld h,ZBUF/256
        ld e,(hl)
        inc hl
        ld d,(hl)                       ; DE = ZBUF[c]
        ld hl,(sd_depth)
        or a
        sbc hl,de                       ; depth - ZBUF[c] < 0 -> draw
        jr nc,ds_col_next
        ; art column = sd_art + (uacc >> 12) * 32
        ld a,(sd_uacc+1)
        rrca
        rrca
        rrca
        rrca
        and 0Fh                         ; u = uacc >> 12 (0..15)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                       ; HL = u*32
        ld de,(sd_art)
        add hl,de
        ex de,hl                        ; DE = art column (32 bytes, rows 0..23 used)
        ; screen address of (rstart, c)
        ld a,(sd_rstart)
        ld b,a
        ld a,c
        call scr_addr                   ; HL = screen address
        ld a,(sd_nrows)
        ld (sd_cnt),a
        ld a,b                          ; current row
        push bc
        ld bc,(sd_vacc0)
        ld (um_a),bc                    ; vacc
        pop bc
ds_row_loop:
        ld a,(um_a+1)                   ; v = vacc >> 11 = hi >> 3 (0..23)
        rrca
        rrca
        rrca
        and 1Fh
        ld c,a
        ld a,e                          ; art[v]
        add a,c
        ld c,e
        ld e,a
        ld a,(de)
        ld e,c
        or a
        jr z,ds_px_skip
        ld (hl),a
ds_px_skip:
        push de
        ld de,(sd_vstep)
        push hl
        ld hl,(um_a)
        add hl,de
        ld (um_a),hl
        pop hl
        pop de
        ld a,(sd_cnt)
        dec a
        jr z,ds_col_done
        ld (sd_cnt),a
        inc b                           ; next row
        ld a,b
        cp 48
        jr nz,ds_row_adv
        ld a,h
        add a,8                         ; row 47 -> 48: 5780h+80h = 5800h -> 6000h
        ld h,a
ds_row_adv:
        ld a,l
        add a,128
        ld l,a
        jr nc,ds_row_loop
        inc h
        jr ds_row_loop
ds_col_done:
ds_col_next:
        ld hl,(sd_uacc)
        ld de,(sd_ustep)
        add hl,de
        ld (sd_uacc),hl
        ld hl,sd_c
        inc (hl)
        jp ds_col_loop

; scr_addr: B = row (0..95), A = column -> HL = screen byte address = base + row*128 + col (SCR_TOP rows 0..47, SCR_BOT 48..95). keeps B, C
scr_addr:
        ld l,a
        ld a,b
        cp 48
        jr c,sa_top
        sub 48
        srl a                           ; A = (row-48) >> 1, carry = row & 1
        jr nc,sa_b1
        set 7,l                         ; odd row: + 128 (col < 128: no carry)
sa_b1:  add a,60h
        ld h,a
        ret
sa_top: srl a
        jr nc,sa_t1
        set 7,l
sa_t1:  add a,40h
        ld h,a
        ret

; ---------------------------------------------------------------- weapon: pistol 32x24 at columns 48..79, rows 64..87 (1:1)
draw_weapon:
        ld a,(g_wframe)
        or a
        ld de,0E000h                    ; idle art (bank 27 at +0)
        jr z,dw_art
        ld de,0E400h                    ; fire art
dw_art: ld c,48
dw_col: ld b,64
        ld a,c
        call scr_addr                   ; HL = screen (64, c) -> SCR_BOT + 16*128 + c
        push bc
        ld b,24
dw_row: ld a,(de)
        or a
        jr z,dw_skip
        ld (hl),a
dw_skip:
        inc de
        ld a,l
        add a,128
        ld l,a
        jr nc,dw_r1
        inc h
dw_r1:  djnz dw_row
        pop bc
        ld a,e                          ; next art column: +32 bytes from the column start (24 used + 8 pad)
        add a,8
        ld e,a
        jr nc,dw_c1
        inc d
dw_c1:  inc c
        ld a,c
        cp 80
        jr nz,dw_col
        ret
