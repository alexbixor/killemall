; draw_b.asm - Kill'em all Spectrum Next edition B: the pixel drawers (lane N1D), derived from draw.asm (lane D2).
; Include nx_vars.inc and draw_b_vars.inc (tier flags PLANES_LO / PLANES_FLAT) first; no org here.
; Spec: docs/next_engine_spec_v0.1.md sections 4 (DRAW_PIECE pixel rule), 5 (planes, VOID), 6 (asset layout),
; 8 (memory map), 10 (call interface). Include AFTER nx_vars.inc; no org here.
; Routines: draw_piece, plane_add, planes_reset, planes_flush, void_fill. Parameter blocks: pc_*, pl_*, vd_* (nx_vars.inc).
; All routines may destroy every register (AF, BC, DE, HL, IX, IY and the alternate set); SP is preserved.
; Scratch: DRAW_VARS (5900h..59FFh, lane D2 owns it) only.
; Lane D1's walker scratch (5840h..58FFh) is never touched.
; Slots used: slot 0 (RD_TAB), slot 6 (wall textures, nextreg 56h switched per piece), slot 7 (floors). Slot 1 is NOT used.
; Techniques (from tools/m30_bench_gen.py, proven at 28 MHz): walls = 96 unrolled row slots with IX pairs and a patched RET;
; planes = Doom visplanes turned into row spans (R_MakeSpans), span pixels = (L and F0h) or (H' and 0Fh) texel index.

dr_nplanes  equ DRAW_VARS+0     ; byte  planes allocated (0..NPLANES)
dr_y        equ DRAW_VARS+1     ; byte  current row
dr_h        equ DRAW_VARS+2     ; byte  int8 height of the current plane
dr_tex      equ DRAW_VARS+3     ; byte  floor texture of the current plane
dr_d        equ DRAW_VARS+4     ; word  row depth Q8
dr_s        equ DRAW_VARS+6     ; byte  row shade
dr_far      equ DRAW_VARS+7     ; byte  1 = row depth > 4095 (paint palette index 0)
dr_dx       equ DRAW_VARS+8     ; word  DX signed Q8
dr_dy       equ DRAW_VARS+10    ; word  DY signed Q12
dr_xb       equ DRAW_VARS+12    ; word  XB
dr_yb       equ DRAW_VARS+14    ; word  YB
dr_page     equ DRAW_VARS+16    ; byte  floor page high byte (0E0h + tex*4 + s)
dr_p0       equ DRAW_VARS+18    ; word  umul scratch
dr_p3       equ DRAW_VARS+20    ; word  umul scratch
dr_shift    equ DRAW_VARS+22    ; byte  smul_shr shift count
dr_plane    equ DRAW_VARS+24    ; word  address of the current plane entry
dr_pcount   equ DRAW_VARS+26    ; byte  planes left to flush
dr_c        equ DRAW_VARS+31    ; byte  current column of the span scan (0..128, 128 = sentinel)
dr_c0       equ DRAW_VARS+32    ; byte  span first column
dr_n        equ DRAW_VARS+33    ; byte  span length (1..128)
dp_orig     equ DRAW_VARS+36    ; byte  draw_piece: byte under the patched RET
dp_patch    equ DRAW_VARS+37    ; word  draw_piece: address of the patched RET
dp_page     equ DRAW_VARS+39    ; byte  draw_piece: texture page
dr_span     equ DRAW_VARS+64    ; 96 bytes: spanstart[y] (5940h..599Fh)
; plane entry (258 bytes): +0 h (int8), +1 tex, +2 top[128] (255 = column unused), +130 bottom[128] (exclusive, 0 when unused)
PL_SIZE     equ 258
PL_TOP      equ 2
PL_BOT      equ 130

; ---------------------------------------------------------------- helpers
; dr_scr_addr: A = row 0..95 -> HL = address of pixel (0, row). Uses A.
dr_scr_addr:
        ld l,0
        cp 48
        jr c,dsa_top
        sub 48
        srl a
        rr l
        add a,60h
        ld h,a
        ret
dsa_top:
        srl a
        rr l
        add a,40h
        ld h,a
        ret

; dr_umul: HL = a, DE = b (unsigned 16 bit) -> DEHL = a*b (32 bit). Uses A, BC, dr_p0, dr_p3.
dr_umul:
        ld b,d                  ; bh
        ld c,e                  ; bl
        ld a,h                  ; ah
        ld d,l
        ld e,c
        db 0EDh,030h            ; mul d,e : DE = al*bl = p0
        ld (dr_p0),de
        ld d,a
        ld e,b
        db 0EDh,030h            ; DE = ah*bh = p3
        ld (dr_p3),de
        ld d,a
        ld e,c
        db 0EDh,030h            ; DE = ah*bl = p1
        push de
        ld d,l
        ld e,b
        db 0EDh,030h            ; DE = al*bh = p2
        pop hl
        add hl,de               ; HL = p1 + p2 (low 16), carry = bit 16
        ld b,0
        rl b                    ; B = carry
        ld de,(dr_p0)
        ld a,d                  ; p0 high
        add a,l
        ld l,a                  ; R1
        ld a,(dr_p3)
        adc a,h
        ld h,a                  ; R2
        ld a,(dr_p3+1)
        adc a,b
        ld d,a                  ; R3
        ld a,e                  ; R0
        ld e,h                  ; E = R2
        ld h,l                  ; H = R1
        ld l,a                  ; L = R0
        ret

; dr_neg_hl: HL = -HL
dr_neg_hl:
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
        ret

; dr_smul_shr: HL = a (signed 16), DE = b (signed 16), A = shift (0..15) -> HL = smul_shr(a, b, shift) (spec 0), low 16 bits.
; |a|*|b| must be < 2^24 (true for every product of spec 5: d <= 4095 times |plx|,|ply|,|dirx|,|diry| <= 256; DX, DY times 127).
dr_smul_shr:
        ld (dr_shift),a
        ld c,0
        bit 7,h
        jr z,dss1
        call dr_neg_hl
        inc c
dss1:   bit 7,d
        jr z,dss2
        ex de,hl
        call dr_neg_hl
        ex de,hl
        inc c
dss2:   push bc
        call dr_umul            ; DEHL = |a|*|b| (D = 0)
        ld a,(dr_shift)
        cp 8
        jr c,dss3
        sub 8
        ld l,h
        ld h,e
        ld e,0
dss3:   or a
        jr z,dss4
        ld b,a                  ; B = s (1..7)
        ld c,e                  ; C = bits 16..23
        ex de,hl
        db 0EDh,02Ah            ; bsrl de,b : DE = DE >> s
        ex de,hl                ; HL = low 16 >> s
        ld a,16
        sub b
        ld b,a
        ld d,0
        ld e,c
        db 0EDh,028h            ; bsla de,b : DE = top byte << (16 - s)
        ld a,h
        or d
        ld h,a
        ld a,l
        or e
        ld l,a
dss4:   pop bc
        dec c
        ret nz                  ; 0 or 2 negative operands: positive result
        jp dr_neg_hl

; dr_mul16x8: HL = x (16 bit), C = k (8 bit) -> HL = (x*k) and 0FFFFh. Uses A, DE.
dr_mul16x8:
        ld d,l
        ld e,c
        db 0EDh,030h            ; DE = x.lo * k
        ld a,d
        ld d,h
        ld l,e
        ld e,c
        db 0EDh,030h            ; DE = x.hi * k
        add a,e
        ld h,a
        ret

; dr_row_params: dr_h, dr_tex, dr_y -> dr_far (1: too far, nothing else valid) or dr_d, dr_s, dr_page, dr_dx, dr_dy, dr_xb, dr_yb.
; Spec 5: dy = 2*(y-48)+1, dh = eye - h, d = (|dh| * RD[|dy|]) >> 6 (24-bit product), far if d > 4095.
dr_row_params:
        IF DEFINED MOUSE_B
        ld a,(horizon_row)      ; lane N5: dy = 2*(y - horizon_row) + 1 = 2y - (2*horizon_row - 1) (95 for the default 48)
        add a,a
        dec a
        ld c,a
        ld a,(dr_y)
        add a,a
        sub c
        ELSE
        ld a,(dr_y)
        add a,a
        sub 95                  ; A = 2y - 95 = dy
        ENDIF
        jr nc,drp_dy
        neg
drp_dy: ld l,a                  ; |dy| 1..95
        ld h,0
        add hl,hl
        ld de,RD_TAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = RD[|dy|]
        ld a,(eye)
        ld hl,dr_h
        sub (hl)                ; A = eye - h (int8)
        jp p,drp_dh
        neg
drp_dh: ld c,a                  ; C = |dh|
        ld h,d                  ; H = RD high
        ld d,a
        db 0EDh,030h            ; DE = |dh| * RD.lo
        ld b,e                  ; B = P0
        ld a,d
        ld d,c
        ld e,h
        db 0EDh,030h            ; DE = |dh| * RD.hi
        add a,e
        ld l,a                  ; P1
        ld a,d
        adc a,0
        ld h,a                  ; P2 ; HL = P >> 8
        cp 4
        jr c,drp_near
        ld a,1
        ld (dr_far),a
        ret
drp_near:
        xor a
        ld (dr_far),a
        add hl,hl
        add hl,hl
        ld a,b
        rlca
        rlca
        and 3
        or l
        ld l,a                  ; HL = d = P >> 6 (0..4095)
        ld (dr_d),hl
        ; shade: 0 if d < 384, 1 if d < 768, 2 if d < 1536, else 3
        ld c,0
        ld de,384
        or a
        sbc hl,de
        jr c,drp_sh
        inc c
        sbc hl,de
        jr c,drp_sh
        inc c
        ld de,768
        sbc hl,de
        jr c,drp_sh
        inc c
drp_sh: ld a,c
        ld (dr_s),a
        ld a,(dr_tex)
        add a,a
        add a,a
        add a,c
        add a,0E0h
        ld (dr_page),a
        if PLANES_FLAT
        ret                     ; flat tier: the colour needs only dr_s (and dr_h vs eye)
        endif
        ; DX = smul_shr(d, plx, 14)
        ld hl,(dr_d)
        ld de,(plx)
        ld a,14
        call dr_smul_shr
        ld (dr_dx),hl
        ; DY = smul_shr(d, ply, 10)
        ld hl,(dr_d)
        ld de,(ply)
        ld a,10
        call dr_smul_shr
        ld (dr_dy),hl
        ; XB = px + smul_shr(d, dirx, 8) - smul_shr(DX, 127, 1)
        ld hl,(dr_d)
        ld de,(dirx)
        ld a,8
        call dr_smul_shr
        ld de,(px)
        add hl,de
        push hl
        ld hl,(dr_dx)
        ld de,127
        ld a,1
        call dr_smul_shr
        pop de
        ex de,hl
        or a
        sbc hl,de
        ld (dr_xb),hl
        ; YB = (py << 4) + smul_shr(d, diry, 4) - smul_shr(DY, 127, 1)
        ld hl,(dr_d)
        ld de,(diry)
        ld a,4
        call dr_smul_shr
        ld de,(py)
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        push hl
        ld hl,(dr_dy)
        ld de,127
        ld a,1
        call dr_smul_shr
        pop de
        ex de,hl
        or a
        sbc hl,de
        ld (dr_yb),hl
        ret

; ---------------------------------------------------------------- draw_piece (spec 4, 6, 8)
; pixel i (0..pc_count-1) at (pc_c, pc_ra+i) = WALLTEX[tex][s][u][(pc_v + i*pc_dv) >> 8]
; slot 6 = 8K bank 16 + (tex >> 1); page = 0C0h + (tex and 1)*16 + s*4 + (u >> 3); byte in page = (u and 7)*32 + v.
; Unrolled drawer (benchmark technique): slot wr<k> draws row k: add hl,bc ; ld e,h ; ld a,(de) ; ld (ix-128 / ix+0),a ;
; rows 2k, 2k+1 share IX (= address of row 2k+1 + c), inc ixh after the odd row; wr48 adds 800h to IX (5800h -> 6000h gap);
; entered at the first row's slot, exits through a RET patched over the slot of the row after the last.
draw_piece:
        ld a,(pc_count)
        or a
        ret z                   ; nothing to draw (spec guarantees >= 1; guard keeps the RET patch consistent)
        ld a,(pc_tex)
        srl a
        add a,WALL_BANK0
        db 0EDh,092h,NR_MMU6    ; nextreg 56h,a
        ld a,(pc_tex)
        and 1
        rrca
        rrca
        rrca
        rrca                    ; (tex and 1)*16
        add a,0C0h
        ld d,a
        ld a,(pc_s)
        add a,a
        add a,a
        add a,d
        ld d,a
        ld a,(pc_u)
        srl a
        srl a
        srl a
        add a,d
        ld (dp_page),a          ; page
        ld a,(pc_u)
        and 7
        add a,a
        add a,a
        add a,a
        add a,a
        add a,a                 ; (u and 7)*32
        ld hl,(pc_v)
        add a,h
        ld h,a                  ; HL = v Q8 + (u and 7)*32*256 -> H = byte in page
        ld bc,(pc_dv)
        or a
        sbc hl,bc               ; the slot adds dv before the first fetch
        push hl
        ld a,(pc_ra)            ; (C is reloaded from pc_dv just before the call)
        ld c,a
        ld a,(pc_count)
        add a,c                 ; A = end row (1..96)
        add a,a
        ld l,a
        ld h,0
        ld de,wr_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = slot of the end row
        ld (dp_patch),de
        ld a,(de)
        ld (dp_orig),a
        ld a,0C9h
        ld (de),a               ; RET
        ld a,c
        cp 48
        ld de,wr48b
        jr z,dp_entry
        add a,a
        ld l,a
        ld h,0
        ld de,wr_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
dp_entry:
        ld (dp_call+1),de
        ld a,c
        or 1
        call dr_scr_addr        ; HL = address of row (ra or 1)
        ld a,(pc_c)
        or l
        ld l,a
        push hl
        pop ix                  ; IX = row (ra or 1) + c
        pop hl                  ; HL = v - dv
        ld bc,(pc_dv)           ; BC = dv (C was used as ra above)
        ld a,(dp_page)
        ld d,a
dp_call:
        call 0
        ld hl,(dp_patch)
        ld a,(dp_orig)
        ld (hl),a
        ret

; ---------------------------------------------------------------- void_fill (spec 5)
void_fill:
        ld a,(vd_b)
        ld c,a
        ld a,(vd_a)
        ld b,a
        ld a,c
        sub b
        ret z
        ret c
        ld c,a                  ; rows
        ld a,b
        call dr_scr_addr
        ld a,(vd_c)
        or l
        ld l,a
        ld b,c
        ld de,128
        xor a
vf_loop:
        ld (hl),a
        add hl,de
        ld a,h
        cp 58h
        jr nz,vf_nc
        ld h,60h
vf_nc:  xor a
        djnz vf_loop
        ret

; ---------------------------------------------------------------- planes (spec 5)
planes_reset:
        xor a
        ld (dr_nplanes),a
        ret

; plane_add: rows pl_a..pl_b-1 of column pl_c show the plane (pl_h, pl_tex).
; Finds a plane with the same (h, tex) whose column c is unused, or whose span in column c is adjacent to [a, b)
; (the colour depends only on h, tex, c, row, so adjacent spans merge); else allocates a plane; if none is free,
; the span is painted at once (pa_direct).
plane_add:
        ld a,(dr_nplanes)
        or a
        jr z,pa_alloc
        ld b,a
        ld hl,PLANES
        ld a,(pl_c)
        ld e,a                  ; E = c
        ld a,(pl_tex)
        ld d,a                  ; D = tex
        ld a,(pl_h)
        ld c,a                  ; C = h
pa_find:
        ld a,(hl)
        cp c
        jr nz,pa_next
        inc hl
        ld a,(hl)
        dec hl
        cp d
        jr nz,pa_next
        push hl
        ld a,e
        db 0EDh,031h            ; add hl,a
        inc hl
        inc hl                  ; HL = &top[c]
        ld a,(hl)
        inc a                   ; 255 -> 0 : column free
        jr z,pa_free
        ld a,(pl_b)
        cp (hl)                 ; top[c] == b : the new span sits just above
        jr nz,pa_m2
        ld a,(pl_a)
        ld (hl),a
        pop hl
        ret
pa_m2:  push de
        ld de,128
        add hl,de               ; HL = &bottom[c]
        pop de
        ld a,(pl_a)
        cp (hl)                 ; bottom[c] == a : the new span sits just below
        jr nz,pa_m3
        ld a,(pl_b)
        ld (hl),a
        pop hl
        ret
pa_m3:  pop hl
pa_next:
        db 0EDh,034h,PL_SIZE and 255,PL_SIZE shr 8   ; add hl,258
        djnz pa_find
pa_alloc:
        ld a,(dr_nplanes)
        cp NPLANES
        jp nc,pa_direct         ; no free plane: draw the span now
        inc a
        ld (dr_nplanes),a
        dec a
        ld h,a
        ld l,0                  ; 256*a
        add a,a
        ld l,a                  ; HL = 258*a (a <= 14)
        ld de,PLANES
        add hl,de
        push hl
        ld a,(pl_h)
        ld (hl),a
        inc hl
        ld a,(pl_tex)
        ld (hl),a
        inc hl
        ld (hl),255             ; top[0..127] = 255 (unused)
        ld d,h
        ld e,l
        inc de
        ld bc,127
        ldir
        ex de,hl                ; HL = &bottom[0]
        ld (hl),0               ; bottom[0..127] = 0
        ld d,h
        ld e,l
        inc de
        ld bc,127
        ldir
        pop hl
        jr pa_use
pa_free:
        pop hl
pa_use:                         ; HL = plane entry: top[c] = pl_a, bottom[c] = pl_b
        ld a,(pl_c)
        db 0EDh,031h            ; add hl,a
        inc hl
        inc hl
        ld a,(pl_a)
        ld (hl),a
        ld de,128
        add hl,de
        ld a,(pl_b)
        ld (hl),a
        ret

; pa_direct: planes table full -> paint column pl_c rows pl_a..pl_b-1 immediately with the per-pixel maths.
pa_direct:
        ld a,(pl_h)
        ld (dr_h),a
        ld a,(pl_tex)
        ld (dr_tex),a
        ld a,(pl_a)
        ld (dr_y),a
pd_loop:
        ld a,(dr_y)
        ld hl,pl_b
        cp (hl)
        ret nc                  ; y >= b : done
        call dr_row_params
        ld a,(dr_y)
        call dr_scr_addr
        ld a,(pl_c)
        or l
        ld l,a
        ld a,(dr_far)
        or a
        jr z,pd_tex
        ld (hl),0
        jr pd_next
pd_tex:
        push hl                 ; pixel address
        ld a,(pl_c)
        ld c,a
        ld hl,(dr_dx)
        call dr_mul16x8         ; HL = c*DX
        ld de,(dr_xb)
        add hl,de               ; wx
        push hl
        ld a,(pl_c)
        ld c,a
        ld hl,(dr_dy)
        call dr_mul16x8
        ld de,(dr_yb)
        add hl,de               ; wy
        ex de,hl                ; DE = wy
        pop hl                  ; HL = wx
        ld a,l
        xor d
        and 0F0h
        xor d                   ; (L and F0h) or (D and 0Fh)
        ld c,a
        ld a,(dr_page)
        ld b,a
        ld a,(bc)
        pop hl
        ld (hl),a
pd_next:
        ld hl,dr_y
        inc (hl)
        jr pd_loop

; ---------------------------------------------------------------- planes_flush: every plane -> row spans -> pixels
planes_flush:
        ld a,(dr_nplanes)
        or a
        ret z
        ld (dr_pcount),a
        ld hl,PLANES
        ld (dr_plane),hl
pf_plane:
        ld hl,(dr_plane)
        ld a,(hl)
        ld (dr_h),a
        inc hl
        ld a,(hl)
        ld (dr_tex),a
        ld de,PL_BOT-1
        add hl,de
        push hl
        pop ix                  ; IX = &bottom[c] ; top[c] = (ix-128)
        ld d,255                ; D = t1 (top of the previous column; 255 = none)
        ld e,0                  ; E = B1 (exclusive bottom of the previous column)
        ld c,0                  ; C = column
pf_col:                         ; Doom R_MakeSpans with exclusive bottoms; H = t2, L = B2 of column c (sentinel column 128: 255, 0)
        ld a,c
        cp 128
        jr z,pf_sentinel
        ld h,(ix-128)
        ld l,(ix+0)
        jr pf_l1
pf_sentinel:
        ld h,255
        ld l,0
pf_l1:                          ; while t1 < t2 and t1 < B1: close span row t1 ; t1++
        ld a,d
        cp h
        jr nc,pf_l2
        cp e
        jr nc,pf_l2
        call dr_close_r
        inc d
        jr pf_l1
pf_l2:                          ; while B1 > B2 and B1 > t1: B1-- ; close span row B1
        ld a,l
        cp e                    ; carry = B2 < B1
        jr nc,pf_l3
        ld a,d
        cp e                    ; carry = t1 < B1
        jr nc,pf_l3
        dec e
        ld a,e
        call dr_close_r
        jr pf_l2
pf_l3:                          ; while t2 < t1 and t2 < B2: open span row t2 at c ; t2++
        ld a,h
        cp d
        jr nc,pf_l4
        cp l
        jr nc,pf_l4
        call dr_open_r
        inc h
        jr pf_l3
pf_l4:                          ; while B2 > B1 and B2 > t2: B2-- ; open span row B2 at c
        ld a,e
        cp l                    ; carry = B1 < B2
        jr nc,pf_l5
        ld a,h
        cp l                    ; carry = t2 < B2
        jr nc,pf_l5
        dec l
        ld a,l
        call dr_open_r
        jr pf_l4
pf_l5:
        ld a,c
        cp 128
        jr z,pf_plane_done
        ld d,(ix-128)           ; t1 = top[c], B1 = bottom[c] (fresh values, the loops above modified H, L)
        ld e,(ix+0)
        inc ix
        inc c
        jr pf_col
pf_plane_done:
        ld hl,(dr_plane)
        ld de,PL_SIZE
        add hl,de
        ld (dr_plane),hl
        ld hl,dr_pcount
        dec (hl)
        jp nz,pf_plane
        ret

; dr_open_r: A = row y, C = column -> spanstart[y] = c. Preserves all registers but A.
dr_open_r:
        push hl
        ld hl,dr_span
        db 0EDh,031h            ; add hl,a
        ld (hl),c
        pop hl
        ret

; dr_close_r: A = row y, C = end column (exclusive) -> draw the span of row y from spanstart[y] to c - 1. Preserves BC, DE, HL, IX.
dr_close_r:
        push bc
        push de
        push hl
        push ix
        ld b,a
        ld a,c
        ld (dr_c),a
        ld a,b
        call dr_close
        pop ix
        pop hl
        pop de
        pop bc
        ret

; dr_close: A = row y -> draw the span of row y from spanstart[y] to dr_c - 1
dr_close:
        ld (dr_y),a
        ld hl,dr_span
        db 0EDh,031h            ; add hl,a
        ld a,(hl)
        ld (dr_c0),a
        ld hl,dr_c0
        ld a,(dr_c)
        sub (hl)
        ld (dr_n),a             ; n = c - c0 (>= 1)
        ; fall through
; ---------------------------------------------------------------- N1D span writer (plane tiers, draw_b_vars.inc)
; dr_span_draw: paint row dr_y, columns dr_c0 .. dr_c0 + dr_n - 1 of the plane (dr_h, dr_tex).
; Tiers (spec v0.2 section 4): hi = draw.asm's writer (every pixel its own texel, (L and F0h) or (H' and 0Fh) index);
; lo = pixels 2k and 2k+1 share the texel of column 2k (one lookup, two writes, step 2DX/2DY);
; flat = one colour per row: material*16 + 12 - 3*s (floor rows FLAT_FLOOR_MAT, ceiling rows FLAT_CEIL_MAT).
; Rows with d > 4095 are palette index 0 in every tier.
; Decision (build/night/N1D_QUESTIONS.md): the writes go through (BC) in the main register set with the texture page in B';
; a PUSH-based writer (m30 T2) costs the same T-states per pixel here (its ex af,af' + ld b,ixh page restore eat the saving).
dr_dx2      equ DRAW_VARS+40    ; word  2*DX (lo tier)
dr_dy2      equ DRAW_VARS+42    ; word  2*DY (lo tier)
dr_cend     equ DRAW_VARS+44    ; byte  c0 + n
dr_ce0      equ DRAW_VARS+45    ; byte  first even column of a full pair (lo tier)
dr_ce1      equ DRAW_VARS+46    ; byte  even column after the last full pair (lo tier)

dr_span_draw:
        call dr_row_params      ; one computation per span (spans ~= rows per plane)
        ld a,(dr_far)
        or a
        jp nz,dr_span_far
        if PLANES_FLAT
        ; flat: colour = material*16 + 12 - 3*s ; floor when eye - h > 0 (spec 5: floors dh > 0, ceilings dh < 0)
        ld a,(dr_h)
        ld c,a
        ld a,(eye)
        sub c                   ; A = eye - h (int8, |dh| < 128)
        ld a,FLAT_FLOOR_MAT*16+12
        jp p,dsf_mat
        ld a,FLAT_CEIL_MAT*16+12
dsf_mat:
        ld c,a
        ld a,(dr_s)
        ld b,a
        add a,a
        add a,b                 ; 3*s
        ld b,a
        ld a,c
        sub b                   ; colour
        jr dr_span_fill
        else
        if PLANES_LO
        ; lo tier
        ld a,(dr_c0)
        ld c,a
        ld a,(dr_n)
        add a,c                 ; c_end = c0 + n (1..128)
        ld (dr_cend),a
        and 0FEh
        ld (dr_ce1),a           ; ce1 = c_end and 0FEh
        ld a,c
        inc a
        and 0FEh
        ld (dr_ce0),a           ; ce0 = (c0 + 1) and 0FEh  (ce0 <= ce1)
        ld a,(dr_y)
        call dr_scr_addr
        ld a,(dr_c0)
        or l
        ld l,a
        push hl                 ; [screen address of (c0, y)]
        ; wy0 = YB + ce0*DY - 2DY -> HL', 2DY -> DE', page -> B'
        ld hl,(dr_dy)
        add hl,hl
        ld (dr_dy2),hl
        ld hl,(dr_dy)
        ld a,(dr_ce0)
        ld c,a
        call dr_mul16x8
        ld de,(dr_yb)
        add hl,de
        ld de,(dr_dy2)
        or a
        sbc hl,de
        ld a,(dr_page)
        ld b,a
        exx
        ; wx0 = XB + ce0*DX - 2DX -> HL, 2DX -> DE, screen -> BC
        ld hl,(dr_dx)
        add hl,hl
        ld (dr_dx2),hl
        ld hl,(dr_dx)
        ld a,(dr_ce0)
        ld c,a
        call dr_mul16x8
        ld de,(dr_xb)
        add hl,de
        ld de,(dr_dx2)
        or a
        sbc hl,de
        pop bc                  ; BC = screen address of (c0, y) ; bit 0 of C = bit 0 of c0 (rows are 128-aligned)
        bit 0,c
        jr z,dsl_nol
        ; left single: c0 odd -> pixel c0 = texel of column c0 - 1 = ce0 - 2 = the start coordinates (no step)
        ld a,l
        exx
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
dsl_nol:
        ld a,(dr_ce1)
        push hl
        ld hl,dr_ce0
        sub (hl)
        pop hl
        srl a                   ; A = pairs = (ce1 - ce0) >> 1 (0..64)
        jr z,dsl_right
        push hl
        ld l,a
        add a,3
        rra
        rra
        and 1Fh                 ; passes = (pairs + 3) >> 2
        ld ixl,a
        ld a,l
        and 3
        add a,a
        ld hl,pl_tab
        db 0EDh,031h            ; add hl,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (dsl_jp+1),hl        ; entry slot (4 - pairs mod 4) mod 4
        pop hl
        call dsl_jp
dsl_right:
        ld a,(dr_cend)
        bit 0,a
        ret z
        ; right single: c_end odd -> pixel c_end - 1 (= ce1, even) = texel one step after the last pair
        add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        ret
dsl_jp: jp 0
; lo pixel block: HL = wx, DE = 2DX, BC = screen pointer ; HL' = wy, DE' = 2DY, B' = page ; IXL = passes of 4 pairs.
pl_block:
pl_s0:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
        ld (bc),a
        inc c
pl_s1:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
        ld (bc),a
        inc c
pl_s2:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
        ld (bc),a
        inc c
pl_s3:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
        ld (bc),a
        inc c
        db 0DDh,02Dh            ; dec ixl
        jp nz,pl_block
        ret
pl_tab: dw pl_s0,pl_s3,pl_s2,pl_s1
        else
        ; hi tier (draw.asm's writer, unchanged)
        ld a,(dr_y)
        call dr_scr_addr
        ld a,(dr_c0)
        or l
        ld l,a
        push hl                 ; [screen address]
        ld a,(dr_n)
        add a,7
        rra
        rra
        rra
        and 1Fh                 ; passes = (n + 7) >> 3
        ld ixl,a
        ld a,(dr_n)
        and 7
        add a,a
        ld hl,ps_tab
        db 0EDh,031h            ; add hl,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (ps_jp+1),de         ; entry slot (8 - n mod 8)
        ; wy0 = YB + (c0 - 1)*DY -> HL', DY -> DE', page -> B'
        ld hl,(dr_dy)
        ld a,(dr_c0)
        ld c,a
        call dr_mul16x8
        ld de,(dr_yb)
        add hl,de
        ld de,(dr_dy)
        or a
        sbc hl,de
        ld a,(dr_page)
        ld b,a
        exx
        ; wx0 = XB + (c0 - 1)*DX -> HL, DX -> DE, screen -> BC
        ld hl,(dr_dx)
        ld a,(dr_c0)
        ld c,a
        call dr_mul16x8
        ld de,(dr_xb)
        add hl,de
        ld de,(dr_dx)
        or a
        sbc hl,de
        pop bc
ps_jp:  jp 0
; span pixel block: HL = wx, DE = DX, BC = screen pointer ; HL' = wy, DE' = DY, B' = page ; IXL = passes of 8 pixels.
; pixel = page[(wx.lo and F0h) or (wy.hi and 0Fh)] ; entered at slot (8 - n mod 8) mod 8 so that the count comes out exact.
ps_block:
ps_s0:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s1:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s2:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s3:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s4:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s5:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s6:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
ps_s7:  add hl,de
        ld a,l
        exx
        add hl,de
        xor h
        and 0F0h
        xor h
        ld c,a
        ld a,(bc)
        exx
        ld (bc),a
        inc c
        db 0DDh,02Dh            ; dec ixl
        jp nz,ps_block
        ret
ps_tab: dw ps_s0,ps_s7,ps_s6,ps_s5,ps_s4,ps_s3,ps_s2,ps_s1
        endif
        endif
dr_span_far:                    ; d > 4095: palette index 0
        xor a
; dr_span_fill: A = colour -> row dr_y, columns dr_c0 .. dr_c0 + dr_n - 1 = A
; N1M (lane N1M, pixel-neutral speed change; the original is in build/night/pre_N1M/src/next/draw_b.asm): 8 unrolled
; `ld (de),a ; inc e` slots (11 T per pixel instead of the 24 T of ld (hl),a ; inc l ; djnz) entered at slot
; (8 - n mod 8) mod 8 like the textured span writer, so the pixel count comes out exact. Rows are 128-byte aligned and
; c0 + n <= 128, so `inc e` never has to carry into D. Uses A, B, C, DE, HL, IXL.
dr_span_fill:
        ld c,a                  ; C = colour
        ld a,(dr_y)
        call dr_scr_addr
        ld a,(dr_c0)
        or l
        ld e,a
        ld d,h                  ; DE = screen address of (c0, y)
        ld a,(dr_n)
        ld b,a                  ; B = n (1..128)
        add a,7
        rra
        rra
        rra
        and 1Fh                 ; passes = (n + 7) >> 3 (1..16)
        ld ixl,a
        ld a,b
        and 7
        add a,a
        ld hl,fl_tab
        db 0EDh,031h            ; add hl,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = entry slot (8 - n mod 8) mod 8
        ld a,c                  ; A = colour
        jp (hl)
fl_block:
fl_s0:  ld (de),a
        inc e
fl_s1:  ld (de),a
        inc e
fl_s2:  ld (de),a
        inc e
fl_s3:  ld (de),a
        inc e
fl_s4:  ld (de),a
        inc e
fl_s5:  ld (de),a
        inc e
fl_s6:  ld (de),a
        inc e
fl_s7:  ld (de),a
        inc e
        db 0DDh,02Dh            ; dec ixl
        jp nz,fl_block
        ret
fl_tab: dw fl_s0,fl_s7,fl_s6,fl_s5,fl_s4,fl_s3,fl_s2,fl_s1


; ---------------------------------------------------------------- unrolled wall column slots (rows 0..95)
; even row 2k: ld (ix-128),a ; odd row 2k+1: ld (ix+0),a then inc ixh (next pair) ; wr48 moves IX over the 5800h..5FFFh gap.
wr0:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr1:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr2:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr3:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr4:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr5:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr6:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr7:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr8:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr9:    add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr10:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr11:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr12:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr13:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr14:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr15:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr16:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr17:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr18:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr19:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr20:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr21:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr22:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr23:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr24:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr25:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr26:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr27:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr28:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr29:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr30:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr31:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr32:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr33:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr34:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr35:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr36:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr37:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr38:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr39:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr40:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr41:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr42:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr43:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr44:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr45:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr46:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr47:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr48:   push de                 ; falling through from row 47: IX = 5880h + c -> 6080h + c (row 49)
        ld de,0800h
        add ix,de
        pop de
wr48b:  add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr49:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr50:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr51:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr52:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr53:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr54:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr55:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr56:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr57:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr58:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr59:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr60:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr61:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr62:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr63:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr64:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr65:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr66:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr67:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr68:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr69:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr70:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr71:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr72:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr73:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr74:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr75:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr76:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr77:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr78:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr79:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr80:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr81:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr82:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr83:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr84:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr85:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr86:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr87:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr88:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr89:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr90:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr91:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr92:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr93:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr94:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix-128),a
wr95:   add hl,bc
        ld e,h
        ld a,(de)
        ld (ix+0),a
        inc ixh
wr96:   ret
wr_tab: dw wr0,wr1,wr2,wr3,wr4,wr5,wr6,wr7,wr8,wr9,wr10,wr11,wr12,wr13,wr14,wr15
        dw wr16,wr17,wr18,wr19,wr20,wr21,wr22,wr23,wr24,wr25,wr26,wr27,wr28,wr29,wr30,wr31
        dw wr32,wr33,wr34,wr35,wr36,wr37,wr38,wr39,wr40,wr41,wr42,wr43,wr44,wr45,wr46,wr47
        dw wr48,wr49,wr50,wr51,wr52,wr53,wr54,wr55,wr56,wr57,wr58,wr59,wr60,wr61,wr62,wr63
        dw wr64,wr65,wr66,wr67,wr68,wr69,wr70,wr71,wr72,wr73,wr74,wr75,wr76,wr77,wr78,wr79
        dw wr80,wr81,wr82,wr83,wr84,wr85,wr86,wr87,wr88,wr89,wr90,wr91,wr92,wr93,wr94,wr95
        dw wr96
