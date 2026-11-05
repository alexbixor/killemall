; fe_test_main.asm - standalone test build of the T2 front end (tools/fe_build.sh -> build/fe_test.tap, autostart).
; Dark screen with a placeholder title in the top rows, then fe_run; on START it prints the five option bytes (row 16,
; "OPT " + 10 hex digits) and the 16 in_keys bytes (row 18, 32 hex digits) so tools/test_frontend.py and tools/fe_shot.py
; can read them back from screen memory, waits for a key and shows the menu again. Includes state.asm (T1), input.asm + frontend.asm (T2), fe_stubs.asm (T2).
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
        call cls
        ld hl,txt_title
        ld de,16384+32*4+6     ; row 4, column 6
        call fe_print
        ld hl,txt_sub
        ld de,16384+32*6+4
        call fe_print
main:   call fe_run
        call fe_clr_bottom
        ld hl,txt_opt
        ld de,0x5000           ; row 16
        call fe_print
        ld hl,opt_music
        ld b,4                 ; opt_music opt_sfx opt_detail opt_joy (M2.2: opt_fps gone)
        call hexrun
        ld hl,txt_keys
        ld de,0x5020           ; row 17
        call fe_print
        ld hl,in_keys
        ld de,0x5040           ; row 18: 32 hex digits
        ld b,16
        call hexrun
        ld hl,txt_any
        ld de,0x5080           ; row 20
        call fe_print
        call in_wait_key
        jp main

hexrun: ld a,(hl)              ; B bytes at HL as hex at DE
        inc hl
        push hl
        push bc
        call prhex
        pop bc
        pop hl
        djnz hexrun
        ret
prhex:  push af
        rra
        rra
        rra
        rra
        call prnib
        pop af
prnib:  and 15
        add a,'0'
        cp '9'+1
        jr c,pn1
        add a,7
pn1:    ld (hexbuf),a
        ld hl,hexbuf
        jp fe_print
hexbuf: defb 0,0

isr:    push hl
        ld hl,(ticks)
        inc hl
        ld (ticks),hl
        pop hl
        ei
        reti

cls:    ld hl,16384
        ld de,16385
        ld bc,6143
        ld (hl),0
        ldir
        ld hl,22528
        ld de,22529
        ld bc,767
        ld (hl),7
        ldir
        ret

txt_title: defb "KILL'EM ALL - T2 MENU TEST",0
txt_sub:   defb "(title screen lives in rows 0-15)",0
txt_opt:   defb "OPT ",0
txt_keys:  defb "KEYS ",0
txt_any:   defb "ANY KEY = MENU AGAIN",0
ticks:     defw 0
frames:    defw 0

        include "src/common/state.asm"
        include "src/common/input.asm"
        include "src/common/frontend.asm"
        include "tools/fe_stubs.asm"
        end start
