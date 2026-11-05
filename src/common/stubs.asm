; stubs.asm - T1 local stand-ins for T2/T3 labels (replaced at integration). Same labels/contracts as ARCH_M2.md.
; in_read: A = action bits b0 fwd b1 back b2 left b3 right b4 fire b5 use b6 strafe L b7 strafe R; honours in_keys.
in_read:
        push bc
        push hl
        ld hl,in_keys+15
        ld e,0
        ld d,8
ir_l:   ld a,(hl)              ; mask
        dec hl
        ld b,(hl)              ; port high byte
        dec hl
        ld c,254
        ld c,a
        push bc
        ld c,254
        in a,(c)
        pop bc
        cpl
        and c
        add a,255              ; carry = pressed
        rl e
        dec d
        jr nz,ir_l
        ld a,127               ; BREAK = CAPS (FE b0) + SPACE (7F b0)
        in a,(254)
        ld b,a
        ld a,254
        in a,(254)
        or b
        cpl
        and 1
        ld (in_break),a
        ld a,e
        pop hl
        pop bc
        ret
in_keys:
        defb 251,1             ; Q
        defb 253,1             ; A
        defb 223,2             ; O
        defb 223,1             ; P
        defb 127,4             ; M
        defb 127,1             ; SPACE
        defb 254,2             ; Z
        defb 254,4             ; X
fe_run:     ret
fe_message: jp hud_message
