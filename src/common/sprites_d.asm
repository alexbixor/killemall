; sprites_d.asm (T1) - vis list insert (sorted far -> near, ascending hv). Drawing loop in sprites_e.asm.
; vis_add: thv/tc0/tnc set, IX -> thing. Sprite id = THSPR[type] (+ anim/state for enemies). Cap hv at 128 (CPU bound).
vis_add:
        ld a,(nvis)
        cp VISMAX
        ret nc
        ld a,(ix+0)
        ld c,a
        ld b,0
        ld hl,THSPR
        add hl,bc
        ld a,(hl)
        bit 4,c
        jr nz,va_id            ; item: fixed sprite
        ld c,a
        ld a,(ix+5)            ; state 0 idle 1 chase 2 attack 3 dead
        cp 2
        jr c,va_walk
        add a,c                ; 2 attack, 3 dead
        jr va_id
va_walk:
        or a
        ld a,c
        jr z,va_id             ; idle: walk A
        ld a,(ticks)           ; M2.9: time-based (bit 4 of the 50 Hz counter), the same on every machine
        rrca
        rrca
        rrca
        rrca
        and 1
        add a,c                ; chase: walk A/B every 16 ticks = 0.32 s (was every 4 rendered frames)
va_id:  add a,a
        ld l,a
        ld h,0
        ld de,spr_table
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)              ; DE = sprite column table
        ld a,(thv)
        cp 129
        jr c,$+4
        ld a,128
        ld (thv),a
; insertion point: first entry with hv > thv; C = entries to shift up
        ld hl,vis
        ld a,(nvis)
        ld c,a
        or a
        jr z,va_put
va_f:   ld a,(thv)
        cp (hl)
        jr c,va_shift
        ld a,l
        add a,6
        ld l,a
        jr nc,$+3
        inc h
        dec c
        jr nz,va_f
        jr va_put
va_shift:
        push hl
        push de
        ld a,c
        add a,a
        add a,c
        add a,a                ; A = 6*C
        ld c,a
        ld b,0
        ld e,a
        ld d,0
        add hl,de
        dec hl                 ; HL = last source byte
        ld e,l
        ld d,h
        ld a,6
        add a,e
        ld e,a
        jr nc,$+3
        inc d                  ; DE = last dest byte
        lddr
        pop de
        pop hl
va_put: ld a,(thv)
        ld (hl),a
        inc hl
        ld a,(tc0)
        ld (hl),a
        inc hl
        ld a,(tnc)
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        push hl
        push ix
        pop hl
        ld de,things
        or a
        sbc hl,de
        ld a,l
        rrca
        rrca
        rrca
        and 31                 ; thing index = (IX - things) / 8
        pop hl
        ld (hl),a
        ld hl,nvis
        inc (hl)
        ret
