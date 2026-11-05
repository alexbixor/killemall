; game_f.asm (T1) - AI helpers (abs8, step_axis, near_player07, los_check) and the pistol hitscan (fire_action).
abs8:   or a
        ret p
        neg
        ret
; step_axis: HL = thing - player delta (s16) -> HL = -sign(delta) * step (ETAB +1 via IY, lane G: 15 = 0.06 cell for types
; 1 / 2); 0 when 0 <= delta < step (the same dead zone as the old `cp 15`; negative deltas always step, as before)
step_axis:
        bit 7,h
        jr nz,sa_neg
        ld a,h
        or a
        jr nz,sa_m
        ld a,l
        cp (iy+1)
        jr nc,sa_m
        ld hl,0
        ret
sa_m:   xor a
        sub (iy+1)
        ld l,a
        sbc a,a
        ld h,a                 ; HL = -step
        ret
sa_neg: ld l,(iy+1)
        ld h,0
        ret
; near_player07: carry when |dx| and |dy| < 0.7 cell (edx/edy set)
near_player07:
        ld hl,(edx)
        call abs16
        ld de,180
        or a
        sbc hl,de
        ret nc
        ld hl,(edy)
        call abs16
        ld de,180
        or a
        sbc hl,de
        ret
abs16:  bit 7,h
        ret z
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
        ret
; los_check: carry when no wall cell between the thing (IX) and the player: 8 samples along the segment (cheap, deterministic)
los_check:
        ld b,8
        ld hl,(posx)
        ld (lx),hl
        ld hl,(posy)
        ld (ly),hl
        ld hl,(edx)
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l                   ; dx/8
        ld (lsx),hl
        ld hl,(edy)
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        ld (lsy),hl
los_l:  ld hl,(lx)
        ld de,(lsx)
        add hl,de
        ld (lx),hl
        ld hl,(ly)
        ld de,(lsy)
        add hl,de
        ld (ly),hl
        ld c,h
        ld a,(lx+1)
        call cell_at
        or a
        ret nz                 ; wall: NC
        djnz los_l
        scf
        ret
lx:     defw 0
ly:     defw 0
lsx:    defw 0
lsy:    defw 0
; fire_action: pistol. Needs ammo and a 12-frame cooldown; hud_weapon 1 (fire frame), snd 1, hitscan over the vis list:
; nearest sprite entry (last in the far->near list) that covers columns 30..33 and is an enemy -> hp -= 10; death -> state 3, kills++, snd 5.
fire_action:
        ld a,(fire_cool)
        or a
        ret nz
        ld a,(ammo)
        or a
        ret z
        dec a
        ld (ammo),a
        ld a,12
        ld (fire_cool),a
        ld a,1
        ld (weapon_frame),a
        ld a,1
        call snd_fx
        jp hitscan
fire_cool: defb 0
weapon_frame: defb 0
