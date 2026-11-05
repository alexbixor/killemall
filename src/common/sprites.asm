; sprites.asm (T1; lane G: hp from ETAB) - things table, camera transform, visibility list. Drawing is in sprites_b.asm.
; thing record (8 bytes): +0 type (0 none; 1 imp 2 zombie 16 health 17 ammo 18 red key 19 blue key 21 barrel 22 lamp)
;   +1 x (8.8 word) +3 y (8.8 word) +5 state (0 idle 1 chase 2 attack 3 dead) +6 hp +7 timer/anim
NTHINGS equ 16
; perp_h: HL = perpendicular distance 8.8 -> A = wall virtual height (same lookup the renderer uses). HL preserved.
perp_h: ld a,h
        cp 4
        jr nc,ph2
        ld a,l                 ; index = perp >> 2 = h*64 + l/4  (dist = index/64)
        rrca
        rrca
        and 63
        ld c,a
        ld a,h
        rrca
        rrca
        or c
        ld c,a
        ld b,HTABN/256
        ld a,(bc)
        ret
ph2:    cp 32
        jr nc,ph3
        ld a,l                 ; index = perp >> 5 = h*8 + l/32  (dist = index/8)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,h
        add a,a
        add a,a
        add a,a
        or c
        ld c,a
        ld b,HTABF/256
        ld a,(bc)
        ret
ph3:    ld a,2
        ret
; mul168: HL (u16) * A (u8) -> A:HL (24-bit unsigned). ~520 T.
mul168: ld e,l
        ld d,h
        ld hl,0
        ld c,a
        xor a
        ld b,8
m168_l: add hl,hl
        adc a,a
        sla c
        jr nc,m168_n
        add hl,de
        adc a,0
m168_n: djnz m168_l
        ret
; muls_7: HL = s16, A = s1.7 (cos/sin high byte... passed as s8 with 64 = 0.5) -> HL = HL*A >> 7 (s16)
muls_7: ld (ms_sgn),a
        ld c,a
        bit 7,h
        jr z,ms1
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
        ld a,c
        cpl
        ld (ms_sgn),a
ms1:    ld a,c
        or a
        jp p,ms2
        neg
ms2:    call mul168
        add hl,hl
        adc a,a
        ld l,h
        ld h,a                 ; HL = product >> 7
        ld a,(ms_sgn)
        or a
        ret p
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
        ret
ms_sgn: defb 0
; things_init: copy the level's thing list (type,x,y cell ints) into the runtime table, centre of cell, hp by type.
things_init:
        IF DEFINED GLIDE
        call glide_mark        ; M2.9b: no stale camera on the first frame of a level
        ENDIF
        ld hl,CMIN             ; M2.6 P2E: no sprite colour marks at the start of a level (48 B)
        ld de,CMIN+1
        ld bc,47
        ld (hl),0
        ldir
        ld hl,things
        ld de,things+1
        ld bc,NTHINGS*8-1
        ld (hl),0
        ldir
        ld hl,(mapptr)
        dec hl                 ; header byte 7 = n_things
        ld a,(hl)
        ld de,1025
        add hl,de              ; HL -> first thing record of the level
        ld de,things
        or a
        ret z
        cp NTHINGS+1
        jr c,ti1
        ld a,NTHINGS
ti1:    ld b,a
ti_l:   ld a,(hl)
        ld (de),a              ; type
        ld c,30                ; items keep hp 30 as before (never read: no AI, the hitscan ignores them)
        bit 4,a
        jr nz,ti_hp
        push hl
        add a,a                ; lane G: hp = ETAB[type].hp for enemies 1..6 (etab.asm)
        add a,a
        add a,a
        add a,a
        add a,ETAB and 255
        ld l,a
        ld h,ETAB/256
        ld c,(hl)              ; C = hp
        pop hl
ti_hp:  inc hl
        inc de
        ld a,128
        ld (de),a              ; x frac
        inc de
        ld a,(hl)
        ld (de),a              ; x int
        inc hl
        inc de
        ld a,128
        ld (de),a
        inc de
        ld a,(hl)
        ld (de),a              ; y int
        inc hl
        inc de
        xor a
        ld (de),a              ; state idle
        inc de
        ld a,c
        ld (de),a              ; hp (ETAB)
        inc de
        xor a
        ld (de),a              ; timer
        inc de
        djnz ti_l
        ret
; things: NTHINGS*8 runtime table -> DRAM (state.asm, M2.2)
