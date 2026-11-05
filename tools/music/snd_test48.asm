; snd_test48.asm - T3 standalone 48K sound test: plays SFX 1..10 in sequence, then loops the menu tune.
; Keys while the tune plays: 1..9, 0 = SFX 1..10 (tune keeps running). Build: tools/snd_build.sh -> build/snd_test48.tap
; Also the host program for tools/test_sound.py (labels snd_fx / snd_menu_tick / snd_music / opt_* come from beeper.asm).
        org 32768
ISRVEC  equ 65021
TABLE   equ 65024

start:  di
        ld sp,65008
        ld hl,TABLE
        ld de,TABLE+1
        ld bc,256
        ld (hl),253
        ldir
        ld a,195
        ld (ISRVEC),a
        ld hl,isr
        ld (ISRVEC+1),hl
        ld a,254
        ld i,a
        im 2
        ei
        ld hl,22528             ; attributes: white ink on black, show a progress bar of SFX played
        ld de,22529
        ld bc,767
        ld (hl),7
        ldir
        ld a,1
        ld (opt_sfx),a
        ld (opt_music),a
        ld b,10
        ld c,1
demo_sfx:
        push bc
        ld a,c
        call snd_fx
        pop bc
        push bc
        ld a,c                  ; paint one attribute cell per SFX played (row 0)
        add a,22527
        ld l,a
        ld h,88
        ld (hl),070h
        ld b,25                 ; ~0.5 s pause between effects
        call wait_frames
        pop bc
        inc c
        djnz demo_sfx
        ld a,1
        call snd_music          ; start the menu tune
main:   halt
        call snd_menu_tick
        call keys               ; A = SFX id or 0
        or a
        jr z,main
        call snd_fx
        ld b,8
        call wait_frames        ; debounce
        jr main

wait_frames:                    ; B = frames; keeps the tune ticking if it is playing
        halt
        call snd_menu_tick
        djnz wait_frames
        ret

keys:   ld bc,0F7FEh            ; 1 2 3 4 5
        in a,(c)
        ld e,1
        call key_row
        ret nz
        ld bc,0EFFEh            ; 0 9 8 7 6
        in a,(c)
        cpl
        and 31
        ret z
        ld e,10
key_r2: rra
        ret c
        dec e
        jr key_r2
key_row:                        ; A = port byte (bits 0..4 active low), E = id of bit 0; returns A = id (nz) or 0 (z)
        cpl
        and 31
        ret z
key_r1: rra
        jr c,key_hit
        inc e
        jr key_r1
key_hit:
        ld a,e
        or a
        ret

isr:    push hl
        ld hl,(ticks)
        inc hl
        ld (ticks),hl
        pop hl
        ei
        reti

ticks:  dw 0
opt_sfx:
        db 1
opt_music:
        db 1

        include "../../src/common/beeper.asm"
fin:
        end start
