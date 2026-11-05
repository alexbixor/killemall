; game_e.asm (T1) - enemy AI: per-thing state 0 idle 1 chase 2 attack 3 dead. Runs every frame for types 1 (imp) / 2 (zombie).
; within 10 cells + LOS (los_check) -> chase: step 0.06 cell toward the player (axis separated, blocked by walls/doors);
; adjacent (< 0.7 cell) -> attack: timer counts 25 steps (2.5 s since M2.9) then damage 10 (imp) / 15 (zombie), snd 8 then 4.
things_tick:
        ld ix,things
        ld b,NTHINGS
tt_l:   push bc
        ld a,(ix+0)
        or a
        jr z,tt_next
        cp 3
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
enemy_think:
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
        cp 10
        jr nc,et_idle
        or a
        jr nz,et_notadj
        call near_player07
        jr c,et_attack
et_notadj:
        ld a,(ix+5)
        cp 1
        jr z,et_chase
        call los_check
        jr nc,et_idle
        ld (ix+5),1
et_chase:
        ld (ix+7),0
        ld hl,(edx)            ; move toward the player: -sign(dx)*0.06 per axis
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
et_attack:
        ld (ix+5),2
        ld a,(ix+7)
        inc a
        ld (ix+7),a
        cp 25
        ret c
        ld (ix+7),0
        ld a,8
        call snd_fx
        ld a,(ix+0)
        ld c,10
        dec a
        jr z,$+4
        ld c,15
        ld a,(shield)          ; M2.2: shield absorbs the hit while it lasts
        or a
        jr z,eh_hp
        sub c
        jr nc,$+3
        xor a
        ld (shield),a
        jr eh_snd
eh_hp:  ld a,(health)
        sub c
        jr nc,$+3
        xor a
        ld (health),a
eh_snd: ld a,4
        jp snd_fx
edx:    defw 0
edy:    defw 0
