; game_b.asm (T1) - doors, use/bump, pickups, fire (hitscan), level clear / death handling.
; ahead_cell: cell ~0.6 cell in front of the player -> HL = cell ptr, A = code
ahead_cell:
        ld a,(angle)
        ld l,a
        ld h,0
        add hl,hl
        push hl
        ld de,MOVXTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        sla e
        rl d
        sla e
        rl d                   ; 0.6 cell
        ld hl,(posx)
        add hl,de
        ld a,h
        ld (ac_x),a
        pop hl
        ld de,MOVYTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        sla e
        rl d
        sla e
        rl d
        ld hl,(posy)
        add hl,de
        ld c,h
        ld a,(ac_x)
        call cell_ptr
        ld a,(hl)
        ret
ac_x:   defb 0
; bump_action (forward held) / use_action (use pressed): doors 8 open, 9/10 need key, 11 secret (use only), 12 exit.
bump_action:
        call ahead_cell
        cp 8
        ret c
        cp 12
        jp z,level_clear
        cp 11
        ret z                  ; secret walls need USE
        jr door_try
use_action:
        call ahead_cell
        cp 8
        ret c
        cp 12
        ret nc
door_try:
        cp 9
        jr c,door_open         ; 8: unlocked
        cp 11
        jr z,door_open         ; secret wall
        sub 8                  ; 9 -> 1 (red, b0), 10 -> 2 (blue, b1)
        ld c,a
        ld a,(keys)
        and c
        jr nz,door_open
        ld a,(door_cool)
        or a
        ret nz
        ld a,25
        ld (door_cool),a
        ld a,7
        call snd_fx
        ld hl,msg_key
        jp hud_message
door_open:
        ld a,(door_n)
        cp 16
        ret nc
        ld e,a
        add a,a
        add a,e                ; 3 bytes per entry
        ld e,a
        ld d,0
        ld ix,door_log
        add ix,de
        ld (ix+0),l
        ld (ix+1),h
        ld a,(hl)
        ld (ix+2),a
        ld (hl),0
        ld hl,door_n
        inc (hl)
        ld a,2
        jp snd_fx
; doors_restore: put the original codes back (level restart)
doors_restore:
        ld a,(door_n)
        or a
        ret z
        ld b,a
        ld ix,door_log
dr_l:   ld l,(ix+0)
        ld h,(ix+1)
        ld a,(ix+2)
        ld (hl),a
        ld de,3
        add ix,de
        djnz dr_l
        xor a
        ld (door_n),a
        ret
door_n:   defb 0
door_cool: defb 0
; door_log: 48 B -> DRAM (state.asm, M2.2)
msg_key: defb "NEED A KEY",0
