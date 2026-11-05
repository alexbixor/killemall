; walk.asm - Kill'em all Spectrum Next engine, lane D1: the column walker.
; Implements docs/next_engine_spec_v0.1.md sections 2 (camera and rays), 3 (projection) and 4 (column walk, WALL tiles)
; exactly; every formula is tagged with the spec section it implements.
; No org here (spec section 10): main.asm / test_walk.asm set org 8000h and include nx_vars.inc + walk_vars.inc first.
; Entry points: setup_camera, walk_frame (walk_column is internal). The walker CALLs lane D2's planes_reset, plane_add,
; draw_piece, void_fill, planes_flush after filling their parameter blocks (nx_vars.inc). The drawers may destroy every
; register except SP, so ALL walker state lives in RAM (walk_vars.inc) and is reloaded after each call.
; Z80N opcodes written as db: mul d,e = 0EDh,030h (DE = D*E, unsigned 8x8 -> 16) ; add hl,a = 0EDh,031h.
; Lane S (speed, 5 Nov): same output byte for byte, less work:
;   - R(d) = 2*RECIP[d] is looked up once per walk step (w_rd) and carried over as R(dprev) (w_rdp); in the walk d is
;     always 8..4095 (step 1), so the min(65535, ...) and the 8..4095 clamps of section 3 can never trigger there.
;   - yproj_r projects with one 8x16 hardware product (|h - eye| <= 255 times R) instead of the generic 16x16 umul32.
;   - the texture column (section 4 step 4) only needs the low byte of (|r| * d) >> 8: hit_lo computes exactly that with
;     three 8x8 products instead of smul_shr's 16x16 product and an 8-step shift loop.
;   - the ray setup (section 2) uses 9x7 / 9x16 products (ray_comp, mul_shr8): |plx|, |ply| <= 256, |cam_c| <= 127,
;     fx <= 256, and (256 * 65535) >> 8 = 65535 so the saturation of sdx/sdy never triggers.
;   - the row of the previous step's projection is cached per surface (w_fh/w_frow floor, w_ch/w_crow ceiling): at the
;     next step, ROW(y(cur.floor, dprev)) is exactly the value computed one step earlier when the height did not change.
;   - the tile count product (count - 1) * dv is an 8x16 product (mul8x16).
;   The generic umul32 / smul_shr / yproj stay: main.asm (movement) and the unit vectors of test_walk.asm use them.

; ---- lane S scratch (inside WALK_VARS 5840h..58FFh, after lane D1's last variable w_camc at 587Ah)
w_rd        equ 587Ch           ; word  R(d) = 2*RECIP[d] of the boundary just crossed (d in 8..4095 -> never saturates)
w_rdp       equ 587Eh           ; word  R(dprev)
w_fh        equ 5880h           ; byte  floor cache: height whose row at depth d (= dprev of the next step) is w_frow
w_frow      equ 5881h           ; byte  ROW(y(w_fh, d)) ; 255 = no value cached
w_ch        equ 5882h           ; byte  ceiling cache height
w_crow      equ 5883h           ; byte  ceiling cache row ; 255 = none
; Coalescer (only assembled when the including program defines WALK_COALESCE, as main.asm does; the test wrapper does not,
; so tools/nx_test_walk.py still sees the spec's call list record by record): consecutive PLANE_ADD spans of one column
; with the same (h, tex) and touching rows are merged in the walker before plane_add sees them. Pixels are identical
; because the colour of (c, row) depends only on (h, tex, c, row) (spec 5) and plane_add merges the same way.
w_pf        equ 5884h           ; 5 bytes: pending floor span: on (0/1), h, tex, a, b
w_pc        equ 5889h           ; 5 bytes: pending ceiling span
; shade table (spec 4 step 4): s = 0 if d < 384, 1 if d < 768, 2 if d < 1536 else 3, indexed by d >> 7 (0..31)

walk_begin:
shade_tab:
        db 0,0,0,1,1,1,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3

; ---------------------------------------------------------------------------------------------------------------
; umul32 - unsigned 16x16 -> 32 product.  in: HL = a, DE = b ; out: DEHL = a*b (D = most significant byte)
; destroys A, BC, (mul_p0), (mul_p3). Four 8x8 partial products with Z80N mul d,e:
;   a*b = al*bl + (al*bh + ah*bl) << 8 + ah*bh << 16
; ---------------------------------------------------------------------------------------------------------------
umul32:
        ld b,h                  ; B = ah
        ld c,l                  ; C = al
        ld a,d                  ; A = bh
        ld d,c                  ; D = al, E = bl
        push de
        db 0EDh,030h            ; mul d,e : DE = al*bl = p0
        ld (mul_p0),de
        pop de                  ; D = al, E = bl
        ld d,b                  ; D = ah, E = bl
        push de
        db 0EDh,030h            ; DE = ah*bl = p2
        ld (mul_p3),de          ; (temporarily holds p2)
        pop de                  ; D = ah, E = bl
        ld e,a                  ; D = ah, E = bh
        push de
        db 0EDh,030h            ; DE = ah*bh = p3
        ld h,d
        ld l,e                  ; HL = p3
        pop de                  ; D = ah, E = bh
        ld d,c                  ; D = al, E = bh
        db 0EDh,030h            ; DE = al*bh = p1
        ex de,hl                ; HL = p1, DE = p3
        ld bc,(mul_p3)          ; BC = p2
        add hl,bc               ; HL = (p1 + p2) low 16 bits, CY = bit 16
        ld b,0
        rl b                    ; B = bit 16 of the middle sum
        ld a,(mul_p0)
        ld c,a                  ; C = result byte 0
        ld a,(mul_p0+1)
        add a,l                 ; byte 1 = p0.hi + mid.lo
        ld l,a
        ld a,e
        adc a,h                 ; byte 2 = p3.lo + mid.mid + carry
        ld e,a
        ld a,d
        adc a,b                 ; byte 3 = p3.hi + mid.bit16 + carry
        ld d,a
        ld h,l                  ; H = byte 1
        ld l,c                  ; L = byte 0
        ret

; ---------------------------------------------------------------------------------------------------------------
; mul8x16 - A * DE -> E:HL (24-bit product, E = bits 16..23). destroys A, B, D
; ---------------------------------------------------------------------------------------------------------------
mul8x16:
        ld b,a                  ; B = a
        ld h,d                  ; H = b.hi
        ld d,a                  ; D = a, E = b.lo
        db 0EDh,030h            ; DE = a*b.lo = P
        ld l,e                  ; L = P.lo = byte 0
        ld a,d                  ; A = P.hi
        ld d,b
        ld e,h                  ; D = a, E = b.hi
        db 0EDh,030h            ; DE = a*b.hi = Q
        add a,e
        ld h,a                  ; byte 1 = P.hi + Q.lo
        ld a,d
        adc a,0
        ld e,a                  ; byte 2 = Q.hi + carry
        ret

; ---------------------------------------------------------------------------------------------------------------
; mul_shr8 - section 2 initial side distance: HL = (HL * DE) >> 8 with HL = fx or 256 - fx (0..256), DE = ddx (0..65535).
;            (256 * 65535) >> 8 = 65535, so the spec's min(65535, ...) can never trigger. destroys A, DE
; ---------------------------------------------------------------------------------------------------------------
mul_shr8:
        ld a,h
        or a
        jr z,ms_lo
        ex de,hl                ; HL = 256 (L = 0): result = DE
        ret
ms_lo:
        ld a,l                  ; A = a (0..255)
        ld h,d                  ; H = b.hi
        ld d,a                  ; D = a, E = b.lo
        db 0EDh,030h            ; DE = a*b.lo = P
        ld l,d                  ; L = P.hi
        ld d,a
        ld e,h                  ; D = a, E = b.hi
        db 0EDh,030h            ; DE = a*b.hi = Q
        ld h,0                  ; HL = P.hi
        add hl,de               ; (a*b) >> 8 = P.hi + Q  (<= 255 + 65025, no carry)
        ret

; ---------------------------------------------------------------------------------------------------------------
; ray_comp - section 2: HL = smul_shr(HL, A, 7) with HL = plx or ply (signed, |HL| <= 256) and A = cam_c (int8,
;            |A| <= 127): |HL| * |A| <= 32512 fits 16 bits. destroys A, BC, DE
; ---------------------------------------------------------------------------------------------------------------
ray_comp:
        ld c,0                  ; C = number of negative operands
        bit 7,a
        jr z,rc_a_pos
        neg
        inc c
rc_a_pos:
        ld e,a                  ; E = |cam_c|
        bit 7,h
        jr z,rc_b_pos
        call neg_hl             ; HL = |plx| (destroys A only)
        inc c
rc_b_pos:
        ld b,e                  ; B = |cam_c|
        ld a,h                  ; A = |plx|.hi (0 or 1)
        ld d,l                  ; D = |plx|.lo, E = |cam_c|
        db 0EDh,030h            ; DE = lo * camc (<= 255*127 = 32385)
        ex de,hl
        add hl,hl               ; no overflow (< 32768)
        ld l,h
        ld h,0                  ; HL = (lo * camc) >> 7
        or a
        jr z,rc_shifted
        ld a,b
        add a,a                 ; (256 * camc) >> 7 = 2 * camc (<= 254)
        db 0EDh,031h            ; add hl,a
rc_shifted:
        dec c
        ret nz                  ; 0 or 2 negative operands -> positive
        jp neg_hl

; ---------------------------------------------------------------------------------------------------------------
; hit_lo - section 4 step 4: A = low byte of smul_shr(HL, DE, 8) with HL = rx or ry (signed, |HL| <= 510) and
;          DE = d (8..4095). Only (hit & 255) is used by the caller, so only the low byte of r = (|r|*d) >> 8 is needed:
;          |r|*d = P + 256*M + 65536*T with P = rl*dl, M = rl*dh + rh*dl -> r & 255 = (P.hi + M.lo) & 255.
;          destroys A, BC, DE, HL
; ---------------------------------------------------------------------------------------------------------------
hit_lo:
        ld c,0
        bit 7,h
        jr z,hl_pos
        call neg_hl             ; HL = |r|
        inc c
hl_pos:
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
        add a,d                 ; A = (M.lo + P.hi) & 255 = r & 255
        dec c
        ret nz                  ; positive
        neg                     ; exactly one negative operand: (-r) & 255
        ret

; ---------------------------------------------------------------------------------------------------------------
; smul_shr - spec section 0: r = (|a|*|b|) >> s ; result = -r if exactly one of a, b is negative, else r.
; in: HL = a (signed 16), DE = b (signed 16), A = s (0..31) ; out: DEHL = result as a signed 32-bit two's complement
; destroys A, BC
; ---------------------------------------------------------------------------------------------------------------
smul_shr:
        ld c,a                  ; C = shift count
        ld b,0                  ; B = number of negative operands
        bit 7,h
        jr z,sm_a_ok
        call neg_hl             ; HL = |a|
        inc b
sm_a_ok:
        bit 7,d
        jr z,sm_b_ok
        ex de,hl
        call neg_hl             ; DE = |b|
        ex de,hl
        inc b
sm_b_ok:
        push bc
        call umul32             ; DEHL = |a|*|b|
        pop bc
        ld a,c
        or a
        jr z,sm_shifted
sm_shift:
        srl d                   ; DEHL >>= 1 (logical: it is a magnitude)
        rr e
        rr h
        rr l
        dec a
        jr nz,sm_shift
sm_shifted:
        bit 0,b
        ret z                   ; both or none negative -> positive result
neg32:                          ; DEHL = -DEHL
        xor a
        sub l
        ld l,a
        ld a,0
        sbc a,h
        ld h,a
        ld a,0
        sbc a,e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a
        ret

neg_hl:                         ; HL = -HL (0 - HL), destroys A
        xor a
        sub l
        ld l,a
        ld a,0
        sbc a,h
        ld h,a
        ret

; ---------------------------------------------------------------------------------------------------------------
; max8 / min8 - A = max(A, (HL)) / A = min(A, (HL)), unsigned bytes (rows 0..96)
; ---------------------------------------------------------------------------------------------------------------
max8:
        cp (hl)
        ret nc
        ld a,(hl)
        ret
min8:
        cp (hl)
        ret c
        ld a,(hl)
        ret

; ---------------------------------------------------------------------------------------------------------------
; cell_ptr - spec sections 4/7: HL -> the 4 bytes of cell (B = mx, C = my) = LEVEL + (my*32 + mx)*4 ;
;            outside 0..31 x 0..15 -> solid stone (0, 0, 80h, 0). destroys A
; ---------------------------------------------------------------------------------------------------------------
cell_ptr:
        ld a,b
        cp LEVEL_W
        jr nc,cp_outside
        ld a,c
        cp LEVEL_H
        jr nc,cp_outside
        rrca                    ; bit 7 = my & 1, bits 0..6 = my >> 1 (my < 16)
        ld l,a
        and 7Fh
        add a,LEVEL / 256       ; high byte = LEVEL.hi + (my >> 1)   (my*128 = (my>>1)*256 + (my&1)*128)
        ld h,a
        ld a,l
        and 80h                 ; (my & 1) * 128
        ld l,a
        ld a,b
        add a,a
        add a,a                 ; mx*4 (0..124)
        add a,l                 ; no carry: <= 128 + 124
        ld l,a
        ret
cp_outside:
        ld hl,solid_cell
        ret
solid_cell:
        db 0,0,80h,0            ; spec section 7: outside the map = solid stone (wtex 0)

; ---------------------------------------------------------------------------------------------------------------
; recip_lookup - spec section 2: DE = RECIP[min(4095, HL)]  (HL unsigned).  destroys A, HL
; ---------------------------------------------------------------------------------------------------------------
recip_lookup:
        ld a,h
        cp 10h
        jr c,rl_ok
        ld hl,0FFFh             ; min(4095, |r|)
rl_ok:
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ret

; ---------------------------------------------------------------------------------------------------------------
; r_of_d - section 3: DE = R(d) = min(65535, 2*RECIP[d]) for HL = d already in 8..4095 (so 2*RECIP[d] <= 16384 and the
;          min never triggers). destroys HL
; ---------------------------------------------------------------------------------------------------------------
r_of_d:
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = RECIP[d]
        ex de,hl
        add hl,hl               ; 2*RECIP[d]
        ex de,hl
        ret

; ---------------------------------------------------------------------------------------------------------------
; yproj_r - spec section 3 with R(d) already known: y_q8 = 48*256 - (h - eye) * R, clamped to [-32768, 32767].
;           in: A = h (int8 H32), DE = R (0..65535) ; out: HL = y_q8 ; destroys A, BC, DE
;           |h - eye| <= 255 (both int8), so the magnitude product is an 8x16 -> 24-bit product; a product >= 65536 lies
;           beyond the int16 clamp on either side (12288 - 65536 < -32768 ; 12288 + 65536 > 32767).
; ---------------------------------------------------------------------------------------------------------------
yproj_r:
        ld b,a                  ; B = h
        ld a,(eye)
        ld c,a
        ld a,b
        sub c                   ; A = low byte of (h - eye); S = bit 7, P/V = signed overflow (|h - eye| may reach 255)
        jp z,yp_center          ; (h - eye) = 0 -> y = 48*256
        jp pe,ypr_dh_ovf
        ld c,0                  ; no overflow: C = 0 (h - eye > 0) or 1 (h - eye < 0), A = |h - eye|
        bit 7,a
        jr z,ypr_mul
        neg
        ld c,1
        jr ypr_mul
ypr_dh_ovf:
        ld c,0                  ; overflow: bit 7 set means the true value is +128..+255 (magnitude = A as unsigned)
        bit 7,a
        jr nz,ypr_mul
        neg                     ; bit 7 clear means the true value is -255..-129 (magnitude = 256 - A)
        ld c,1
ypr_mul:                        ; A = |h - eye| (1..255), C = sign, DE = R
        ld b,a
        ld h,d                  ; H = R.hi
        ld d,a                  ; D = |dh|, E = R.lo
        db 0EDh,030h            ; DE = |dh| * R.lo = P
        ld l,e                  ; L = P.lo
        ld a,d                  ; A = P.hi
        ld d,b
        ld e,h                  ; D = |dh|, E = R.hi
        db 0EDh,030h            ; DE = |dh| * R.hi = Q
        add a,e                 ; byte 1 = P.hi + Q.lo ; carry = bit 16 of the product
        ld h,a                  ; HL = product low 16 bits
        jr c,ypr_saturate
        ld a,d                  ; Q.hi = bits 16..23 (no carry into them)
        or a
        jr nz,ypr_saturate      ; product >= 65536 -> beyond the int16 clamp either way
        ex de,hl                ; DE = product (16 bits)
        ld a,c
        or a
        jr nz,ypr_dh_neg
        ld hl,0B000h            ; h - eye > 0: y = 12288 - product ; product > 45056 -> -32768
        sbc hl,de               ; (carry clear after or a)
        jp c,yp_min
        ld hl,3000h
        or a
        sbc hl,de               ; HL = 12288 - product
        ret
ypr_dh_neg:
        ld hl,4FFFh             ; h - eye < 0: y = 12288 + product ; product > 20479 -> 32767
        or a
        sbc hl,de
        jp c,yp_max
        ld hl,3000h
        add hl,de               ; HL = 12288 + product
        ret
ypr_saturate:
        ld a,c
        or a
        jp nz,yp_max
        jp yp_min

; ---------------------------------------------------------------------------------------------------------------
; yproj - spec section 3: y_q8 = 48*256 - (h - eye) * R(d), R(d) = min(65535, 2*RECIP[clamp(d, 8, 4095)]),
;         y_q8 clamped to [-32768, 32767].  in: A = h (int8 H32), DE = d (Q8) ; out: HL = y_q8 ; destroys A, BC, DE
;         (generic version with the clamps: used by the unit vectors of test_walk.asm; the walk uses yproj_r)
; ---------------------------------------------------------------------------------------------------------------
yproj:
        ld b,a                  ; B = h
        ld a,d
        cp 10h
        jr c,yp_dhi_ok
        ld de,0FFFh             ; clamp d to 4095
        jr yp_dok
yp_dhi_ok:
        or a
        jr nz,yp_dok
        ld a,e
        cp 8
        jr nc,yp_dok
        ld e,8                  ; clamp d to 8
yp_dok:
        ex de,hl
        add hl,hl
        ld de,RECIP_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = RECIP[d]
        ex de,hl
        add hl,hl               ; 2*RECIP[d]
        jr nc,yp_r_ok
        ld hl,0FFFFh            ; min(65535, ...)
yp_r_ok:
        ex de,hl                ; DE = R(d)
        ld a,b
        jp yproj_r
yp_min:
        ld hl,8000h             ; -32768
        ret
yp_max:
        ld hl,7FFFh             ; 32767
        ret
yp_center:
        ld hl,3000h             ; 48*256
        ret

; ---------------------------------------------------------------------------------------------------------------
; row_of - spec section 0: ROW(y) = clamp((y + 127) >> 8, 0, 96), y signed, arithmetic shift.
;          For y < 0, y + 127 <= 126 so the arithmetic shift gives <= 0 -> ROW = 0. For y >= 0 the sum is < 65536 and
;          (y + 127) >> 8 is its high byte (<= 128), then min 96.  in: HL = y ; out: A = row ; destroys A
; ---------------------------------------------------------------------------------------------------------------
row_of:
        bit 7,h
        jr nz,ro_zero
        ld a,l
        add a,127
        ld a,h
        adc a,0                 ; (y + 127) >> 8
        cp 97
        ret c
        ld a,96
        ret
ro_zero:
        xor a
        ret

; ---------------------------------------------------------------------------------------------------------------
; setup_camera - spec section 2: dirx = COS[a], diry = SIN[a], plx = -SIN[a], ply = COS[a], mx0 = px >> 8,
;                my0 = py >> 8, eye = floor(cell(mx0, my0)) + 22 (H32). Reads px, py, ang (nx_vars.inc).
; ---------------------------------------------------------------------------------------------------------------
setup_camera:
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
        ld (dirx),de            ; dirx = COS[a]
        ld (ply),de             ; ply = COS[a]
        pop hl
        ld de,SIN_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = SIN[a]
        ld (diry),de            ; diry = SIN[a]
        ex de,hl
        call neg_hl
        ld (plx),hl             ; plx = -SIN[a]
        ld a,(px+1)
        ld (mx0),a              ; mx0 = px >> 8
        ld b,a
        ld a,(py+1)
        ld (my0),a              ; my0 = py >> 8
        ld c,a
        call cell_ptr
        ld a,(hl)               ; floor of the start cell
        add a,22
        ld (eye),a              ; eye = floor + 22
        ret

; ---------------------------------------------------------------------------------------------------------------
; walk_frame - spec section 8/10: planes_reset ; columns 0..127 ; planes_flush ; frames += 1
; ---------------------------------------------------------------------------------------------------------------
walk_frame:
        call planes_reset
        xor a
        ld (w_c),a
wf_loop:
        call walk_column
        ld a,(w_c)
        inc a
        ld (w_c),a
        cp 128
        jr nz,wf_loop
        call planes_flush
        ld hl,(frames)
        inc hl
        ld (frames),hl
        ret

; ---------------------------------------------------------------------------------------------------------------
; walk_column - spec section 2 (ray of column w_c) + section 4 (the walk). Writes ZBUF[c].
; ---------------------------------------------------------------------------------------------------------------
walk_column:
        ; --- section 2: cam_c = 2*c + 1 - 128 (odd, -127..127)
        ld a,(w_c)
        add a,a
        inc a
        sub 128                 ; A = cam_c (int8)
        ld (w_camc),a
        ; rx = dirx + smul_shr(plx, cam_c, 7)
        ld hl,(plx)
        call ray_comp
        ld de,(dirx)
        add hl,de
        ld (w_rx),hl
        ; ry = diry + smul_shr(ply, cam_c, 7)
        ld a,(w_camc)
        ld hl,(ply)
        call ray_comp
        ld de,(diry)
        add hl,de
        ld (w_ry),hl
        ; sx = -1 if rx < 0 else +1 ; ddx = RECIP[min(4095, |rx|)]
        ld hl,(w_rx)
        ld a,1
        bit 7,h
        jr z,wc_rx_pos
        call neg_hl
        ld a,0FFh
wc_rx_pos:
        ld (w_sx),a
        call recip_lookup
        ld (w_ddx),de
        ; sy, ddy likewise
        ld hl,(w_ry)
        ld a,1
        bit 7,h
        jr z,wc_ry_pos
        call neg_hl
        ld a,0FFh
wc_ry_pos:
        ld (w_sy),a
        call recip_lookup
        ld (w_ddy),de
        ; sdx = (fx*ddx) >> 8 if rx < 0 else ((256 - fx)*ddx) >> 8, fx = px & 255 (saturation impossible: see mul_shr8)
        ld a,(px)
        ld l,a
        ld h,0                  ; HL = fx
        ld a,(w_sx)
        cp 1
        jr nz,wc_sdx_neg
        ex de,hl
        ld hl,256
        or a
        sbc hl,de               ; HL = 256 - fx
wc_sdx_neg:
        ld de,(w_ddx)
        call mul_shr8           ; HL = HL*DE >> 8
        ld (w_sdx),hl
        ; sdy likewise with fy, ry
        ld a,(py)
        ld l,a
        ld h,0
        ld a,(w_sy)
        cp 1
        jr nz,wc_sdy_neg
        ex de,hl
        ld hl,256
        or a
        sbc hl,de
wc_sdy_neg:
        ld de,(w_ddy)
        call mul_shr8
        ld (w_sdy),hl
        ; --- section 4 state: ytop = 0, ybot = 96, cur = cell(mx0, my0), dprev = 8 (R(8) in w_rdp), 48 steps, caches empty
        ld a,(mx0)
        ld (w_mx),a
        ld b,a
        ld a,(my0)
        ld (w_my),a
        ld c,a
        call cell_ptr
        ld de,w_cur
        ld bc,4
        ldir                    ; cur = cell(mx, my)
        xor a
        ld (w_ytop),a
        ld a,96
        ld (w_ybot),a
        ld hl,8
        call r_of_d
        ld (w_rdp),de           ; R(dprev) with dprev = 8
        ld a,255
        ld (w_frow),a
        ld (w_crow),a
    IF DEFINED WALK_COALESCE
        xor a
        ld (w_pf),a             ; no pending plane spans
        ld (w_pc),a
    ENDIF
        ld a,48
        ld (w_steps),a
wc_loop:
        ; --- step 1: advance to the next boundary
        ld hl,(w_sdx)
        ld de,(w_sdy)
        or a
        sbc hl,de
        jr c,wc_step_x          ; sdx < sdy
        ld hl,(w_sdy)           ; d = sdy ; sdy = sat_add(sdy, ddy) ; my += sy ; side = 1
        ld (w_d),hl
        ld de,(w_ddy)
        add hl,de
        jr nc,wc_sdy_ok
        ld hl,0FFFFh
wc_sdy_ok:
        ld (w_sdy),hl
        ld a,(w_my)
        ld hl,w_sy
        add a,(hl)
        ld (w_my),a
        ld a,1
        ld (w_side),a
        jr wc_step_d
wc_step_x:
        ld hl,(w_sdx)           ; d = sdx ; sdx = sat_add(sdx, ddx) ; mx += sx ; side = 0
        ld (w_d),hl
        ld de,(w_ddx)
        add hl,de
        jr nc,wc_sdx_ok
        ld hl,0FFFFh
wc_sdx_ok:
        ld (w_sdx),hl
        ld a,(w_mx)
        ld hl,w_sx
        add a,(hl)
        ld (w_mx),a
        xor a
        ld (w_side),a
wc_step_d:
        ld hl,(w_d)             ; d = max(d, 8)
        ld a,h
        or a
        jr nz,wc_d_ge8
        ld a,l
        cp 8
        jr nc,wc_d_ge8
        ld hl,8
        ld (w_d),hl
wc_d_ge8:
        ld a,h
        cp 10h
        jp nc,wc_exhaust        ; d > 4095 -> EXHAUST
        ld a,(w_mx)
        cp LEVEL_W
        jp nc,wc_exhaust        ; left the map -> EXHAUST
        ld a,(w_my)
        cp LEVEL_H
        jp nc,wc_exhaust
        ; R(d) for this step (d is 8..4095 here)
        ld hl,(w_d)
        call r_of_d
        ld (w_rd),de
        ; --- step 2: FLOOR of cur: ya = ROW(y(cur.floor, d)), yb = ROW(y(cur.floor, dprev))
        ;     yb is the row cached by the previous step (its ya, or its step-6 row) when the floor height is unchanged
        ld a,(w_cur+0)
        ld hl,w_fh
        cp (hl)
        jr nz,wc_fyb_calc
        inc hl                  ; HL -> w_frow
        ld a,(hl)
        cp 255
        jr z,wc_fyb_calc
        ld (w_yb),a
        jr wc_fyb_done
wc_fyb_calc:
        ld a,(w_cur+0)
        ld de,(w_rdp)
        call yproj_r
        call row_of
        ld (w_yb),a
wc_fyb_done:
        ld a,(w_cur+0)
        ld (w_fh),a
        ld de,(w_rd)
        call yproj_r
        call row_of
        ld (w_ya),a
        ld (w_frow),a           ; cache: ROW(y(cur.floor, d)) for the next step's yb
        ld a,(w_cur+3)
        and 0Fh
        ld (pl_tex),a           ; cur.ftex
        ld a,(w_cur+0)
        ld (pl_h),a             ; cur.floor
        ld ix,w_pf
        call plane_span         ; a = max(ya, ytop), b = min(yb, ybot) ; if a < b: PLANE_ADD
        ld a,(w_ytop)           ; ybot = min(ybot, max(ytop, ya))
        ld hl,w_ya
        call max8
        ld hl,w_ybot
        call min8
        ld (w_ybot),a
        ; --- step 3: CEILING of cur: ya = ROW(y(cur.ceil, dprev)) (cached when unchanged), yb = ROW(y(cur.ceil, d))
        ld a,(w_cur+1)
        ld hl,w_ch
        cp (hl)
        jr nz,wc_cya_calc
        inc hl                  ; HL -> w_crow
        ld a,(hl)
        cp 255
        jr z,wc_cya_calc
        ld (w_ya),a
        jr wc_cya_done
wc_cya_calc:
        ld a,(w_cur+1)
        ld de,(w_rdp)
        call yproj_r
        call row_of
        ld (w_ya),a
wc_cya_done:
        ld a,(w_cur+1)
        ld (w_ch),a
        ld de,(w_rd)
        call yproj_r
        call row_of
        ld (w_yb),a
        ld (w_crow),a           ; cache: ROW(y(cur.ceil, d)) for the next step's ya
        ld a,(w_cur+3)
        rrca
        rrca
        rrca
        rrca
        and 0Fh
        ld (pl_tex),a           ; cur.ctex
        ld a,(w_cur+1)
        ld (pl_h),a             ; cur.ceil
        ld ix,w_pc
        call plane_span
        ld a,(w_ybot)           ; ytop = max(ytop, min(ybot, yb))
        ld hl,w_yb
        call min8
        ld hl,w_ytop
        call max8
        ld (w_ytop),a
        ; --- step 4: nxt = cell(mx, my) ; texture column u ; shade s
        ld a,(w_mx)
        ld b,a
        ld a,(w_my)
        ld c,a
        call cell_ptr
        ld de,w_nxt
        ld bc,4
        ldir
        ld a,(w_side)
        or a
        jr nz,wc_hit_side1
        ld hl,(w_ry)            ; side 0: hit = py + smul_shr(ry, d, 8)
        ld de,(w_d)
        call hit_lo             ; A = low byte of smul_shr(ry, d, 8)
        ld b,a
        ld a,(py)
        add a,b                 ; only (hit & 255) is needed
        jr wc_hit_done
wc_hit_side1:
        ld hl,(w_rx)            ; side 1: hit = px + smul_shr(rx, d, 8)
        ld de,(w_d)
        call hit_lo
        ld b,a
        ld a,(px)
        add a,b
wc_hit_done:
        srl a
        srl a
        srl a
        ld (w_u),a              ; u = (hit & 255) >> 3
        ld hl,(w_d)             ; s = shade_tab[d >> 7] (0 if d < 384 else 1 if d < 768 else 2 if d < 1536 else 3)
        ld a,l
        rlca
        and 1
        ld b,a
        ld a,h
        add a,a
        or b                    ; A = d >> 7 (0..31)
        ld hl,shade_tab
        db 0EDh,031h            ; add hl,a
        ld b,(hl)
        ld a,(w_side)
        or a
        jr z,wc_shade_store
        inc b                   ; side == 1: s = min(3, s + 1)
        ld a,b
        cp 4
        jr c,wc_shade_store
        ld b,3
wc_shade_store:
        ld a,b
        ld (w_s),a
        ; --- step 5: nxt.solid -> WALL(c, cur.ceil, cur.floor, nxt.wtex, d, u, s) ; ZBUF[c] = d ; STOP
        ld a,(w_nxt+2)
        bit 7,a
        jr z,wc_not_solid
        and 0Fh
        ld (w_wtex),a
        ld a,(w_cur+1)
        ld (w_htop),a
        ld a,(w_cur+0)
        ld (w_hbot),a
        call wall
        jp wc_zbuf_d
wc_not_solid:
        ; --- step 6: nxt.floor > cur.floor -> WALL(c, nxt.floor, cur.floor, nxt.wtex, d, u, s) ;
        ;             ybot = min(ybot, max(ytop, ROW(y(nxt.floor, d))))  (that row is the next step's floor yb: cache it)
        ld a,(w_cur+0)
        xor 80h
        ld b,a                  ; signed compare via xor 80h -> unsigned compare
        ld a,(w_nxt+0)
        xor 80h
        cp b
        jr c,wc_no_step
        jr z,wc_no_step
        ld a,(w_nxt+2)
        and 0Fh
        ld (w_wtex),a
        ld a,(w_nxt+0)
        ld (w_htop),a
        ld a,(w_cur+0)
        ld (w_hbot),a
        call wall
        ld a,(w_nxt+0)
        ld (w_fh),a
        ld de,(w_rd)
        call yproj_r
        call row_of
        ld (w_frow),a
        ld hl,w_ytop
        call max8
        ld hl,w_ybot
        call min8
        ld (w_ybot),a
wc_no_step:
        ; --- step 7: nxt.ceil < cur.ceil -> WALL(c, cur.ceil, nxt.ceil, nxt.ltex, d, u, s) ;
        ;             ytop = max(ytop, min(ybot, ROW(y(nxt.ceil, d))))  (that row is the next step's ceiling ya: cache it)
        ld a,(w_cur+1)
        xor 80h
        ld b,a
        ld a,(w_nxt+1)
        xor 80h
        cp b
        jr nc,wc_no_lintel
        ld a,(w_nxt+2)
        rrca
        rrca
        rrca
        rrca
        and 7
        ld (w_wtex),a           ; ltex = (byte2 >> 4) & 7
        ld a,(w_cur+1)
        ld (w_htop),a
        ld a,(w_nxt+1)
        ld (w_hbot),a
        call wall
        ld a,(w_nxt+1)
        ld (w_ch),a
        ld de,(w_rd)
        call yproj_r
        call row_of
        ld (w_crow),a
        ld hl,w_ybot
        call min8
        ld hl,w_ytop
        call max8
        ld (w_ytop),a
wc_no_lintel:
        ; --- step 8: ytop >= ybot -> ZBUF[c] = d ; STOP
        ld a,(w_ytop)
        ld hl,w_ybot
        cp (hl)
        jr nc,wc_zbuf_d
        ; --- step 9: cur = nxt ; dprev = d (R(dprev) = R(d)) ; continue (at most 48 steps)
        ld hl,w_nxt
        ld de,w_cur
        ld bc,4
        ldir
        ld hl,(w_d)
        ld (w_dprev),hl
        ld hl,(w_rd)
        ld (w_rdp),hl
        ld hl,w_steps
        dec (hl)
        jp nz,wc_loop
wc_exhaust:
        ; --- EXHAUST: if ytop < ybot: VOID(c, ytop, ybot) ; ZBUF[c] = 4095
        ld a,(w_ytop)
        ld hl,w_ybot
        cp (hl)
        jr nc,wc_no_void
        ld (vd_a),a
        ld a,(hl)
        ld (vd_b),a
        ld a,(w_c)
        ld (vd_c),a
        call void_fill
wc_no_void:
        ld hl,0FFFh
        jr wc_zbuf_hl
wc_zbuf_d:
        ld hl,(w_d)
wc_zbuf_hl:
    IF DEFINED WALK_COALESCE
        push hl                 ; end of the column: emit the pending plane spans
        ld ix,w_pf
        ld a,(ix+0)
        or a
        call nz,ps_flush_ix
        ld ix,w_pc
        ld a,(ix+0)
        or a
        call nz,ps_flush_ix
        pop hl
    ENDIF
        ex de,hl                ; ZBUF[c] = DE (word at ZBUF + 2*c)
        ld a,(w_c)
        add a,a
        ld l,a
        ld h,ZBUF / 256
        ld (hl),e
        inc hl
        ld (hl),d
        ret

; ---------------------------------------------------------------------------------------------------------------
; plane_span - section 4 steps 2/3: a = max(ya, ytop), b = min(yb, ybot) ; if a < b: PLANE_ADD(c, pl_h, pl_tex, a, b)
;              (pl_h and pl_tex already filled by the caller; IX -> the pending block of this surface, WALK_COALESCE builds)
; ---------------------------------------------------------------------------------------------------------------
plane_span:
        ld a,(w_ya)
        ld hl,w_ytop
        call max8
        ld (pl_a),a
        ld a,(w_yb)
        ld hl,w_ybot
        call min8
        ld (pl_b),a
        ld hl,pl_a
        cp (hl)                 ; b - a : carry if b < a, zero if equal
        ret c
        ret z
    IF DEFINED WALK_COALESCE
        ld a,(ix+0)
        or a
        jr z,ps_new             ; nothing pending: start a span
        ld a,(pl_h)
        cp (ix+1)
        jr nz,ps_flush_new
        ld a,(pl_tex)
        cp (ix+2)
        jr nz,ps_flush_new
        ld a,(pl_b)             ; same surface: the new span [a, b) touches the pending [pa, pb) when b == pa ...
        cp (ix+3)
        jr nz,ps_try_below
        ld a,(pl_a)
        ld (ix+3),a             ; ... -> pending = [a, pb)
        ret
ps_try_below:
        ld a,(pl_a)             ; ... or when a == pb -> pending = [pa, b)
        cp (ix+4)
        jr nz,ps_flush_new
        ld a,(pl_b)
        ld (ix+4),a
        ret
ps_flush_new:
        ld hl,(pl_h)            ; L = h, H = tex (pl_h, pl_tex are contiguous) of the NEW span: ps_flush_ix overwrites pl_*
        ld de,(pl_a)            ; E = a, D = b
        push hl
        push de
        push ix
        call ps_flush_ix        ; emit the pending span (plane_add destroys every register)
        pop ix
        pop de
        pop hl
        ld (ix+0),1             ; pending = the new span
        ld (ix+1),l
        ld (ix+2),h
        ld (ix+3),e
        ld (ix+4),d
        ret
ps_new:
        ld (ix+0),1
        ld a,(pl_h)
        ld (ix+1),a
        ld a,(pl_tex)
        ld (ix+2),a
        ld a,(pl_a)
        ld (ix+3),a
        ld a,(pl_b)
        ld (ix+4),a
        ret
ps_flush_ix:                    ; IX -> pending block (on = 1): PLANE_ADD(c, h, tex, a, b) ; on = 0
        ld (ix+0),0
        ld a,(ix+1)
        ld (pl_h),a
        ld a,(ix+2)
        ld (pl_tex),a
        ld a,(ix+3)
        ld (pl_a),a
        ld a,(ix+4)
        ld (pl_b),a
        ld a,(w_c)
        ld (pl_c),a
        jp plane_add
    ELSE
        ld a,(w_c)
        ld (pl_c),a
        jp plane_add
    ENDIF

; ---------------------------------------------------------------------------------------------------------------
; wall - spec section 4 WALL(c, h_top, h_bot, tex, d, u, s): split into 1-cell texture tiles aligned to world height 0.
;        in: (w_htop) = h_top, (w_hbot) = h_bot, (w_wtex) = tex, (w_d) = d (R(d) in w_rd), (w_u) = u, (w_s) = s,
;        ytop/ybot = current
; ---------------------------------------------------------------------------------------------------------------
wall:
        ld a,(w_htop)
        ld (w_ttop),a           ; t_top = h_top
wall_loop:
        ld a,(w_hbot)           ; while t_top > h_bot (signed)
        xor 80h
        ld b,a
        ld a,(w_ttop)
        xor 80h
        cp b
        ret c
        ret z
        ld a,(w_ttop)           ; tile_base = ((t_top - 1) // 32) * 32  (floor division = and 0E0h on the int8)
        dec a
        and 0E0h
        ld (w_tbase),a
        xor 80h                 ; t_bot = max(h_bot, tile_base) (signed)
        cp b
        jr nc,wall_tbot_ok
        ld a,b
wall_tbot_ok:
        xor 80h
        ld (w_tbot),a
        ld a,(w_ttop)           ; y_a = y(t_top, d) ; ra = max(ROW(y_a), ytop)
        ld de,(w_rd)
        call yproj_r
        ld (w_yaq),hl
        call row_of
        ld hl,w_ytop
        call max8
        ld (w_ra),a
        ld a,(w_tbot)           ; y_b = y(t_bot, d) ; rb = min(ROW(y_b), ybot)
        ld de,(w_rd)
        call yproj_r
        call row_of
        ld hl,w_ybot
        call min8
        ld (w_rb),a
        ld hl,w_ra              ; if ra < rb
        cp (hl)
        jp c,wall_next
        jp z,wall_next
        ld a,(w_tbase)          ; v_top = tile_base + 32 - t_top (0..31)
        add a,32
        ld hl,w_ttop
        sub (hl)
        ld (w_vtop),a
        ld hl,(w_d)             ; dv = d >> 1 (Q8)
        srl h
        rr l
        ld (w_dv),hl
        ld (pc_dv),hl
        ; v_first = v_top*256 + smul_shr((ra*256 + 128) - y_a, dv, 8)
        ; (ra*256 + 128) - y_a >= 0 always (ra >= ROW(y_a) and ROW(y_a)*256 + 128 >= y_a), so the product is unsigned;
        ; the difference is computed with 17-bit care (y_a may be -32768 while ra*256+128 is up to 24704: sum <= 57472).
        ld a,(w_ra)
        ld h,a
        ld l,128                ; HL = ra*256 + 128
        ld de,(w_yaq)           ; DE = y_a
        bit 7,d
        jr z,wall_diff_sub
        ex de,hl
        call neg_hl             ; HL = |y_a|
        ex de,hl
        add hl,de               ; HL = ra*256 + 128 + |y_a|  (<= 57472, no carry)
        jr wall_diff_ok
wall_diff_sub:
        or a
        sbc hl,de               ; HL = ra*256 + 128 - y_a (>= 0 by construction)
        jr nc,wall_diff_ok
        ld hl,0                 ; unreachable guard (would mean a negative difference)
wall_diff_ok:
        ld de,(w_dv)
        call umul32             ; DEHL = diff * dv (< 2^27)
        ; q = (diff*dv) >> 8 = D:E:H (24 bits) ; v_first_raw = v_top*256 + q. If v_first_raw > 8191 the guard below
        ; triggers for sure (v_last >= v_first_raw), so only the 16-bit case needs the exact value.
        ld a,d
        or a
        jr nz,wall_guard
        ld l,h
        ld h,e                  ; HL = q
        ld a,(w_vtop)
        ld d,a
        ld e,0
        add hl,de               ; HL = v_first_raw
        jr c,wall_guard
        ld (w_vraw),hl
        ld a,h
        cp 20h
        jr nc,wall_guard        ; v_first_raw > 8191
        call wall_cnt_dv        ; E:HL = (count - 1) * dv (24 bits)
        ld a,e
        or a
        jr nz,wall_guard        ; v_last >= 65536 > 8191
        ld de,(w_vraw)
        add hl,de               ; v_last = v_first + (count - 1)*dv
        jr c,wall_guard
        ld a,h
        cp 20h
        jr nc,wall_guard        ; v_last > 8191
        ld hl,(w_vraw)          ; guard not triggered: v_first unchanged (>= 0)
        jr wall_v_done
wall_guard:
        ; v_last > 8191: v_first -= (v_last - 8191)  ==  v_first = 8191 - (count - 1)*dv ; if v_first < 0: v_first = 0
        call wall_cnt_dv
        ld a,e
        or a
        jr nz,wall_v_zero
        ex de,hl
        ld hl,8191
        or a
        sbc hl,de
        jr nc,wall_v_done
wall_v_zero:
        ld hl,0
wall_v_done:
        ld (pc_v),hl
        ld a,(w_c)              ; DRAW_PIECE(c, ra, count, tex, s, u, v_first, dv)
        ld (pc_c),a
        ld a,(w_ra)
        ld (pc_ra),a
        ld a,(w_rb)
        ld hl,w_ra
        sub (hl)
        ld (pc_count),a         ; count = rb - ra
        ld a,(w_wtex)
        ld (pc_tex),a
        ld a,(w_s)
        ld (pc_s),a
        ld a,(w_u)
        ld (pc_u),a
        call draw_piece
wall_next:
        ld a,(w_tbot)           ; t_top = t_bot
        ld (w_ttop),a
        jp wall_loop

wall_cnt_dv:                    ; E:HL = (rb - ra - 1) * dv  (24-bit product: count - 1 <= 95, dv <= 2047)
        ld a,(w_rb)
        ld hl,w_ra
        sub (hl)
        dec a                   ; A = count - 1
        ld de,(w_dv)
        jp mul8x16

walk_end:
