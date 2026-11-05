; snd_test128.asm - T3 standalone 128K AY sound test (runs in the plain 48K memory window; no banking).
; Boots: IM2 ISR calls snd_isr every frame; starts the menu track.
; Keys: M = menu track, G = game track, S = stop music, 1..9,0 = SFX 1..10 (on channel C, pre-empting the music).
; Attribute row 0 shows the music state (cell 0: 1 = menu blue, 2 = game red, stop black) and the last SFX (cell 2+id).
; Build: tools/snd_build.sh -> build/snd_test128.tap. Also the host program for the AY half of tools/test_sound.py.
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
        ld hl,22528
        ld de,22529
        ld bc,767
        ld (hl),7
        ldir
        ld a,1
        ld (opt_sfx),a
        ld (opt_music),a
        ei
        ld a,1
        call snd_music
        ld a,9                  ; blue cell = menu track
        ld (22528),a
main:   halt
        call keys               ; A = SFX id 1..10, 11 = M, 12 = G, 13 = S, 0 = nothing
        or a
        jr z,main
        cp 11
        jr c,main_sfx
        sub 10                  ; 1 = M, 2 = G, 3 = S
        cp 3
        jr nz,main_mus
        xor a
main_mus:
        push af
        call snd_music
        pop af
        ld hl,mus_colors
        add a,l
        ld l,a
        ld a,(hl)
        ld (22528),a
        jr main_db
main_sfx:
        push af
        call snd_fx
        pop af
        add a,22529
        ld l,a
        ld h,88
        ld (hl),070h
main_db:
        ld b,8                  ; debounce
main_w: halt
        djnz main_w
        jr main
mus_colors:
        db 0,9,10

keys:   ld bc,0F7FEh            ; 1 2 3 4 5
        in a,(c)
        ld e,1
        call key_row
        ret nz
        ld bc,0EFFEh            ; 0 9 8 7 6
        in a,(c)
        cpl
        and 31
        jr z,keys2
        ld e,10
key_r2: rra
        jr c,key_hit
        dec e
        jr key_r2
keys2:  ld bc,07FFEh            ; SPACE SYM M N B
        in a,(c)
        bit 2,a
        ld a,11
        ret z                   ; M
        ld bc,0FDFEh            ; A S D F G
        in a,(c)
        bit 4,a
        ld a,12
        ret z                   ; G
        ld bc,0FDFEh
        in a,(c)
        bit 1,a
        ld a,13
        ret z                   ; S
        xor a
        ret
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

isr:    push af
        push hl
        ld hl,(ticks)
        inc hl
        ld (ticks),hl
        call snd_isr
        pop hl
        pop af
        ei
        reti

ticks:  dw 0
opt_sfx:
        db 1
opt_music:
        db 1

        include "../../src/128k/ay.asm"
        include "../../src/gen/music_data.asm"
fin:
        end start
