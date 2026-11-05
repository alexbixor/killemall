; etab.asm (lane G, 5 Nov 2026) - ETAB: the ONE table that describes every enemy type, read by the AI (game_e.asm, game_f.asm
; step_axis), things_init (sprites.asm, hp), vis_add (sprites_d.asm, base sprite id) and ds_inkl (blood.asm, ink).
; Included by kea48.asm at org 0FF01h: the 255 bytes above the IM2 vector table that no edition ever used. The table is the
; 128 B at 0FF70h (page-contained: row = ETAB + type*16, looked up with ld l,a / ld h,ETAB/256, so the two
; look-ups on the render path stay as cheap as the old THSPR / INKTAB ones); et_ranged sits below it.
;
; ETAB row (16 bytes, index = thing type 0..6; row 0 = type 0 "none", never looked up by the shipped game):
;   +0  hp            hit points at things_init (a pistol hit takes 10, game_g.asm enemy_hit)
;   +1  step_q8       cells per 0.1 s step * 256 (0.06 cell -> 15; also the per-axis dead zone, game_f.asm step_axis)
;   +2  melee dmg     health/shield damage when the attack timer fires adjacent (< 0.7 cell)
;   +3  ranged dmg    damage of the hit-scan ranged attack (flags bit 1)
;   +4  ranged range  cells (Chebyshev); the ranged attack needs 0 < dist <= range and LOS (los_check)
;   +5  attack timer  steps from the start of an attack to the hit (25 = 2.5 s since M2.9)
;   +6  wake radius   cells (Chebyshev): farther enemies are idle; nearer ones wake with LOS and chase
;   +7  flags         bit0 floating (reserved, no code yet) bit1 ranged bit2 melee bit3 boss (reserved)
;   +8  base sprite   spr_table id of walk A (walk B = +1, attack = +2, dead = +3)
;   +9  ink           ink << 4 for the window attribute cells (attr.asm adds BRIGHT; 0 = colours nothing)
;   +10..+15 spare    (zero)
; Rows 1 (imp) and 2 (zombie) = the numbers that were hard-wired before lane G (game_e.asm cp 10 / cp 25 / dmg 10 / 15,
; game_f.asm step 15, sprites.asm ld a,30, sprites_b.asm THSPR 0 / 4, lowcode.asm INKTAB 30h / 40h). Rows 3..6 are
; PLACEHOLDERS copied from row 2 (docs/enemies_v1.md, lane E, did not exist at 14:20Z on 5 Nov) with their own sprite ids
; 18 / 22 / 26 / 30 (ids 18..21 exist in spr_table as copies of the zombie frames; 22.. do not exist yet: no shipped level
; places types 4..6, and the 128K build fills them from its sprite cache later).
; Ranged attack (flags bit 1, game_e.asm et_ranged): in range with LOS the enemy stands and counts the attack timer; when it
; fires: snd 8, damage (shield first), snd 4, and the attack frame (state 2) is shown for 5 steps; then it re-aims or chases.
; It is dead code for types 1 / 2 (bit 1 clear): their timing is byte-for-byte the pre-G one (tools/test_game_replay.py).

; et_attack / e_hurt (from game_e.asm enemy_think, adjacent < 0.7 cell): moved here from game_e.asm by lane G.
et_attack:
        call etab_row          ; IY -> ETAB row of (ix+0) (callable with IX alone: tools/test_game_hud.py enters here)
        ld (ix+5),2
        ld a,(ix+7)
        inc a
        ld (ix+7),a
        cp (iy+5)
        ret c
        ld (ix+7),0
        ld a,8
        call snd_fx
        ld c,(iy+2)            ; melee damage
; e_hurt: C = damage to the player: the shield absorbs it while it lasts (M2.2), then health; snd 4.
e_hurt: ld a,(shield)
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
; et_ranged (from game_e.asm enemy_think): IX -> thing, IY -> its ETAB row; flags bit 1 set, 0 < dist <= range, LOS.
; The enemy stands still. (ix+7) counts: below the attack timer it aims in the chase pose (state 1); at the timer value it
; fires: snd 8, ranged dmg through the shield then health, snd 4 (game_e.asm e_hurt) and shows the attack frame (state 2);
; 5 steps later the timer restarts and the pose returns to chase (it re-aims while still in range with LOS, else chases:
; et_chase resets the timer). ~40 B.
et_ranged:
        ld a,(ix+7)
        inc a
        ld (ix+7),a
        cp (iy+5)
        jr nc,er_hot
        ld (ix+5),1            ; aiming: standing in the chase pose
        ret
er_hot: jr z,er_fire
        sub (iy+5)
        cp 5
        ret c                  ; attack frame held for 5 steps
        ld (ix+7),0
        ld (ix+5),1
        ret
er_fire:
        ld (ix+5),2
        ld a,8
        call snd_fx
        ld c,(iy+3)            ; ranged damage
        jp e_hurt

        defs 0FF70h-$          ; ETAB + ITSPR + ITINK = 128 B at 0FF70h..0FFEFh (kea48.asm org 0FF01h; code above must fit;
                               ; the image must end below 0FFFFh: pasmo's TAP length wraps to 0 at the 64K limit)
ETAB:                          ;  hp step mel rng rrg tim wak flg spr ink  spare
        defb  0,  0,  0,  0,  0,  0,  0,  0,  0,   0,  0,0,0,0,0,0   ; 0 none
        defb 30, 15, 10,  0,  0, 25, 10,  4,  0, 30h,  0,0,0,0,0,0   ; 1 imp (magenta)
        defb 30, 15, 15,  0,  0, 25, 10,  4,  4, 40h,  0,0,0,0,0,0   ; 2 zombie (green)
        defb 30, 15, 15,  0,  0, 25, 10,  4, 18, 40h,  0,0,0,0,0,0   ; 3 shotgunner PLACEHOLDER = zombie row, sprites 18..21
        defb 30, 15, 15,  0,  0, 25, 10,  4, 22, 40h,  0,0,0,0,0,0   ; 4 floater    PLACEHOLDER (128K/Next; sprite cache)
        defb 30, 15, 15,  0,  0, 25, 10,  4, 26, 40h,  0,0,0,0,0,0   ; 5 brute      PLACEHOLDER
        defb 30, 15, 15,  0,  0, 25, 10,  4, 30, 40h,  0,0,0,0,0,0   ; 6 boss       PLACEHOLDER
ITSPR:  defb 8,9,10,11,8,12,13,13      ; item types 16..23 -> sprite id (health, ammo, red key, blue key, shield, barrel, lamp, lamp)
ITINK:  defb 20h,60h,20h,10h,50h,0,0,0 ; item types 16..23 -> ink << 4 (red, yellow, red, blue, cyan, none, none, none)
                               ; (the old THSPR / INKTAB tails; entries 0..15 of those tables came from ETAB rows 1..6 /
                               ; were never looked up: types 7..15 do not exist)
etab_end:
