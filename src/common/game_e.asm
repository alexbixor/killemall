; game_e.asm (T1; lane G 5 Nov 2026: ETAB) - enemy AI: per-thing state 0 idle 1 chase 2 attack 3 dead. One step (0.1 s) per
; call for types 1..6 (enemies: ETAB rows, ../common/etab.asm). Within the wake radius + LOS (los_check) -> chase: step_q8 toward
; the player (axis separated, blocked by walls/doors); adjacent (< 0.7 cell) -> attack: the timer counts (25 steps = 2.5 s since
; M2.9) then melee dmg, snd 8 then 4. Flags bit 1 (ranged) adds a hit-scan attack from 1..range cells with LOS (etab.asm).
; Types 1 / 2 keep their pre-G numbers in ETAB rows 1 / 2: their behaviour is byte-for-byte unchanged (tools/test_game_replay.py).
things_tick:
        ld ix,things
        ld b,NTHINGS
tt_l:   push bc
        ld a,(ix+0)
        or a
        jr z,tt_next
        cp 7
        jr nc,tt_next          ; items / other types: no AI
        ld a,(ix+5)
        cp 3
        jr z,tt_next           ; dead
        call enemy_think
tt_next:
        ld de,8
        add ix,de
        pop bc
        djnz tt_l
        ret
; et_attack / e_hurt live in ../common/etab.asm (top-of-RAM page 0FF01h) since lane G: 57 B of this file moved
; there so the high block stays >= 40 B below the stack top (the ETAB look-ups cost 37 B more than the old constants).
; etab_row: IX -> thing -> IY -> its ETAB row (16 B each, page-contained). A changed. Called by enemy_think and et_attack.
etab_row:
        ld a,(ix+0)
        add a,a
        add a,a
        add a,a
        add a,a
        add a,ETAB and 255
        ld iyl,a
        ld iyh,ETAB/256
        ret
enemy_think:
        call etab_row          ; IY -> this type's ETAB row (16 B each, page-contained: etab.asm)
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(posx)
        or a
        sbc hl,de
        ld (edx),hl
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(posy)
        or a
        sbc hl,de
        ld (edy),hl
        ld a,(edx+1)
        call abs8
        ld c,a
        ld a,(edy+1)
        call abs8
        cp c
        jr nc,$+3
        ld a,c                 ; A = Chebyshev distance (cells)
        cp (iy+6)
        jr nc,et_idle          ; beyond the wake radius
        or a
        jr nz,et_notadj
        call near_player07
        jp c,et_attack         ; etab.asm (jp: it lives in the top-of-RAM page)
et_notadj:
        bit 1,(iy+7)
        jr z,et_wake
        cp (iy+4)
        jr z,$+4
        jr nc,et_wake          ; ranged: 1..range cells (dist 0 falls through to melee / chase above)
        call los_check
        jp c,et_ranged         ; in range with LOS: stand and shoot (etab.asm)
et_wake:
        ld a,(ix+5)
        cp 1
        jr z,et_chase
        call los_check
        jr nc,et_idle
        ld (ix+5),1
et_chase:
        ld (ix+7),0
        ld hl,(edx)            ; move toward the player: -sign(dx)*step_q8 per axis
        call step_axis
        ld c,(ix+1)
        ld b,(ix+2)
        add hl,bc
        push hl
        ld a,h
        ld c,(ix+4)
        call cell_at
        pop hl
        or a
        jr nz,et_y
        ld (ix+1),l
        ld (ix+2),h
et_y:   ld hl,(edy)
        call step_axis
        ld c,(ix+3)
        ld b,(ix+4)
        add hl,bc
        push hl
        ld c,h
        ld a,(ix+2)
        call cell_at
        pop hl
        or a
        ret nz
        ld (ix+3),l
        ld (ix+4),h
        ret
et_idle:
        ld (ix+5),0
        ret
edx:    defw 0
edy:    defw 0
