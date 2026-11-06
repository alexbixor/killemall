; shim128.asm - Kill'em all 128K (lane T4). Pulled into the engine image by tools/make128.py (replaces beeper.asm; it is
; included right before the `isr:` label so it assembles below 49152 and stays mapped while bank 1 is paged in).
; Bank 1 (build/bank1.bin = src/128k/bank1.asm) holds the AY player + music + level images and is paged at 49152 only
; between PAGEN 1 and PAGEN 0 below; bank 0 (engine code/data above 49152, stack, IM2 table) is paged everywhere else.
; Rules: paging is INLINE (never a call/ret across a page switch); only bits 0..2 of port 7FFDh change, bits 3..5 come
; from BANKM (23388) which is kept updated; every call made after PAGEN 1 returns before PAGEN 0, so pushes and pops
; always hit the same bank (the stack at 65008 lies in the paged window); main-loop wrappers run under DI, snd_isr is
; called from the engine ISR which already runs with interrupts off.
;
; Lane F (5/6 Nov 2026, pasmo --equ FLIP=1, 128K only): shadow-screen flip. The rules above change as follows - lane P2
; must keep these (tools/test_flip.py proves them on the real image):
;  F1 7FFDh is always derived from BANKM (23388) - the ONLY exception is bank_init (fixed 10h: BANKM is garbage at start).
;     fl_pg7 / fl_pg0 (main context) switch bank 7 / bank 0 in at C000h and UPDATE BANKM (display latch bit 3 kept).
;     fl_pg1 / fl_pgb (transient bank-1 excursions: snd_isr, snd_call, load_level) do NOT touch BANKM: fl_pg1 pages
;     bank 1 keeping the latch, fl_pgb writes BANKM back to the port = the bank AND the latch that were interrupted.
;  F2 the stack lives in the fixed area (kea48.asm FSTACK = 5D00h, grows down over 5Cxxh): a call/ret across a page
;     switch is legal and ISR pushes never land in a paged bank. Bank 7 carries a mirror of the IM2 table + ISRVEC
;     (fl_init, kea48.asm start), so an interrupt during a bank-7 phase reaches isr. Nothing writes bank 7 above DAFFh.
;  F3 the display switch happens only in snd_isr (= in the vertical blank): main code writes the wanted 7FFDh byte
;     (10h screen 0 / 18h bank 7) into fl_req; snd_isr copies it into BANKM, the fl_pg1 `out` that follows applies it,
;     fl_req := 0. A request is only ever pending while bank 0 is paged (fl_frame / fl_show0 drain it first).
;  F4 cb_hi = destination high byte of COPYBUF (gen48.py FLIP form: 40h screen 0, C0h bank 7), set by fl_frame for the
;     HIDDEN screen. attr_write (attr.asm FLIP form) stages its 288 cells contiguously in BUF (free after COPYBUF) with
;     bank 0 paged; fl_ca copies them into the hidden screen's attribute window with bank 7 paged.
;  F5 snd_isr forwards opt_music / opt_sfx (bank-0 variables) to bank 1 only when it interrupted bank 0 (BANKM bits
;     0..2 = 0); when it interrupted a bank-7 phase the copies forwarded by the previous tick stay.
;  F6 hud_dirty <> 0 (hud.asm: print_char, keys_draw, hud_init set it = every HUD pixel writer) -> fl_hud copies pixel
;     rows 104..191 + attribute rows 13..23 of screen 0 (where the HUD code draws) into bank 7 before the switch is
;     requested, then clears it. Static HUD = copied once; a HUD change = one extra 3.1 KB copy (~66k T) that frame.
;  F7 every exit from the frame loop (pause menu, menu, level clear / death message wait) calls fl_show0 first: screen 0
;     displayed, request drained, so front end / menu / messages draw into the displayed screen as on the 48K.
;  Code placement (the fixed area below COLBASE has ~9 B of slack: every byte added there moves COLBASE, see F_LAYOUT):
;     fixed (this file):  paging primitives, the bank-7 copy stubs, fl_init, variables; the tape loader (dead on the
;                         128K), the beeper knob and 6 inline PAGEN expansions are dropped under FLIP to pay for them.
;     bank 0 (flip_hi.asm, hi_end gap, 110 B): fl_wait + fl_frame - run with bank 0 paged.
BANKM     equ 23388
B1_ISR    equ 49152+0          ; bank-1 fixed table (bank1.asm): jp snd_isr
B1_FX     equ 49152+3          ; jp snd_fx      A = 1..10
B1_MUSIC  equ 49152+6          ; jp snd_music   A = 0/1/2
B1_LEVTAB equ 49152+9          ; dw lev0, lev1, lev2 (1081-byte level_data images, byte 0 = id 1..3)
B1_OPTM   equ 49152+15         ; opt_music / opt_sfx copies read by the bank-1 player
B1_OPTS   equ 49152+16
LEVEL_BLK equ 1081

PAGEN   macro n                ; 7FFDh = 10h + n: ROM 1 (48K ROM font used by print), screen 0, bank n; BANKM updated.
        ld a,010h+n            ; fixed value on purpose: under ZEsarUX's 128K autoload BANKM read 00h while 7FFDh was 10h,
        ld (BANKM),a           ; so deriving bits 3..5 from BANKM paged ROM 0 in (probe build/dbg128.out). Destroys A, BC.
        ld bc,07FFDh           ; Lane F: used by bank_init only; everything else derives the byte from BANKM (rule F1).
        out (c),a
        endm

bank_init:                     ; first instruction of start: bank 0 at 49152, BANKM consistent (= 10h: screen 0 shown)
        PAGEN 0
        ret

        IF DEFINED FLIP
        ELSE
mt_outer:  defb 0              ; beeper knob written by kea48.asm (no beeper on the 128K)
        ENDIF
snd_menu_tick:
        ret                    ; menu music comes from the AY (snd_music 1 in the engine's menu)

snd_isr:                       ; from the engine ISR (interrupts already off): tick the player in bank 1
        push af
        push bc
        push de
        push hl
        IF DEFINED FLIP
        ld a,(fl_req)          ; rule F3: a pending display switch is applied here, in the vertical blank: BANKM takes the
        or a                   ; wanted byte (bank bits 0: a request is only pending with bank 0 paged), the fl_pg1 `out`
        jr z,si_n              ; below writes it to the port together with bank 1, fl_pgb restores it with bank 0
        ld (BANKM),a
        xor a
        ld (fl_req),a
si_n:
        ENDIF
        ld a,(opt_music)
        ld e,a
        ld a,(opt_sfx)
        ld h,a
        IF DEFINED FLIP
        call fl_pg1
        ld a,(BANKM)           ; rule F5: opt_* live in bank 0 - with a bank-7 phase interrupted they were not readable,
        and 07h                ; so the copies forwarded by the previous tick stay
        jr nz,si_go
        ELSE
        PAGEN 1
        ENDIF
        ld a,e
        ld (B1_OPTM),a
        ld a,h
        ld (B1_OPTS),a
si_go:  call B1_ISR
        IF DEFINED FLIP
        call fl_pgb            ; rule F1: back to the interrupted bank, display latch as BANKM says
        ELSE
        PAGEN 0
        ENDIF
        pop hl
        pop de
        pop bc
        pop af
        ret

        IF DEFINED FLIP
fl_req:  defb 0                ; wanted 7FFDh value (10h / 18h) or 0 = nothing pending (fl_frame/fl_show0 write, snd_isr clears)
cb_hi:   defb 040h             ; COPYBUF destination high byte: 40h screen 0, C0h bank 7 (fl_frame sets it per frame)
hud_dirty: defb 1              ; <> 0: a HUD routine drew into screen 0 since the last fl_hud (rule F6); 1 = copy at start
; ---- paging primitives (rule F2: the stack is in the fixed area, so these may be CALLed). Destroy A, BC; A = port byte.
fl_pg7: ld a,(BANKM)           ; main context: bank 7 at C000h, latch kept, BANKM updated (an ISR between the two writes
        or 07h                 ; sees BANKM = bank 7 with bank 0 still paged: it skips opt forwarding and restores bank 7,
        ld (BANKM),a           ; which the `out` below asserts again - consistent either way)
        ld bc,07FFDh
        out (c),a
        ret
fl_pg0: ld a,(BANKM)           ; main context: bank 0 back, latch kept. Port first, BANKM second, port again: an ISR between
        and 0F8h               ; them sees BANKM = bank 7 (skips opt forwarding) and restores bank 7; the second `out`
        ld bc,07FFDh           ; puts bank 0 back, so port and BANKM agree whenever an interrupt cannot be in flight
        out (c),a
        ld (BANKM),a
        out (c),a
        ret
fl_pg1: ld a,(BANKM)           ; transient: bank 1 at C000h, latch kept, BANKM untouched (callers run with DI or are the ISR)
        and 0F8h
        or 01h
        ld bc,07FFDh
        out (c),a
        ret
fl_pgb: ld a,(BANKM)           ; transient excursion over: whatever BANKM says (bank 0 or 7 + latch) back on the port
        ld bc,07FFDh
        out (c),a
        ret
; ---- bank-7 copy stubs: page bank 7, copy, page bank 0 (interrupts may stay on: rule F2). Called from bank-0 code.
fl_ldir:                       ; HL -> DE, BC bytes, destination in bank 7 (fl_init table mirror, fl_hud)
        push bc
        call fl_pg7
        pop bc
        ldir
        jp fl_pg0
fl_init:                       ; start (kea48.asm, DI): IM2 table + ISRVEC (0FDFDh..0FF00h, 260 B) mirrored into bank 7.
        ld hl,ISRVEC           ; bank 7 shares the addresses, so the block goes through BUF (fixed RAM, dead at start):
        ld de,BUF              ; bank 0 -> BUF with bank 0 paged, then BUF -> bank 7 with bank 7 paged (fl_ldir)
        ld bc,TABLE+256+1-ISRVEC
        push bc
        ldir
        pop bc
        ld hl,BUF
        ld de,ISRVEC
        jr fl_ldir
fl_cb:  call fl_pg7            ; COPYBUF (fixed code) into the hidden screen selected by cb_hi
        call COPYBUF
        jp fl_pg0
fl_ca:  call fl_pg7            ; D = hidden screen's attribute high byte (58h / D8h): the 12 x 24 cells staged by
        ld e,024h              ; attr_write at ATTRWIN = BUF+24h (same low bytes, stride 32) -> row 1, column 4 of that
        ld hl,ATTRWIN          ; screen. Both pointers advance 24 by ldir + 8 here = 32 per row.
        ld a,12
fca_l:  ld bc,24
        ldir
        ld c,8                 ; B = 0 after ldir
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        dec a
        jr nz,fca_l
        jp fl_pg0
; ---- fl_hud (fixed area: the hi_end gap could not hold it): screen 0 pixel rows 104..191 (4D00h..57FFh, 2816 B) -> bank 7 CD00h..D7FFh and screen 0 attribute rows
; 13..23 (59A0h..5AFFh, 352 B) -> bank 7 D9A0h..DAFFh; hud_dirty := 0. Interrupts on (rule F2). Destroys AF BC DE HL.
fl_hud:
        xor a
        ld (hud_dirty),a
        ld hl,04D00h
        ld de,0CD00h
        ld bc,00B00h
        call fl_ldir
        ld hl,059A0h
        ld de,0D9A0h
        ld bc,0160h
        jp fl_ldir
; ---- fl_show0 (fixed area): rule F7. Called (interrupts on, bank 0 paged) before anything draws for the user outside the frame
; loop: screen 0 displayed, request drained, cb_hi back to screen 0. Idempotent; costs <= 2 ticks when a switch was pending.
fl_show0:
        call fl_wait
        ld a,040h
        ld (cb_hi),a
        ld a,(BANKM)
        and 08h
        ret z                  ; screen 0 already displayed
        ld a,010h
        ld (fl_req),a
        jp fl_wait
        ENDIF

snd_fx:                        ; A = SFX id 1..10 (enqueue; the ISR plays it). Destroys AF, HL.
        ld l,B1_FX and 255
        jr snd_call
snd_music:                     ; A = 0 stop, 1 menu, 2 game. Destroys AF, HL.
        ld l,B1_MUSIC and 255
snd_call:                      ; L = low byte of the bank-1 entry (high byte C0h). NOTHING is pushed/popped across the
        di                     ; page switch (the stack lies in the paged window): all state travels in D E H L.
        push bc                ; (lane F: with FSTACK in the fixed area that rule is moot, the structure is kept.)
        push de
        ld d,a                 ; D = argument
        ld a,(opt_music)
        ld e,a
        ld a,(opt_sfx)
        ld h,a
        IF DEFINED FLIP
        call fl_pg1
        ELSE
        PAGEN 1
        ENDIF
        ld a,e
        ld (B1_OPTM),a
        ld a,h
        ld (B1_OPTS),a
        ld h,B1_FX/256
        ld a,d
        call snd_jp            ; into bank 1; returns here with bank 1 still paged (call/ret both in bank 1)
        IF DEFINED FLIP
        call fl_pgb
        ELSE
        PAGEN 0
        ENDIF
        pop de
        pop bc
        ei
        ret
snd_jp: jp (hl)

; load_level: A = level id 1..3 -> copy that level image from bank 1 over the engine's level_data slot (1081 bytes).
; Replaces T6's tape load_level (make128.py renames the tape routine to load_level_tape). Destroys AF BC DE HL.
load_level:
        di
        dec a
        add a,a
        ld hl,B1_LEVTAB
        add a,l
        ld l,a
        IF DEFINED FLIP
        call fl_pg1
        ELSE
        PAGEN 1
        ENDIF
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                 ; HL = level image in bank 1
        ld de,level_data
        ld bc,LEVEL_BLK
        ldir
        IF DEFINED FLIP
        call fl_pgb
        ELSE
        PAGEN 0
        ENDIF
        ei
        ret
