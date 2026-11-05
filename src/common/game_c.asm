; game_c.asm (T1) - pickups, level clear, death, restart; fire (hitscan) and enemy AI are in game_d.asm.
; pickups: any item thing (type >= 16) within 0.5 cell (Chebyshev on 8.8) of the player is collected.
pickups:
        ld ix,things
        ld b,NTHINGS
pk_l:   ld a,(ix+0)
        cp 16
        jr c,pk_next
        cp 21
        jr nc,pk_next          ; barrel / lamp are decor
        call near_player
        jr nc,pk_next
        call pickup_item
pk_next:
        ld de,8
        add ix,de
        djnz pk_l
        ret
; near_player: IX -> thing; carry set when |dx| < 0.5 and |dy| < 0.5 cell (word + 128 has a zero high byte)
near_player:
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(posx)
        or a
        sbc hl,de
        ld de,128
        add hl,de
        ld a,h
        or a
        ret nz                 ; NC: far
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(posy)
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
        ld a,(health)
        add a,25
        cp 101
        jr c,$+4
        ld a,100
        ld (health),a
        ld hl,msg_health
        jr pi_done
pi1:    cp 17
        jr nz,pi2
        ld a,(ammo)
        add a,20
        cp 100
        jr c,$+4
        ld a,99
        ld (ammo),a
        ld hl,msg_ammo
        jr pi_done
pi2:    cp 20
        jr nz,pi3
        ld a,(shield)          ; M2.2: 20 = shield pickup (+50, cap 100)
        add a,50
        cp 101
        jr c,$+4
        ld a,100
        ld (shield),a
        ld hl,msg_shield
        jr pi_done
pi3:    sub 17                 ; 18 -> 1 red, 19 -> 2 blue
        ld c,a
        ld hl,keys
        or (hl)
        ld (hl),a
        ld hl,msg_keyr
        bit 1,c
        jr z,pi_done
        ld hl,msg_keyb
pi_done:
        call hud_message
        ld a,3
        jp snd_fx
msg_health: defb "HEALTH +25",0
msg_ammo:   defb "AMMO +20",0
msg_keyr:   defb "RED KEY",0
msg_keyb:   defb "BLUE KEY",0
msg_shield: defb "SHIELD +50",0
