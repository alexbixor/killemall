; sprites_c.asm (T1) - projection of one thing to screen columns, vis list insert, painter's sort.
; thing_xform2: tdx/tdy/tdepth set, IX -> thing. Camera lateral s = -dx*sin + dy*cos; column cx = 32 + 32.3*s/depth
; (M2.5C: plane 0.99 -> 32/0.99 rays per unit of s/depth; was 48.5 = 32/0.66).
thing_xform2:
        ld hl,(tdepth)
        call perp_h            ; A = virtual height at this depth (same lookup as walls)
        cp 6
        ret c                  ; too small to see
        cp 129
        jr c,$+4
        ld a,128               ; cap (CPU bound, NCTAB/VSTEP sized for it)
        ld (thv),a
        ld hl,(tdx)
        ld a,(sin7)
        neg
        call muls_7
        push hl
        ld hl,(tdy)
        ld a,(cos7)
        call muls_7
        pop de
        add hl,de              ; HL = lateral (s16, 8.8 cells)
        ld a,h
        and 128
        ld (tsgn),a
        jr z,tx2p
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
tx2p:   push hl                ; |lat|
        ld hl,(tdepth)         ; inv = 65536/depth via RECIP (index < 512, else >>3 and shift back)
        ld a,h
        cp 2
        jr c,tx2a
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        add hl,hl
        ld de,RECIP
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e
        jr tx2b
tx2a:   add hl,hl
        ld de,RECIP
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
tx2b:   pop bc                 ; BC = |lat|, DE = inv
        call mul16             ; DE:HL = |lat| * inv  (< 2^23)
        ld a,d
        or a
        ret nz                 ; far off screen
        ld a,e
        cp 2
        ret nc                 ; product >= 2^17 -> |cx-32| >= 64: off screen
        ld l,h                 ; v = product >> 10  (ratio * 64)
        ld h,e
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h                 ; A = v (0..127)
        srl a                  ; A = v/2 = |cx - 32|  (M2.5C: 32.3 ~ 64 / 2)
        ld c,a
        ld a,(tsgn)
        or a
        ld a,c
        jr z,tx2c
        neg
tx2c:   add a,32               ; A = cx (s8)
        ld (tcx),a
        ld a,(thv)
        bit 4,(ix+0)
        call z,enemy_h         ; M2.2: enemies are drawn 0.8 x the wall height (width here, height in draw_sprite)
        ld c,a
        ld b,NCTAB/256
        ld a,NCTAB and 255
        add a,c
        ld c,a
        jr nc,$+3
        inc b
        ld a,(bc)              ; nc = columns
        ld (tnc),a
        srl a
        ld c,a
        ld a,(tcx)
        sub c                  ; c0 = cx - nc/2 (s8)
        ld (tc0),a
        bit 7,a
        jr nz,tx2n
        cp 64
        ret nc                 ; left edge beyond the right border
        jp vis_add
tx2n:   ld c,a
        ld a,(tnc)
        add a,c                ; c0 + nc (s8, no overflow: c0 >= -95, nc <= 64)
        ret z
        ret m                  ; right edge still left of column 0
        jp vis_add
; enemy_h: A = hv -> A = hv - hv/4 + hv/16 (0.8125 hv; the depth test keeps the true hv)
enemy_h:
        ld c,a
        srl c
        srl c
        sub c
        srl c
        srl c
        add a,c
        ret
thv:    defb 0
tcx:    defb 0
tnc:    defb 0
tc0:    defb 0
tsgn:   defb 0
