; game_g.asm (T1) - hitscan over the vis list (built by the last render: far -> near). The centre ray is column 32;
; hit when c0 <= 33 and c0 + nc >= 31 (±2 columns). The vis entry is only present if the sprite passed the zbuf test
; in at least... (vis holds all projected sprites; depth vs wall per column was applied while drawing) -> check zbuf[32] < hv.
hitscan:
        ld a,(nvis)
        or a
        ret z
        ld b,a
        ld hl,vis
        ld de,6
        dec a
        ld c,a
        add a,a
        add a,c                ; 3*(n-1)
        add a,a                ; 6*(n-1)
        add a,l
        ld l,a
        jr nc,$+3
        inc h                  ; HL -> nearest entry
hs_l:   push hl
        push bc
        ld a,(hl)
        ld (hs_hv),a
        inc hl
        ld a,(hl)              ; c0 (s8)
        ld c,a
        inc hl
        ld a,(hl)              ; nc
        inc hl
        inc hl
        inc hl
        ld e,(hl)              ; thing idx
        add a,c                ; c0 + nc (s8)
        cp 31
        jp m,hs_next           ; right edge left of the centre
        ld a,c
        cp 34
        jp p,hs_next           ; c0 >= 34 (s8): left of nothing... entry right of the centre
        ld a,(zbuf+32)
        ld hl,hs_hv
        cp (hl)
        jr nc,hs_next          ; wall nearer than the sprite in the centre column
        ld a,e
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,things
        add hl,de
        push hl
        pop ix
        ld a,(ix+0)
        cp 7
        jr nc,hs_next          ; not an enemy (items/decor let the shot pass); lane G: types 1..6 (ETAB rows)
        ld a,(ix+5)
        cp 3
        jr z,hs_next           ; already dead
        call enemy_hit
        pop bc
        pop hl
        ret
hs_next:
        pop bc
        pop hl
        ld de,6
        or a
        sbc hl,de
        djnz hs_l
        ret
hs_hv:  defb 0
enemy_hit:
        ld a,(ix+6)
        and 31                 ; M2.6 blood 1: bits 6..7 = red flash frames left (blood.asm ds_inkl)
        sub 10
        jr c,eh_dead
        jr z,eh_dead
        or 0xC0                ; flash 3 frames
        ld (ix+6),a
        ld (ix+5),1            ; hit enemies wake up and chase
        ret
eh_dead:
        ld (ix+6),0xC0         ; hp 0 + flash 3 frames: the corpse flashes red, then turns white
        ld (ix+5),3
        ld hl,kills
        inc (hl)
        ld a,5
        jp snd_fx
