; game_a.asm (T1) - game tick = one fixed 0.1 s step since M2.9 (kea48.asm steps): input via in_read contract (b0 fwd b1 back b2 left b3 right b4 fire b5 use b6/b7 strafe L/R), movement.
; Doors/pickups/enemies/weapon hooks are in game_b.asm (milestone B/C); hud in hud.asm (D).
game_tick:
        call in_read
        ld (in_bits),a
        bit 2,a
        jr z,gt1
        ld a,(angle)
        sub 6
        ld (angle),a
gt1:    ld a,(in_bits)
        bit 3,a
        jr z,gt2
        ld a,(angle)
        add a,6
        ld (angle),a
gt2:    ld a,(in_bits)
        bit 0,a
        jr z,gt3
        ld b,38                ; M2.3: floor line phase step when the move lands (0.15 cell = 38/256), forward
        ld a,(angle)
        call move_by
        call bump_action       ; doors auto-open when walked into
gt3:    ld a,(in_bits)
        bit 1,a
        jr z,gt3s
        ld b,256-38            ; M2.3: backward -> lines flow away
        ld a,(angle)
        add a,128
        call move_by
gt3s:   ld a,(in_bits)         ; M2.8 (3 Nov 2026): strafe. Z = b6 slides left = heading - 64 (turn-right P is angle + 6,
        bit 6,a                ; so the right-hand side is + 64 and the left-hand side - 64 = + 192), X = b7 slides right.
        ld a,256-64            ; (ld does not touch the Z flag of the bit test)
        call nz,strafe
        ld a,(in_bits)
        bit 7,a
        ld a,64
        call nz,strafe
gt4:    ld a,(in_bits)
        bit 5,a
        call nz,use_action
        ld a,(in_bits)
        bit 4,a
        call nz,fire_action
        call things_tick
        call pickups
        ld hl,door_cool
        ld a,(hl)
        or a
        jr z,$+3
        dec (hl)
        ld hl,fire_cool
        ld a,(hl)
        or a
        jr z,$+3
        dec (hl)
        cp 7
        jr nz,gt5
        xor a
        ld (weapon_frame),a    ; fire frame shown for 5 frames
gt5:
        ld a,(health)
        or a
        jp z,player_dead
        jp hud_update
in_bits: defb 0
; M2.8 strafe: A = heading offset (64 right / 192 left) -> move_by along angle + A with B = 0: fl_ph counts forward distance
; only, so a sideways slide leaves the floor/ceiling line phase alone. 10 B.
strafe: ld b,0
        ld c,a
        ld a,(angle)
        add a,c
        jp move_by
