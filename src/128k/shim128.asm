; shim128.asm - Kill'em all 128K (lane T4). Pulled into the engine image by tools/make128.py (replaces beeper.asm; it is
; included right before the `isr:` label so it assembles below 49152 and stays mapped while bank 1 is paged in).
; Bank 1 (build/bank1.bin = src/128k/bank1.asm) holds the AY player + music + level images and is paged at 49152 only
; between PAGEN 1 and PAGEN 0 below; bank 0 (engine code/data above 49152, stack, IM2 table) is paged everywhere else.
; Rules: paging is INLINE (never a call/ret across a page switch); only bits 0..2 of port 7FFDh change, bits 3..5 come
; from BANKM (23388) which is kept updated; every call made after PAGEN 1 returns before PAGEN 0, so pushes and pops
; always hit the same bank (the stack at 65008 lies in the paged window); main-loop wrappers run under DI, snd_isr is
; called from the engine ISR which already runs with interrupts off.
BANKM     equ 23388
B1_ISR    equ 49152+0          ; bank-1 fixed table (bank1.asm): jp snd_isr
B1_FX     equ 49152+3          ; jp snd_fx      A = 1..10
B1_MUSIC  equ 49152+6          ; jp snd_music   A = 0/1/2
B1_LEVTAB equ 49152+9          ; dw lev0, lev1, lev2 (1081-byte level_data images, byte 0 = id 1..3)
B1_OPTM   equ 49152+15         ; opt_music / opt_sfx copies read by the bank-1 player
B1_OPTS   equ 49152+16
LEVEL_BLK equ 1081

PAGEN   macro n                ; 7FFDh = 10h + n: ROM 1 (48K ROM font used by print), screen 0, bank n; BANKM updated.
        ld a,010h+n            ; fixed value on purpose: under ZEsarUX's 128K autoload BANKM read 00h while 7FFDh was 11h,
        ld (BANKM),a           ; so deriving bits 3..5 from BANKM paged ROM 0 in (probe build/dbg128.out). Destroys A, BC.
        ld bc,07FFDh
        out (c),a
        endm

bank_init:                     ; first instruction of start: bank 0 at 49152, BANKM consistent
        PAGEN 0
        ret

mt_outer:  defb 0              ; beeper knob written by kea48.asm (no beeper on the 128K)
snd_menu_tick:
        ret                    ; menu music comes from the AY (snd_music 1 in the engine's menu)

snd_isr:                       ; from the engine ISR (interrupts already off): tick the player in bank 1
        push af
        push bc
        push de
        push hl
        ld a,(opt_music)
        ld e,a
        ld a,(opt_sfx)
        ld h,a
        PAGEN 1
        ld a,e
        ld (B1_OPTM),a
        ld a,h
        ld (B1_OPTS),a
        call B1_ISR
        PAGEN 0
        pop hl
        pop de
        pop bc
        pop af
        ret

snd_fx:                        ; A = SFX id 1..10 (enqueue; the ISR plays it). Destroys AF, HL.
        ld l,B1_FX and 255
        jr snd_call
snd_music:                     ; A = 0 stop, 1 menu, 2 game. Destroys AF, HL.
        ld l,B1_MUSIC and 255
snd_call:                      ; L = low byte of the bank-1 entry (high byte C0h). NOTHING is pushed/popped across the
        di                     ; page switch (the stack lies in the paged window): all state travels in D E H L.
        push bc
        push de
        ld d,a                 ; D = argument
        ld a,(opt_music)
        ld e,a
        ld a,(opt_sfx)
        ld h,a
        PAGEN 1
        ld a,e
        ld (B1_OPTM),a
        ld a,h
        ld (B1_OPTS),a
        ld h,B1_FX/256
        ld a,d
        call snd_jp            ; into bank 1; returns here with bank 1 still paged (call/ret both in bank 1)
        PAGEN 0
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
        PAGEN 1
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                 ; HL = level image in bank 1
        ld de,level_data
        ld bc,LEVEL_BLK
        ldir
        PAGEN 0
        ei
        ret
