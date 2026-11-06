; flip_hi.asm - lane F (6 Nov 2026, 128K only, pasmo --equ FLIP=1). Bank-0 half of the shadow-screen flip: included by
; kea48.asm right before `hi_end equ $` (the gap below the stack top / TABLE), so it runs only with bank 0 paged. The
; fixed-area half (paging primitives, fl_ldir / fl_cb / fl_ca copy stubs, fl_init, fl_hud, fl_show0, variables) is
; shim128.asm: the hi_end gap is ~110 B, so only fl_wait + fl_frame live here (56 B).
; Rules F1..F7: shim128.asm header.
        IF DEFINED FLIP
; ---- fl_wait: block until no display switch is pending (snd_isr applies it at the next 50 Hz tick). A frame takes
; >= 7 ticks on the 128K, so this never waits there; it protects the Next (28 MHz) and the test harness.
fl_wait:
        ld a,(fl_req)
        or a
        ret z
        halt
        jr fl_wait
; ---- fl_frame: tail of render (kea48.asm FLIP form: `jp fl_frame` replaces `call COPYBUF / jp attr_write`).
; Interrupts on, bank 0 paged. Draws the whole frame into the HIDDEN screen, then asks the ISR to show it:
;  1. fl_wait             2. hidden screen = the one BANKM bit 3 does not show: cb_hi = C0h (bank 7) / 40h (screen 0)
;  3. HUD rows changed? -> fl_hud mirrors screen 0 rows 104..191 + attribute rows 13..23 into bank 7 (rule F6)
;  4. fl_cb: COPYBUF into the hidden pixel window (bank 7 paged)
;  5. attr_write: 288 cells into the BUF staging window (bank 0)   6. fl_ca: staging -> hidden attribute window (bank 7)
;  7. fl_req = BANKM xor 08h (rule F3: snd_isr switches at the next interrupt)
fl_frame:
        call fl_wait
        ld a,(BANKM)           ; 10h (screen 0 shown) / 18h (bank 7 shown): bank bits 0 (bank 0 paged here), bits 5..7 0
        add a,a
        add a,a
        add a,a
        add a,a                ; 00h / 80h
        xor 0C0h               ; C0h = write bank 7 (hidden while screen 0 is shown) / 40h = write screen 0
        ld (cb_hi),a
        ld a,(hud_dirty)
        or a
        call nz,fl_hud
        call fl_cb
        call attr_write
        ld a,(cb_hi)
        add a,018h             ; D8h / 58h: the hidden screen's attribute area
        ld d,a
        call fl_ca
        ld a,(BANKM)
        xor 08h
        ld (fl_req),a
        ret
        ENDIF
