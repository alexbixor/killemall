; walk_b.asm - Kill'em all Spectrum Next edition B ("flat" engine): the column walker. Lane N1.
; Implements docs/next_engine_spec_v0.2_flat.md section 3 (ray + DDA until a solid cell, hit column/shade, WALL tile split
; of v0.1 section 4 with ytop = 0 / ybot = 96, floor and ceiling spans, ZBUF) with the v0.1 sections 0, 2 and 3 maths.
; No org here (spec section 10): main_b.asm / test_walk_b.asm set org 8000h and include nx_vars.inc + walk_b_vars.inc first.
; Entry points: setup_camera_b (eye = 22 constant, spec v0.2 section 2), walk_frame_b (planes_reset ; 128 columns ;
; planes_flush ; frames += 1).  Call interface unchanged: the drawers' parameter blocks of nx_vars.inc, draw_piece /
; plane_add / void_fill / planes_reset / planes_flush, ZBUF at 1A00h.  The level is the mapc level at LEVEL (0B800h):
; cell(mx, my) = byte at LEVEL + 8 + my*32 + mx ; CEIL / FTEX / CTEX = bytes wb_ceil / wb_ftex / wb_ctex (walk_b_vars.inc).
; All labels are prefixed wb_/wc_/dda_ so this file can coexist with option A's walk.asm in one program.
; Z80N opcodes as db: mul d,e = 0EDh,030h ; add hl,a = 0EDh,031h.
;
; Speed design (the walk is the biggest cost of the frame):
;   - the DDA state lives in registers: HL = sdx, BC = ddx, IX = sdy, DE = ddy ; HL' = cell pointer, E' = mx, D' = my,
;     BC' = +32 / -32 (the pointer step of a y step). d of the boundary just crossed is stored to wb_d (16 T) because the
;     saturating add makes it unrecoverable from the new side distance.
;   - four copies of the DDA loop, one per (sign sx, sign sy), so the cell steps are inc/dec and the map test is one
;     bit/jp m test (mx or my becoming 32 or -1 = the ray left the map -> VOID(c, 0, 96), ZBUF 4095).
;   - the "at most 64 steps" bound of spec v0.2 section 3 step 1 needs no counter: from a start cell inside a 32x32 map
;     a ray leaves it after at most (32 - mx0) + (32 - my0) - 1 <= 63 steps, so the map test always fires first
;     (build/night/N1_QUESTIONS.md Q2). The d > 4095 test is done once at the hit: d is non-decreasing along the ray,
;     so "d > 4095 at an earlier step" and "d > 4095 at the hit" are the same event (Q3).
;   - one RECIP lookup per column gives R(d); two (CEIL = 64: three) 8x16 projections; the texture column needs only the
;     low byte of (|r| * d) >> 8 (wb_hit_lo, three 8x8 products); the ray components use one 8x8 product each.

walk_b_begin:
; shade (v0.1 section 4 step 4): s = 0 if d < 384, 1 if d < 768, 2 if d < 1536 else 3, indexed by d >> 7 (0..31)
wb_shade_tab:
        db 0,0,0,1,1,1,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3
; WALLMAP (spec v0.2 section 1): cell code -> walls.bin texture id. Codes 13..15 are not defined by mapc -> stone (Q4).
wb_wallmap:
        db 0,0,1,3,8,2,13,14,4,5,6,0,7,0,0,0

; ---------------------------------------------------------------------------------------------------------------
; setup_camera_b - v0.1 section 2 with eye = 22 (spec v0.2 section 2): dirx = COS[a], diry = SIN[a], plx = -SIN[a],
;                  ply = COS[a], mx0 = px >> 8, my0 = py >> 8. Reads px, py, ang (nx_vars.inc).
; ---------------------------------------------------------------------------------------------------------------
setup_camera_b:
        ld hl,(ang)
        ld a,h
        and 3                   ; a & 1023
        ld h,a
        add hl,hl               ; word index
        push hl
        ld de,COS_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = COS[a]
        ld (dirx),de
        ld (ply),de
        pop hl
        ld de,SIN_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = SIN[a]
        ld (diry),de
        ex de,hl
        call wb_neg_hl
        ld (plx),hl             ; plx = -SIN[a]
        ld a,(px+1)
        ld (mx0),a
        ld a,(py+1)
        ld (my0),a
        ld a,22
        ld (eye),a              ; edition B: every walkable cell has floor 0 -> eye = 22
        ret

; ---------------------------------------------------------------------------------------------------------------
; walk_frame_b - planes_reset ; per-frame constants ; columns 0..127 ; planes_flush ; frames += 1
; ---------------------------------------------------------------------------------------------------------------
walk_frame_b:
        call planes_reset
        ld hl,(plx)             ; |plx| and its sign
        xor a
        bit 7,h
        jr z,wf_plx_pos
        call wb_neg_hl
        ld a,1
wf_plx_pos:
        ld (wb_splx),a
        ld (wb_aplx),hl
        ld hl,(ply)             ; |ply| and its sign
        xor a
        bit 7,h
        jr z,wf_ply_pos
        call wb_neg_hl
        ld a,1
wf_ply_pos:
        ld (wb_sply),a
        ld (wb_aply),hl
        ld a,(my0)              ; ptr0 = LEVEL + 8 + my0*32 + mx0
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(mx0)
        db 0EDh,031h            ; add hl,a
        ld de,LEVEL+8
        add hl,de
        ld (wb_ptr0),hl
        xor a
        ld (wb_c),a
wf_loop:
        call walk_column_b
        ld hl,wb_c
        inc (hl)
        bit 7,(hl)
        jr z,wf_loop
        call planes_flush
        ld hl,(frames)
        inc hl
        ld (frames),hl
        ret

; ---------------------------------------------------------------------------------------------------------------
; walk_column_b - column (wb_c): ray (v0.1 section 2), DDA to the first solid cell, floor span, ceiling span, wall
;                 pieces top-down, ZBUF[c] = d  (spec v0.2 section 3). EXHAUST -> VOID(c, 0, 96), ZBUF[c] = 4095.
; ---------------------------------------------------------------------------------------------------------------
walk_column_b:
        ; --- cam_c = 2*c + 1 - 128 (odd, -127..127): B = |cam_c|, C = 1 if cam_c < 0
        ld a,(wb_c)
        add a,a
        inc a
        sub 128
        ld c,0
        bit 7,a
        jr z,wc_camc_pos
        neg
        inc c
wc_camc_pos:
        ld b,a
        ; --- rx = dirx + smul_shr(plx, cam_c, 7): magnitude (|plx| * |cam_c|) >> 7 (|plx| <= 256, |cam_c| <= 127)
        ld e,a
        ld a,(wb_aplx+1)
        or a
        jr nz,wc_rx_256
        ld a,(wb_aplx)
        ld d,a
        db 0EDh,030h            ; DE = |plx|.lo * |cam_c| (<= 32385)
        ex de,hl
        add hl,hl
        ld a,h                  ; (product << 1) >> 8 = product >> 7
        jr wc_rx_mag
wc_rx_256:
        ld a,e
        add a,a                 ; |plx| = 256: (256 * |cam_c|) >> 7 = 2*|cam_c| (<= 254)
wc_rx_mag:
        ld e,a
        ld d,0
        ld hl,(dirx)
        ld a,(wb_splx)
        xor c                   ; exactly one negative operand -> subtract the magnitude
        jr nz,wc_rx_sub
        add hl,de
        jr wc_rx_done
wc_rx_sub:
        or a                    ; (A = 1: clears carry)
        sbc hl,de
wc_rx_done:
        ld (wb_rx),hl
        ; --- ry = diry + smul_shr(ply, cam_c, 7)
        ld e,b
        ld a,(wb_aply+1)
        or a
        jr nz,wc_ry_256
        ld a,(wb_aply)
        ld d,a
        db 0EDh,030h
        ex de,hl
        add hl,hl
        ld a,h
        jr wc_ry_mag
wc_ry_256:
        ld a,e
        add a,a
wc_ry_mag:
        ld e,a
        ld d,0
        ld hl,(diry)
        ld a,(wb_sply)
        xor c
        jr nz,wc_ry_sub
        add hl,de
        jr wc_ry_done
wc_ry_sub:
        or a
        sbc hl,de
wc_ry_done:
        ld (wb_ry),hl
        ; --- y axis: sy, ddy = RECIP[|ry|] (|ry| <= 510, so min(4095, .) never triggers), sdy
        xor a
        bit 7,h
        jr z,wc_ry_pos
        call wb_neg_hl          ; HL = |ry|
        ld a,1
wc_ry_pos:
        ld (wb_syn),a           ; 1 = ry < 0
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = ddy
        ld (wb_ddy),de
        ld a,(wb_syn)
        or a
        jr nz,wc_sdy_neg
        ld a,(py)               ; ry >= 0: sdy = ((256 - fy) * ddy) >> 8   (A = 0 means 256 for wb_side_dist)
        neg
        call wb_side_dist
        jr wc_sdy_done
wc_sdy_neg:
        ld a,(py)               ; ry < 0: sdy = (fy * ddy) >> 8
        or a
        jr z,wc_sdy_zero
        call wb_side_dist
        jr wc_sdy_done
wc_sdy_zero:
        ld hl,0
wc_sdy_done:
        ld (wb_sdy),hl
        ; --- x axis: sx, ddx, sdx -> HL = sdx, BC = ddx
        ld hl,(wb_rx)
        xor a
        bit 7,h
        jr z,wc_rx_pos
        call wb_neg_hl
        ld a,1
wc_rx_pos:
        ld (wb_sxn),a           ; 1 = rx < 0
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = ddx
        ld d,b
        ld e,c
        or a                    ; A = sxn
        jr nz,wc_sdx_neg
        ld a,(px)
        neg
        call wb_side_dist       ; HL = ((256 - fx) * ddx) >> 8
        jr wc_sdx_done
wc_sdx_neg:
        ld a,(px)
        or a
        jr z,wc_sdx_zero
        call wb_side_dist       ; HL = (fx * ddx) >> 8
        jr wc_sdx_done
wc_sdx_zero:
        ld hl,0
wc_sdx_done:
        ; --- DDA registers: HL = sdx, BC = ddx, IX = sdy, DE = ddy ; HL' = cell pointer, E' = mx, D' = my, BC' = +-32
        ld ix,(wb_sdy)
        ld de,(wb_ddy)
        exx
        ld hl,(wb_ptr0)
        ld de,(mx0)             ; E' = mx0, D' = my0 (consecutive bytes in nx_vars.inc)
        ld a,(wb_syn)
        or a
        jr nz,wc_sy_neg
        ld bc,32
        exx
        ld a,(wb_sxn)
        or a
        jp z,dda_pp
        jp dda_np
wc_sy_neg:
        ld bc,0FFE0h
        exx
        ld a,(wb_sxn)
        or a
        jp z,dda_pn
        jp dda_nn

; --- the DDA loops (v0.1 section 4 step 1 until cell(mx, my) != 0): dda_XY, X = sign of sx, Y = sign of sy
dda_pp:                         ; sx = +1, sy = +1
        ld a,h
        cp ixh
        jr c,dda_pp_x           ; sdx < sdy
        jr nz,dda_pp_y
        ld a,l
        cp ixl
        jr c,dda_pp_x
dda_pp_y:                       ; d = sdy ; sdy = sat_add(sdy, ddy) ; my += 1 ; side = 1
        ld (wb_d),ix
        add ix,de
        jr nc,dda_pp_y1
        ld ix,0FFFFh
dda_pp_y1:
        exx
        inc d
        bit 5,d
        jp nz,wc_exhaust_x      ; my = 32: left the map
        add hl,bc
        ld a,(hl)
        exx
        or a
        jp z,dda_pp
        jp wc_hit1
dda_pp_x:                       ; d = sdx ; sdx = sat_add(sdx, ddx) ; mx += 1 ; side = 0
        ld (wb_d),hl
        add hl,bc
        jr nc,dda_pp_x1
        ld hl,0FFFFh
dda_pp_x1:
        exx
        inc e
        bit 5,e
        jp nz,wc_exhaust_x      ; mx = 32
        inc hl
        ld a,(hl)
        exx
        or a
        jp z,dda_pp
        jp wc_hit0

dda_pn:                         ; sx = +1, sy = -1
        ld a,h
        cp ixh
        jr c,dda_pn_x
        jr nz,dda_pn_y
        ld a,l
        cp ixl
        jr c,dda_pn_x
dda_pn_y:
        ld (wb_d),ix
        add ix,de
        jr nc,dda_pn_y1
        ld ix,0FFFFh
dda_pn_y1:
        exx
        dec d
        jp m,wc_exhaust_x       ; my = -1
        add hl,bc               ; BC' = -32
        ld a,(hl)
        exx
        or a
        jp z,dda_pn
        jp wc_hit1
dda_pn_x:
        ld (wb_d),hl
        add hl,bc
        jr nc,dda_pn_x1
        ld hl,0FFFFh
dda_pn_x1:
        exx
        inc e
        bit 5,e
        jp nz,wc_exhaust_x
        inc hl
        ld a,(hl)
        exx
        or a
        jp z,dda_pn
        jp wc_hit0

dda_np:                         ; sx = -1, sy = +1
        ld a,h
        cp ixh
        jr c,dda_np_x
        jr nz,dda_np_y
        ld a,l
        cp ixl
        jr c,dda_np_x
dda_np_y:
        ld (wb_d),ix
        add ix,de
        jr nc,dda_np_y1
        ld ix,0FFFFh
dda_np_y1:
        exx
        inc d
        bit 5,d
        jp nz,wc_exhaust_x
        add hl,bc
        ld a,(hl)
        exx
        or a
        jp z,dda_np
        jp wc_hit1
dda_np_x:
        ld (wb_d),hl
        add hl,bc
        jr nc,dda_np_x1
        ld hl,0FFFFh
dda_np_x1:
        exx
        dec e
        jp m,wc_exhaust_x       ; mx = -1
        dec hl
        ld a,(hl)
        exx
        or a
        jp z,dda_np
        jp wc_hit0

dda_nn:                         ; sx = -1, sy = -1
        ld a,h
        cp ixh
        jr c,dda_nn_x
        jr nz,dda_nn_y
        ld a,l
        cp ixl
        jr c,dda_nn_x
dda_nn_y:
        ld (wb_d),ix
        add ix,de
        jr nc,dda_nn_y1
        ld ix,0FFFFh
dda_nn_y1:
        exx
        dec d
        jp m,wc_exhaust_x
        add hl,bc
        ld a,(hl)
        exx
        or a
        jp z,dda_nn
        jp wc_hit1
dda_nn_x:
        ld (wb_d),hl
        add hl,bc
        jr nc,dda_nn_x1
        ld hl,0FFFFh
dda_nn_x1:
        exx
        dec e
        jp m,wc_exhaust_x
        dec hl
        ld a,(hl)
        exx
        or a
        jp z,dda_nn
        jp wc_hit0

; --- the hit: A = cell code (1..12), (wb_d) = d of the boundary
wc_hit0:
        ld b,a
        xor a                   ; side 0: crossed an x boundary
        jr wc_hit
wc_hit1:
        ld b,a
        ld a,1                  ; side 1: crossed a y boundary
wc_hit:
        ld (wb_side),a
        ld a,b
        and 0Fh
        ld hl,wb_wallmap
        db 0EDh,031h            ; add hl,a
        ld a,(hl)
        ld (pc_tex),a           ; tex = WALLMAP[code]
        ld hl,(wb_d)            ; d = max(d, 8) ; d > 4095 -> EXHAUST
        ld a,h
        cp 10h
        jp nc,wc_exhaust
        or a
        jr nz,wc_d_ok
        ld a,l
        cp 8
        jr nc,wc_d_ok
        ld l,8
wc_d_ok:
        ld (wb_d),hl
        ; R(d) = 2*RECIP[d] (d in 8..4095 -> <= 16384, the min(65535, .) of v0.1 section 3 never triggers)
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        add hl,hl
        ld (wb_r),hl
        ; shade s = shade_tab[d >> 7] ; side 1: min(3, s + 1)
        ld hl,(wb_d)
        ld a,l
        rlca
        and 1
        ld b,a
        ld a,h
        add a,a
        or b                    ; A = d >> 7 (0..31)
        ld hl,wb_shade_tab
        db 0EDh,031h            ; add hl,a
        ld b,(hl)
        ld a,(wb_side)
        or a
        jr z,wc_shade_ok
        inc b
        ld a,b
        cp 4
        jr c,wc_shade_ok
        ld b,3
wc_shade_ok:
        ld a,b
        ld (pc_s),a
        ; texture column: hit = py + smul_shr(ry, d, 8) (side 0) or px + smul_shr(rx, d, 8) (side 1) ; u = (hit & 255) >> 3
        ld a,(wb_side)
        or a
        jr nz,wc_u_side1
        ld hl,(wb_ry)
        ld a,(py)
        jr wc_u
wc_u_side1:
        ld hl,(wb_rx)
        ld a,(px)
wc_u:
        ld (wb_plo),a
        ld de,(wb_d)
        call wb_hit_lo          ; A = low byte of smul_shr(r, d, 8)
        ld hl,wb_plo
        add a,(hl)
        srl a
        srl a
        srl a
        ld (pc_u),a
        ; projections (v0.1 section 3): y(CEIL, d) -> b = ROW ; y(0, d) -> a = ROW ; CEIL = 64: y(32, d) too
        ld a,(wb_ceil)
        ld de,(wb_r)
        call wb_yproj_r
        ld (wb_yc),hl
        call wb_row_of
        ld (wb_rowb),a
        xor a
        ld de,(wb_r)
        call wb_yproj_r
        call wb_row_of
        ld (wb_rowa),a
        ld a,(wb_ceil)
        cp 33
        jr c,wc_proj_done
        ld a,32
        ld de,(wb_r)
        call wb_yproj_r
        ld (wb_y32),hl
        call wb_row_of
        ld (wb_row32),a
wc_proj_done:
        ; --- record order: floor plane, ceiling plane, wall pieces top-down
        ld a,(wb_c)
        ld (pl_c),a
        ld a,(wb_rowa)          ; floor: a = ROW(y_floor) ; if a < 96: PLANE_ADD(c, 0, FTEX, a, 96)
        cp 96
        jr nc,wc_no_floor
        ld (pl_a),a
        ld a,96
        ld (pl_b),a
        xor a
        ld (pl_h),a
        ld a,(wb_ftex)
        ld (pl_tex),a
        call plane_add
wc_no_floor:
        ld a,(wb_rowb)          ; ceiling: b = ROW(y_ceil) ; if b > 0: PLANE_ADD(c, CEIL, CTEX, 0, b)
        or a
        jr z,wc_no_ceil
        ld (pl_b),a
        xor a
        ld (pl_a),a
        ld a,(wb_c)
        ld (pl_c),a
        ld a,(wb_ceil)
        ld (pl_h),a
        ld a,(wb_ctex)
        ld (pl_tex),a
        call plane_add
wc_no_ceil:
        ld hl,(wb_d)            ; dv = d >> 1 (shared by the tiles of this column)
        srl h
        rr l
        ld (pc_dv),hl
        ld a,(wb_ceil)
        cp 33
        jr c,wc_one_tile
        ld a,(wb_rowb)          ; CEIL = 64: tile 64..32 (rows [ROW(y(64)), ROW(y(32))), y_a = y(64))
        ld (wb_pra),a
        ld a,(wb_row32)
        ld (wb_prb),a
        ld hl,(wb_yc)
        ld (wb_pya),hl
        call wb_piece
        ld a,(wb_row32)         ; tile 32..0 (rows [ROW(y(32)), ROW(y(0))), y_a = y(32))
        ld (wb_pra),a
        ld a,(wb_rowa)
        ld (wb_prb),a
        ld hl,(wb_y32)
        ld (wb_pya),hl
        call wb_piece
        jr wc_zbuf
wc_one_tile:
        ld a,(wb_rowb)          ; CEIL = 32: tile 32..0 (rows [b, a), y_a = y(32))
        ld (wb_pra),a
        ld a,(wb_rowa)
        ld (wb_prb),a
        ld hl,(wb_yc)
        ld (wb_pya),hl
        call wb_piece
wc_zbuf:
        ld de,(wb_d)
wc_zbuf_de:                     ; ZBUF[c] = DE
        ld a,(wb_c)
        add a,a
        ld l,a
        ld h,ZBUF / 256
        ld (hl),e
        inc hl
        ld (hl),d
        ret
wc_exhaust_x:                   ; left the map from inside a DDA loop (alternate set active)
        exx
wc_exhaust:                     ; VOID(c, 0, 96) ; ZBUF[c] = 4095
        ld a,(wb_c)
        ld (vd_c),a
        xor a
        ld (vd_a),a
        ld a,96
        ld (vd_b),a
        call void_fill
        ld de,0FFFh
        jr wc_zbuf_de

; ---------------------------------------------------------------------------------------------------------------
; wb_piece - one WALL tile (v0.1 section 4 WALL with ytop = 0, ybot = 96, v_top = 0): ra = (wb_pra), rb = (wb_prb),
;            y_a = (wb_pya), dv = (pc_dv). If ra < rb: v_first = ((ra*256 + 128 - y_a) * dv) >> 8, the v_last > 8191
;            guard, then DRAW_PIECE(c, ra, rb - ra, tex, s, u, v_first, dv) (pc_tex / pc_s / pc_u / pc_dv already set).
; ---------------------------------------------------------------------------------------------------------------
wb_piece:
        ld a,(wb_prb)
        ld hl,wb_pra
        sub (hl)                ; count = rb - ra
        ret z
        ret c
        ld (pc_count),a
        ld a,(wb_pra)
        ld (pc_ra),a
        ld h,a
        ld l,128                ; HL = ra*256 + 128
        ld de,(wb_pya)          ; DE = y_a (signed)
        bit 7,d
        jr z,wbp_sub
        ex de,hl
        call wb_neg_hl          ; HL = |y_a|
        ex de,hl
        add hl,de               ; ra*256 + 128 + |y_a| (<= 24704 + 32768: no carry)
        jr wbp_diff
wbp_sub:
        or a
        sbc hl,de               ; ra*256 + 128 - y_a (>= 0: ra >= ROW(y_a) and ROW(y_a)*256 + 128 >= y_a)
wbp_diff:
        ld de,(pc_dv)
        call wb_umul32          ; DEHL = diff * dv ; q = (diff * dv) >> 8 = D:E:H
        ld a,d
        or a
        jr nz,wbp_guard         ; q >= 65536 > 8191
        ld l,h
        ld h,e                  ; HL = q = v_first before the guard
        ld a,h
        cp 20h
        jr nc,wbp_guard         ; q > 8191
        ld (wb_vraw),hl
        call wb_cnt_dv          ; E:HL = (count - 1) * dv
        ld a,e
        or a
        jr nz,wbp_guard
        ld de,(wb_vraw)
        add hl,de               ; v_last = v_first + (count - 1) * dv
        jr c,wbp_guard
        ld a,h
        cp 20h
        jr nc,wbp_guard         ; v_last > 8191
        ld hl,(wb_vraw)
        jr wbp_v_done
wbp_guard:                      ; v_first -= (v_last - 8191)  ==  v_first = 8191 - (count - 1) * dv ; if < 0: 0
        call wb_cnt_dv
        ld a,e
        or a
        jr nz,wbp_v_zero
        ex de,hl
        ld hl,8191
        or a
        sbc hl,de
        jr nc,wbp_v_done
wbp_v_zero:
        ld hl,0
wbp_v_done:
        ld (pc_v),hl
        ld a,(wb_c)
        ld (pc_c),a
        jp draw_piece

wb_cnt_dv:                      ; E:HL = (count - 1) * dv  (count - 1 <= 95, dv <= 2047)
        ld a,(pc_count)
        dec a
        ld de,(pc_dv)
        jp wb_mul8x16

; ---------------------------------------------------------------------------------------------------------------
; wb_side_dist - v0.1 section 2 initial side distance: HL = (A * DE) >> 8 with A = f (1..255; A = 0 means 256) and
;                DE = dd (0..65535). (256 * 65535) >> 8 = 65535: the min(65535, .) never triggers. destroys A, DE
; ---------------------------------------------------------------------------------------------------------------
wb_side_dist:
        or a
        jr nz,wsd_mul
        ex de,hl                ; f = 256: result = dd
        ret
wsd_mul:
        ld h,d                  ; H = dd.hi
        ld d,a                  ; D = f, E = dd.lo
        db 0EDh,030h            ; DE = f * dd.lo
        ld l,d                  ; L = (f * dd.lo) >> 8
        ld d,a
        ld e,h                  ; D = f, E = dd.hi
        ld h,0                  ; HL = (f * dd.lo) >> 8
        db 0EDh,030h            ; DE = f * dd.hi
        add hl,de               ; (f * dd) >> 8 = ((f*lo) >> 8) + f*hi  (<= 255 + 65025: no carry)
        ret

; ---------------------------------------------------------------------------------------------------------------
; wb_hit_lo - v0.1 section 4 step 4: A = low byte of smul_shr(HL, DE, 8) with HL = rx or ry (signed, |HL| <= 510) and
;             DE = d (8..4095). |r|*d = P + 256*M + 65536*T with P = rl*dl, M = rl*dh + rh*dl -> (|r|*d >> 8) & 255 =
;             (P.hi + M.lo) & 255 ; negated when exactly one operand is negative. destroys A, BC, DE, HL
; ---------------------------------------------------------------------------------------------------------------
wb_hit_lo:
        ld c,0
        bit 7,h
        jr z,whl_pos
        call wb_neg_hl          ; HL = |r|
        inc c
whl_pos:
        ld a,h                  ; A = rh
        ld b,d                  ; B = dh
        ld h,e                  ; H = dl ; L = rl
        ld d,l
        ld e,b                  ; D = rl, E = dh
        db 0EDh,030h            ; DE = rl*dh
        ld b,e                  ; B = (rl*dh).lo
        ld d,a
        ld e,h                  ; D = rh, E = dl
        db 0EDh,030h            ; DE = rh*dl
        ld a,e
        add a,b                 ; A = M.lo
        ld d,l
        ld e,h                  ; D = rl, E = dl
        db 0EDh,030h            ; DE = rl*dl = P
        add a,d                 ; A = (M.lo + P.hi) & 255
        dec c
        ret nz                  ; positive
        neg                     ; exactly one negative operand
        ret

; ---------------------------------------------------------------------------------------------------------------
; wb_umul32 - unsigned 16x16 -> 32: in HL = a, DE = b ; out DEHL = a*b. destroys A, BC, (wb_mp0), (wb_mp3)
; ---------------------------------------------------------------------------------------------------------------
wb_umul32:
        ld b,h                  ; B = ah
        ld c,l                  ; C = al
        ld a,d                  ; A = bh
        ld d,c                  ; D = al, E = bl
        push de
        db 0EDh,030h            ; DE = al*bl = p0
        ld (wb_mp0),de
        pop de
        ld d,b                  ; D = ah, E = bl
        push de
        db 0EDh,030h            ; DE = ah*bl = p2
        ld (wb_mp3),de
        pop de
        ld e,a                  ; D = ah, E = bh
        push de
        db 0EDh,030h            ; DE = ah*bh = p3
        ld h,d
        ld l,e                  ; HL = p3
        pop de
        ld d,c                  ; D = al, E = bh
        db 0EDh,030h            ; DE = al*bh = p1
        ex de,hl                ; HL = p1, DE = p3
        ld bc,(wb_mp3)          ; BC = p2
        add hl,bc               ; HL = (p1 + p2) low 16, CY = bit 16
        ld b,0
        rl b
        ld a,(wb_mp0)
        ld c,a                  ; C = byte 0
        ld a,(wb_mp0+1)
        add a,l
        ld l,a                  ; byte 1
        ld a,e
        adc a,h
        ld e,a                  ; byte 2
        ld a,d
        adc a,b
        ld d,a                  ; byte 3
        ld h,l
        ld l,c
        ret

; ---------------------------------------------------------------------------------------------------------------
; wb_mul8x16 - A * DE -> E:HL (24 bits). destroys A, B, D
; ---------------------------------------------------------------------------------------------------------------
wb_mul8x16:
        ld b,a
        ld h,d
        ld d,a                  ; D = a, E = b.lo
        db 0EDh,030h            ; DE = a*b.lo = P
        ld l,e
        ld a,d                  ; A = P.hi
        ld d,b
        ld e,h                  ; D = a, E = b.hi
        db 0EDh,030h            ; DE = a*b.hi = Q
        add a,e
        ld h,a                  ; byte 1 = P.hi + Q.lo
        ld a,d
        adc a,0
        ld e,a                  ; byte 2
        ret

; ---------------------------------------------------------------------------------------------------------------
; wb_yproj_r - v0.1 section 3 with R(d) known: y_q8 = 48*256 - (h - eye) * R, clamped to [-32768, 32767].
;              in: A = h (int8 H32), DE = R (0..65535) ; out: HL = y_q8 ; destroys A, BC, DE. |h - eye| <= 255 ->
;              8x16 magnitude product; a product >= 65536 is beyond the int16 clamp on either side.
; ---------------------------------------------------------------------------------------------------------------
wb_yproj_r:
        ld b,a
        ld a,(eye)
        ld c,a
        ld a,b
        sub c                   ; A = low byte of (h - eye) ; P/V = signed overflow
        jp z,wby_center
        jp pe,wby_dh_ovf
        ld c,0
        bit 7,a
        jr z,wby_mul
        neg
        ld c,1
        jr wby_mul
wby_dh_ovf:
        ld c,0                  ; overflow: bit 7 set means +128..+255 (magnitude = A unsigned)
        bit 7,a
        jr nz,wby_mul
        neg                     ; bit 7 clear means -255..-129 (magnitude = 256 - A)
        ld c,1
wby_mul:                        ; A = |h - eye| (1..255), C = 1 if h - eye < 0, DE = R
        ld b,a
        ld h,d
        ld d,a                  ; D = |dh|, E = R.lo
        db 0EDh,030h            ; DE = |dh| * R.lo = P
        ld l,e
        ld a,d                  ; A = P.hi
        ld d,b
        ld e,h                  ; D = |dh|, E = R.hi
        db 0EDh,030h            ; DE = |dh| * R.hi = Q
        add a,e
        ld h,a                  ; HL = product low 16 bits ; CY = bit 16
        jr c,wby_saturate
        ld a,d
        or a
        jr nz,wby_saturate      ; product >= 65536
        ex de,hl                ; DE = product
        ld a,c
        or a
        jr nz,wby_dh_neg
        ld hl,0B000h            ; h - eye > 0: y = 12288 - product ; product > 45056 -> -32768
        sbc hl,de
        jp c,wby_min
        ld hl,3000h
        or a
        sbc hl,de
        ret
wby_dh_neg:
        ld hl,4FFFh             ; h - eye < 0: y = 12288 + product ; product > 20479 -> 32767
        or a
        sbc hl,de
        jp c,wby_max
        ld hl,3000h
        add hl,de
        ret
wby_saturate:
        ld a,c
        or a
        jp nz,wby_max
wby_min:
        ld hl,8000h             ; -32768
        ret
wby_max:
        ld hl,7FFFh             ; 32767
        ret
wby_center:
        ld hl,3000h             ; 48*256
        ret

; ---------------------------------------------------------------------------------------------------------------
; wb_row_of - v0.1 section 0: ROW(y) = clamp((y + 127) >> 8, 0, 96), y signed (HL) -> A. destroys A
; ---------------------------------------------------------------------------------------------------------------
wb_row_of:
        bit 7,h
        jr nz,wbr_zero
        ld a,l
        add a,127
        ld a,h
        adc a,0
        cp 97
        ret c
        ld a,96
        ret
wbr_zero:
        xor a
        ret

wb_neg_hl:                      ; HL = -HL, destroys A
        xor a
        sub l
        ld l,a
        ld a,0
        sbc a,h
        ld h,a
        ret

walk_b_end:
