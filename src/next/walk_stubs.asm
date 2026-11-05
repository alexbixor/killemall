; walk_stubs.asm - lane D1 test stubs for lane D2's drawer entry points (spec section 10).
; Instead of drawing, each call appends one record to the log at LOG_BASE (walk_vars.inc) and bumps LOG_COUNT:
;   1 = piece (c, ra, count, tex, s, u, v lo, v hi, dv lo, dv hi)   = the 10 contiguous bytes pc_c..pc_dv+1
;   2 = plane (c, h, tex, a, b)                                       = the 5 bytes pl_c..pl_b
;   3 = void  (c, a, b)                                               = the 3 bytes vd_c..vd_b
; LOG_ON = 0 makes every stub return at once (used for the timing frames). Registers: destroys A, BC, DE, HL (allowed by
; section 10). planes_reset / planes_flush do nothing here (the wrapper resets the log itself).

planes_reset:
        ret
planes_flush:
        ret

draw_piece:
        ld a,(LOG_ON)
        or a
        ret z
        ld a,1
        ld b,10
        ld hl,pc_c
        jr log_rec
plane_add:
        ld a,(LOG_ON)
        or a
        ret z
        ld a,2
        ld b,5
        ld hl,pl_c
        jr log_rec
void_fill:
        ld a,(LOG_ON)
        or a
        ret z
        ld a,3
        ld b,3
        ld hl,vd_c
log_rec:                        ; A = record type, B = payload length, HL = payload source
        ld c,a
        ld de,(LOG_COUNT)
        inc de
        ld (LOG_COUNT),de
        ld de,(LOG_PTR)
        ld a,d
        cp LOG_END / 256
        ret nc                  ; log full: count it, drop the bytes
        ld a,c
        ld (de),a
        inc de
        ld c,b
        ld b,0
        ldir
        ld (LOG_PTR),de
        ret
