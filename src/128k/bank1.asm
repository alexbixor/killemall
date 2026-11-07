; bank1.asm - Kill'em all 128K (lane T4): everything that lives in RAM BANK 1 (paged at 49152 only while the
; shim in the engine image calls in: see shim128.asm). Assembled standalone: pasmo --bin bank1.asm (cwd src/128k).
; Fixed jump/data table at 49152 (the engine image never needs this file's symbols; test_128.py checks it vs the .sym):
;   +0  jp snd_isr        per-frame tick (AY register writes)
;   +3  jp snd_fx         A = SFX id 1..10 (enqueue)
;   +6  jp snd_music      A = 0 stop / 1 menu / 2 game
; pre-K1 layout (no LEVELS8):
;   +9  dw lev0, lev1, lev2   level images: exact level_data slot layout (tools/mklevelblk.py: id 1..3 + header +
;                          1024 cells + 16 things = LEV_STRIDE = 1081 bytes), so a plain LDIR replaces the slot
;   +15 db opt_music copy  +16 db opt_sfx copy  (the engine's state.asm bytes sit inside the paged window:
;        the shim copies them here right after paging and before calling snd_fx / snd_music / snd_isr)
;   +17 db 3 (level count)   +18 dw LEV_STRIDE   +20 dw bank1_end
; lane K1 (6 Nov 2026, pasmo --equ LEVELS8=1, every 128K build): 8 levels of LEV_STRIDE = 1141 B (36 things) + the low
; code block image (build/lowcode128.bin, src/128k/lowcode128.asm) copied to LOWCODE 5BC0h by b1_load at every load_level:
;   +9  dw lev0..lev7 (16 B, one page)   +25 db opt_music copy   +26 db opt_sfx copy   +27 db 8 (level count)
;   +28 dw LEV_STRIDE   +30 dw bank1_end   +32 jp b1_load (H = level id 1..8, DE = level_data)   table = 48 B
        org 49152
        include "gen/lev128_sizes.asm"
B1_TABLE:
        jp snd_isr
        jp snd_fx
        jp snd_music
        IF DEFINED LEVELS8
levtab: dw lev0
        dw lev1
        dw lev2
        dw lev3
        dw lev4
        dw lev5
        dw lev6
        dw lev7
opt_music:  db 1
opt_sfx:    db 1
        db NLEV
        dw LEV_STRIDE
        dw bank1_end
        jp b1_load
        ds 48-($-B1_TABLE),0
        ELSE
        dw lev0
        dw lev1
        dw lev2
opt_music:  db 1
opt_sfx:    db 1
        db 3
        dw LEV_STRIDE
        dw bank1_end
        ds 32-($-B1_TABLE),0
        ENDIF

        include "ay.asm"
        include "../gen/music_data.asm"

        IF DEFINED LEVELS8
; b1_load (lane K1): H = level id 1..8, DE = level_data. Copies that level's image (LEV_STRIDE B) over the engine's slot,
; then the low code block image to LOWCODE (LOWCODE_LEN B: dc_white .. msg_dead [+ hr_pass], with its variables' initial
; values). Called through the +32 entry by shim128.asm load_level with bank 1 paged, interrupts off and the stack in the
; fixed area (rule F2). Destroys AF BC DE HL. levtab (C009h..C018h) never crosses a page.
b1_load:
        ld a,h
        dec a
        add a,a
        add a,levtab and 255
        ld l,a
        ld h,levtab/256
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                 ; HL = level image
        ld bc,LEV_STRIDE
        ldir
        ld hl,lowcode_img
        ld de,LOWCODE
        ld bc,LOWCODE_LEN
        ldir
        ret
lowcode_img:
        incbin "../../build/lowcode128.bin"
lev0:   incbin "../../build/lev128_0.bin"
lev1:   incbin "../../build/lev128_1.bin"
lev2:   incbin "../../build/lev128_2.bin"
lev3:   incbin "../../build/lev128_3.bin"
lev4:   incbin "../../build/lev128_4.bin"
lev5:   incbin "../../build/lev128_5.bin"
lev6:   incbin "../../build/lev128_6.bin"
lev7:   incbin "../../build/lev128_7.bin"
        ELSE
lev0:   incbin "../../build/lev128_0.bin"
lev1:   incbin "../../build/lev128_1.bin"
lev2:   incbin "../../build/lev128_2.bin"
        ENDIF
bank1_end:
