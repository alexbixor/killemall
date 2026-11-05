; game_b_next.asm - lane N2 (5 Nov 2026): the GAME rules of edition B, a thin port of src/common/game_a..game_g.asm + etab.asm
; against edition B's variables (px/py Q8 at 5802h/5804h, ang 0..1023, mapc level at LEVEL, ZBUF 128 words at 1A00h).
; Included by main_b.asm after walk_b.asm / draw_b.asm. Variables: main_b_vars.inc (5C00h..5EFFh).
; Rules (brief section 2, 48K file:line in the comments):
;   game_steps  kea48.asm steps/st_two: STEP_B = 5 ticks per game step, >= 3 steps of backlog -> exactly 2 steps run.
;   game_tick   game_a.asm game_tick: bump (forward held) -> doors, SPACE use, M fire, things_tick, pickups, cooldowns,
;               weapon fire frame for 5 steps, health 0 -> YOU DIED (2 s freeze, restart level).
;   doors       game_b.asm: cell ~0.6 cell ahead; 8 opens, 9/10 need key b0/b1 (else NEED A KEY, 25-step cooldown), 11 secret
;               (use only), 12 exit = LEVEL CLEARED (bump only). Door log (ptr, code) restored on restart.
;   pickups     game_c.asm: items 16..20 within 0.5 cell: health +25 (cap 100), ammo +20 (cap 99), keys, shield +50 (cap 100).
;   enemies     game_e.asm/game_f.asm/etab.asm with ETAB_B (docs/enemies_v1.md, 8 bytes per type, hp in pistol hits):
;               idle -> chase when Chebyshev distance < wake and LOS (8 samples); chase = step toward the player per axis,
;               blocked by solid cells; adjacent (< 0.7 cell) -> melee attack after `timer` steps; ranged types (flags b1):
;               0 < dist <= range and LOS -> stand, timer, at `timer` a hit-scan hit (proposal A: 50 % miss beyond 3 cells on
;               bit 0 of ticks), attack frame 5 steps. Shield absorbs first (e_hurt).
;   pistol      game_f.asm fire_action + game_g.asm hitscan: ammo > 0 and no cooldown (12 steps): ammo -1, fire frame, the
;               nearest VIS_B entry covering the centre column (c0 <= 65 and c0 + w >= 63) with ZBUF[64] > its depth and an
;               enemy alive takes 1 hit (= 10 hp); 0 hits left -> dead (state 3), kills + 1; a hit enemy wakes (state 1).
; Z80N: mul d,e = db 0EDh,030h ; add hl,a = db 0EDh,031h.

; ---------------------------------------------------------------- init / restart
game_init:
        ld a,100
        ld (g_health),a
        ld a,50
        ld (g_ammo),a
        xor a
        ld (g_kkeys),a
        ld (g_kills),a
        ld (g_level),a
        ld (g_shield),a
        ld (g_door_n),a
        ld (g_dead),a
        ld (g_clears),a
        ld (g_music_tk),a
        ld (g_music_tk+1),a
        ld a,(ticks)
        ld (g_step_t),a
        ; fall into restart_level
; restart_level: doors back, things from the level, camera from the header, cooldowns/messages cleared (game_d.asm restart_level)
restart_level:
        call doors_restore
        call things_init_b
        ld a,(LV_SX)
        ld h,a
        ld l,128
        ld (px),hl
        ld a,(LV_SY)
        ld h,a
        ld l,128
        ld (py),hl
        ld a,(LV_ANGLE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld (ang),hl
        ld a,1
        ld (g_moved),a
        xor a
        ld (g_door_cool),a
        ld (g_fire_cool),a
        ld (g_wframe),a
        ld (g_nvis),a
        ld (g_freeze),a
        ld (g_msg),a
        ld (g_msg_t),a
        ret

; things_init_b (sprites.asm things_init): clear 32 x 8, copy n_things (cap 32) records type/x/y -> type, x*256+128, y*256+128,
; state 0, hp = ETAB_B[type].hp (pistol hits) for enemies 1..6 or 3 for items, timer 0.
things_init_b:
        ld hl,THINGS_B
        ld de,THINGS_B+1
        ld bc,NTHINGS_B*8-1
        ld (hl),0
        ldir
        ld a,(LEVEL+7)
        or a
        ret z
        cp NTHINGS_B+1
        jr c,ti_n_ok
        ld a,NTHINGS_B
ti_n_ok:
        ld b,a
        ld hl,LV_THINGS
        ld de,THINGS_B
ti_loop:
        ld a,(hl)
        ld (de),a               ; +0 type
        ld c,3                  ; items: 3 (never read)
        cp 7
        jr nc,ti_hp
        push hl
        add a,a
        add a,a
        add a,a                 ; type*8
        ld l,a
        ld h,0
        push de
        ld de,ETAB_B
        add hl,de
        pop de
        ld c,(hl)               ; hp in pistol hits
        pop hl
ti_hp:
        inc hl
        inc de
        ld a,128
        ld (de),a               ; +1 x lo
        inc de
        ld a,(hl)
        ld (de),a               ; +2 x hi = cell
        inc hl
        inc de
        ld a,128
        ld (de),a               ; +3 y lo
        inc de
        ld a,(hl)
        ld (de),a               ; +4 y hi
        inc hl
        inc de
        xor a
        ld (de),a               ; +5 state idle
        inc de
        ld a,c
        ld (de),a               ; +6 hp
        inc de
        xor a
        ld (de),a               ; +7 timer
        inc de
        djnz ti_loop
        ret

; ---------------------------------------------------------------- fixed-rate steps (kea48.asm steps / game_d.asm st_two)
game_steps:
        ld a,(ticks)
        ld hl,g_step_t
        sub (hl)                ; elapsed ticks since the last step (mod 256)
        cp 3*STEP_B
        jr c,gs_ok
        ld a,(ticks)            ; backlog >= 3 steps: keep exactly 2
        sub 2*STEP_B
        ld (hl),a
        ld a,2*STEP_B
gs_ok:  cp STEP_B
        ret c                   ; no step due
        call gs_one
        ld a,(ticks)
        ld hl,g_step_t
        sub (hl)
        cp STEP_B
        ret c
gs_one: ld a,(hl)
        add a,STEP_B
        ld (hl),a
        ; fall into game_tick
; ---------------------------------------------------------------- one 0.1 s game step (game_a.asm game_tick)
game_tick:
        ld a,(g_freeze)
        or a
        jr z,gt_live
        dec a
        ld (g_freeze),a
        ret nz
        ld a,(g_msg)            ; freeze over: 2 = YOU DIED -> stats reset + restart ; 3 = LEVEL CLEARED -> next level
        cp 3
        jr z,gt_next_level
        ld a,100                ; game_d.asm player_dead
        ld (g_health),a
        ld a,50
        ld (g_ammo),a
        xor a
        ld (g_kkeys),a
        ld (g_shield),a
        jp restart_level
gt_next_level:
        ld a,(g_level)          ; game_d.asm level_clear: level + 1; NLEVELS_B = 1 -> back to level 0 (N2_QUESTIONS.md)
        inc a
        cp NLEVELS_B
        jr c,gt_nl_ok
        xor a
gt_nl_ok:
        ld (g_level),a
        jp restart_level
gt_live:
        ld a,(g_keys)
        bit KB_FWD,a
        call nz,bump_action     ; doors auto-open when walked into (exit = level cleared)
        ld a,(g_freeze)
        or a
        ret nz                  ; level cleared this step: nothing else
        ld a,(g_keys)
        bit KB_USE,a
        call nz,use_action
        ld a,(g_keys)
        bit KB_FIRE,a
        call nz,fire_action
        call things_tick
        call pickups
        ld hl,g_door_cool
        ld a,(hl)
        or a
        jr z,gt_c1
        dec (hl)
gt_c1:  ld hl,g_fire_cool
        ld a,(hl)
        or a
        jr z,gt_c2
        dec (hl)
        cp 7
        jr nz,gt_c2
        xor a
        ld (g_wframe),a         ; fire frame shown for 5 steps (12 -> 7)
gt_c2:  ld hl,g_msg_t
        ld a,(hl)
        or a
        jr z,gt_c3
        dec (hl)
        jr nz,gt_c3
        xor a
        ld (g_msg),a
gt_c3:  ld a,(g_health)
        or a
        ret nz
        ; player_dead (game_d.asm): message, 2 s freeze, then the reset above
        ld a,2
        ld (g_msg),a
        ld a,20
        ld (g_freeze),a
        ld (g_msg_t),a
        ld hl,g_dead
        inc (hl)
        ret

; ---------------------------------------------------------------- doors (game_b.asm)
; ahead_cell: cell ~0.6 cell in front of the player: (px + dirx*5/8, py + diry*5/8) -> HL = cell ptr, A = code (1 if outside)
ahead_cell:
        ld hl,(dirx)
        call ac_scale
        ld de,(px)
        add hl,de
        ld (g_ax),hl
        ld hl,(diry)
        call ac_scale
        ld de,(py)
        add hl,de
        ld (g_ay),hl
        ld a,(g_ax+1)
        ld b,a
        ld a,(g_ay+1)
        ld c,a
        jp cell_ptr_bc
ac_scale:                       ; HL = HL*5/8 (signed): (HL >> 1) + (HL >> 3)
        sra h
        rr l
        ld d,h
        ld e,l
        sra h
        rr l
        sra h
        rr l
        add hl,de
        ret
; cell_ptr_bc: B = cell x, C = cell y -> HL = cell pointer (or a dummy solid byte when outside), A = code
cell_ptr_bc:
        ld a,b
        cp MAPC_W
        jr nc,cp_out
        ld a,c
        cp MAPC_H
        jr nc,cp_out
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,b
        db 0EDh,031h            ; add hl,a
        ld de,LV_CELLS
        add hl,de
        ld a,(hl)
        ret
cp_out: ld hl,solid_byte
        ld a,1
        ret
solid_byte: db 1

bump_action:
        call ahead_cell
        cp 8
        ret c
        cp 12
        jp z,level_clear
        cp 11
        ret z                   ; secret walls need USE
        jr door_try
use_action:
        call ahead_cell
        cp 8
        ret c
        cp 12
        ret nc
door_try:
        cp 9
        jr c,door_open          ; 8: unlocked
        cp 11
        jr z,door_open          ; secret wall
        sub 8                   ; 9 -> 1 (red b0), 10 -> 2 (blue b1)
        ld c,a
        ld a,(g_kkeys)
        and c
        jr nz,door_open
        ld a,(g_door_cool)
        or a
        ret nz
        ld a,25
        ld (g_door_cool),a
        ld a,1                  ; NEED A KEY
        ld (g_msg),a
        ld a,10
        ld (g_msg_t),a
        ret
door_open:
        ld a,(g_door_n)
        cp 16
        ret nc
        ld e,a
        add a,a
        add a,e                 ; 3 bytes per entry
        ld e,a
        ld d,0
        ld ix,DOOR_LOG_B
        add ix,de
        ld (ix+0),l
        ld (ix+1),h
        ld a,(hl)
        ld (ix+2),a
        ld (hl),0
        ld hl,g_door_n
        inc (hl)
        ret
doors_restore:
        ld a,(g_door_n)
        or a
        ret z
        ld b,a
        ld ix,DOOR_LOG_B
dr_l:   ld l,(ix+0)
        ld h,(ix+1)
        ld a,(ix+2)
        ld (hl),a
        ld de,3
        add ix,de
        djnz dr_l
        xor a
        ld (g_door_n),a
        ret
level_clear:
        ld a,3                  ; LEVEL CLEARED: 2 s freeze, then the next level (game_tick)
        ld (g_msg),a
        ld a,20
        ld (g_freeze),a
        ld (g_msg_t),a
        ld hl,g_clears
        inc (hl)
        ret

; ---------------------------------------------------------------- pickups (game_c.asm)
pickups:
        ld ix,THINGS_B
        ld b,NTHINGS_B
pk_l:   ld a,(ix+0)
        cp 16
        jr c,pk_next
        cp 21
        jr nc,pk_next           ; barrel / lamp are decor
        call near_player
        jr nc,pk_next
        push bc
        call pickup_item
        pop bc
pk_next:
        ld de,8
        add ix,de
        djnz pk_l
        ret
; near_player: carry when |dx| < 0.5 and |dy| < 0.5 cell ((delta + 128) has a zero high byte)
near_player:
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(px)
        or a
        sbc hl,de
        ld de,128
        add hl,de
        ld a,h
        or a
        ret nz
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(py)
        or a
        sbc hl,de
        ld de,128
        add hl,de
        ld a,h
        or a
        ret nz
        scf
        ret
pickup_item:
        ld a,(ix+0)
        ld (ix+0),0
        cp 16
        jr nz,pi1
        ld a,(g_health)
        add a,25
        cp 101
        jr c,pi_h
        ld a,100
pi_h:   ld (g_health),a
        ret
pi1:    cp 17
        jr nz,pi2
        ld a,(g_ammo)
        add a,20
        cp 100
        jr c,pi_a
        ld a,99
pi_a:   ld (g_ammo),a
        ret
pi2:    cp 20
        jr nz,pi3
        ld a,(g_shield)
        add a,50
        cp 101
        jr c,pi_s
        ld a,100
pi_s:   ld (g_shield),a
        ret
pi3:    sub 17                  ; 18 -> 1 red, 19 -> 2 blue
        ld hl,g_kkeys
        or (hl)
        ld (hl),a
        ret

; ---------------------------------------------------------------- enemies (game_e.asm, game_f.asm, etab.asm)
things_tick:
        ld ix,THINGS_B
        ld b,NTHINGS_B
tt_l:   push bc
        ld a,(ix+0)
        or a
        jr z,tt_next
        cp 7
        jr nc,tt_next           ; items: no AI
        ld a,(ix+5)
        cp 3
        jr z,tt_next            ; dead
        call enemy_think
tt_next:
        ld de,8
        add ix,de
        pop bc
        djnz tt_l
        ret
etab_row:                       ; IY -> ETAB_B row of (ix+0)
        ld a,(ix+0)
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld iy,ETAB_B
        add iy,de
        ret
enemy_think:
        call etab_row
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(px)
        or a
        sbc hl,de
        ld (e_dx),hl
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(py)
        or a
        sbc hl,de
        ld (e_dy),hl
        ld a,(e_dx+1)
        call abs8
        ld c,a
        ld a,(e_dy+1)
        call abs8
        cp c
        jr nc,et_d
        ld a,c
et_d:   ld (e_dist),a           ; Chebyshev distance in cells (signed high bytes)
        cp (iy+6)
        jr nc,et_idle           ; beyond the wake radius
        or a
        jr nz,et_notadj
        call near_player07
        jp c,et_attack
et_notadj:
        bit 1,(iy+7)
        jr z,et_wake
        ld a,(e_dist)
        cp (iy+4)
        jr z,et_rng
        jr nc,et_wake           ; farther than the range: chase
et_rng: call los_check
        jp c,et_ranged
et_wake:
        ld a,(ix+5)
        cp 1
        jr z,et_chase
        call los_check
        jr nc,et_idle
        ld (ix+5),1
et_chase:
        ld (ix+7),0
        ld hl,(e_dx)
        call step_axis
        ld c,(ix+1)
        ld b,(ix+2)
        add hl,bc
        push hl
        ld b,h
        ld c,(ix+4)
        call cell_ptr_bc
        pop hl
        or a
        jr nz,et_y
        ld (ix+1),l
        ld (ix+2),h
et_y:   ld hl,(e_dy)
        call step_axis
        ld c,(ix+3)
        ld b,(ix+4)
        add hl,bc
        push hl
        ld c,h
        ld b,(ix+2)
        call cell_ptr_bc
        pop hl
        or a
        ret nz
        ld (ix+3),l
        ld (ix+4),h
        ret
et_idle:
        ld (ix+5),0
        ret
abs8:   or a
        ret p
        neg
        ret
; step_axis: HL = thing - player delta -> HL = -sign(delta) * step_q8 (0 when 0 <= delta < step)
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
        ld h,a
        ret
sa_neg: ld l,(iy+1)
        ld h,0
        ret
near_player07:                  ; carry when |dx| and |dy| < 0.7 cell (180)
        ld hl,(e_dx)
        call abs16
        ld de,180
        or a
        sbc hl,de
        ret nc
        ld hl,(e_dy)
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
; los_check: carry when no solid cell between the thing and the player: 8 samples from the player along (dx, dy)/8
los_check:
        ld b,8
        ld hl,(px)
        ld (l_x),hl
        ld hl,(py)
        ld (l_y),hl
        ld hl,(e_dx)
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        ld (l_sx),hl
        ld hl,(e_dy)
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        ld (l_sy),hl
los_l:  ld hl,(l_x)
        ld de,(l_sx)
        add hl,de
        ld (l_x),hl
        ld hl,(l_y)
        ld de,(l_sy)
        add hl,de
        ld (l_y),hl
        push bc
        ld c,h
        ld a,(l_x+1)
        ld b,a
        call cell_ptr_bc
        pop bc
        or a
        ret nz                  ; solid: NC
        djnz los_l
        scf
        ret
; et_attack: adjacent melee (etab.asm)
et_attack:
        ld (ix+5),2
        ld a,(ix+7)
        inc a
        ld (ix+7),a
        cp (iy+5)
        ret c
        ld (ix+7),0
        ld c,(iy+2)             ; melee damage
        jr e_hurt
; et_ranged: hit-scan ranged attack (etab.asm et_ranged + docs/enemies_v1.md proposal A miss rule)
et_ranged:
        ld a,(ix+7)
        inc a
        ld (ix+7),a
        cp (iy+5)
        jr nc,er_hot
        ld (ix+5),1             ; aiming in the chase pose
        ret
er_hot: jr z,er_fire
        sub (iy+5)
        cp 5
        ret c                   ; attack frame held for 5 steps
        ld (ix+7),0
        ld (ix+5),1
        ret
er_fire:
        ld (ix+5),2
        ld a,(e_dist)
        cp 4
        jr c,er_hit             ; <= 3 cells: always hits
        ld a,(ticks)
        and 1
        ret nz                  ; beyond 3 cells: 50 % miss (bit 0 of ticks)
er_hit: ld c,(iy+3)             ; ranged damage
; e_hurt: C = damage; the shield absorbs first
e_hurt: ld a,(g_shield)
        or a
        jr z,eh_hp
        sub c
        jr nc,eh_s
        xor a
eh_s:   ld (g_shield),a
        ret
eh_hp:  ld a,(g_health)
        sub c
        jr nc,eh_h
        xor a
eh_h:   ld (g_health),a
        ret

; ---------------------------------------------------------------- pistol (game_f.asm fire_action, game_g.asm hitscan)
fire_action:
        ld a,(g_fire_cool)
        or a
        ret nz
        ld a,(g_ammo)
        or a
        ret z
        dec a
        ld (g_ammo),a
        ld a,12
        ld (g_fire_cool),a
        ld a,1
        ld (g_wframe),a
        ; hitscan over VIS_B (far -> near): walk from the nearest (last) entry back
        ld a,(g_nvis)
        or a
        ret z
        ld b,a
        dec a
        add a,a
        add a,a
        add a,a                 ; 8*(n-1)
        ld l,a
        ld h,0
        ld de,VIS_B
        add hl,de
hs_l:   push hl
        push bc
        push hl
        pop iy                  ; IY -> vis entry
        ld l,(iy+2)
        ld h,(iy+3)             ; c0 (s16)
        ld de,66
        or a
        sbc hl,de               ; c0 - 66 < 0  <=> c0 <= 65
        jp p,hs_next
        ld l,(iy+2)
        ld h,(iy+3)
        ld e,(iy+4)
        ld d,0
        add hl,de               ; c0 + w
        ld de,63
        or a
        sbc hl,de               ; c0 + w - 63 >= 0
        jp m,hs_next
        ld hl,(ZBUF+128)        ; ZBUF[64]
        ld e,(iy+0)
        ld d,(iy+1)
        or a
        sbc hl,de               ; ZBUF[64] - depth > 0 -> sprite in front of the wall
        jp m,hs_next
        jr z,hs_next
        ld a,(iy+7)             ; thing index
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,THINGS_B
        add hl,de
        push hl
        pop ix
        ld a,(ix+0)
        cp 7
        jr nc,hs_next           ; items let the shot pass
        ld a,(ix+5)
        cp 3
        jr z,hs_next            ; already dead
        call enemy_hit
        pop bc
        pop hl
        ret
hs_next:
        pop bc
        pop hl
        ld de,8
        or a
        sbc hl,de
        djnz hs_l
        ret
enemy_hit:
        ld a,(ix+6)
        dec a                   ; one pistol hit = 10 hp = 1 unit
        jr z,eh_dead
        ld (ix+6),a
        ld (ix+5),1             ; hit enemies wake up and chase
        ret
eh_dead:
        ld (ix+6),0
        ld (ix+5),3
        ld hl,g_kills
        inc (hl)
        ret

; ---------------------------------------------------------------- ETAB_B (docs/enemies_v1.md machine block, 8 bytes per type)
; hp (pistol hits), step_q8, melee dmg, ranged dmg, ranged range (cells), attack timer (steps), wake radius (cells), flags
ETAB_B:
        db  0,  0,  0,  0,  0,  0,  0, 00h    ; 0 none
        db  3, 15, 10,  0,  0, 25, 10, 04h    ; 1 imp        hp 30
        db  3, 15, 15,  0,  0, 25, 10, 04h    ; 2 zombie     hp 30
        db  3, 13,  0, 20,  6, 20, 10, 02h    ; 3 shotgunner hp 30 ranged 20 range 6
        db  6, 10,  0, 15,  8, 30, 10, 03h    ; 4 floater    hp 60 ranged 15 range 8, floating
        db 12, 18, 25,  0,  0, 20, 10, 04h    ; 5 brute      hp 120
        db 40, 13, 35, 20,  8, 15, 10, 0Eh    ; 6 boss       hp 400 melee 35 ranged 20 range 8
SPRBASE_B:                                    ; type -> base sprite id (walk A; +1 walk B, +2 attack, +3 dead)
        db 0, 0, 4, 18, 22, 26, 30
ITSPR_B:                                      ; item type 16..22 -> sprite id (health, ammo, red key, blue key, shield=health art, barrel, lamp)
        db 8, 9, 10, 11, 8, 12, 13
