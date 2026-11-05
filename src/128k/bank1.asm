; bank1.asm - Kill'em all 128K (lane T4): everything that lives in RAM BANK 1 (paged at 49152 only while the
; shim in the engine image calls in: see shim128.asm). Assembled standalone: pasmo --bin bank1.asm (cwd src/128k).
; Fixed jump/data table at 49152 (the engine image never needs this file's symbols; test_128.py checks it vs the .sym):
;   +0  jp snd_isr        per-frame tick (AY register writes)
;   +3  jp snd_fx         A = SFX id 1..10 (enqueue)
;   +6  jp snd_music      A = 0 stop / 1 menu / 2 game
;   +9  dw lev0, lev1, lev2   level images: exact level_data slot layout (tools/mklevelblk.py: id 1..3 + header +
;                          1024 cells + 16 things = LEV_STRIDE = 1081 bytes), so a plain LDIR replaces the slot
;   +15 db opt_music copy  +16 db opt_sfx copy  (the engine's state.asm bytes sit inside the paged window:
;        the shim copies them here right after paging and before calling snd_fx / snd_music / snd_isr)
;   +17 db 3 (level count)   +18 dw LEV_STRIDE   +20 dw bank1_end
        org 49152
        include "gen/lev128_sizes.asm"
B1_TABLE:
        jp snd_isr
        jp snd_fx
        jp snd_music
        dw lev0
        dw lev1
        dw lev2
opt_music:  db 1
opt_sfx:    db 1
        db 3
        dw LEV_STRIDE
        dw bank1_end
        ds 32-($-B1_TABLE),0

        include "ay.asm"
        include "../gen/music_data.asm"

lev0:   incbin "../../build/lev128_0.bin"
lev1:   incbin "../../build/lev128_1.bin"
lev2:   incbin "../../build/lev128_2.bin"
bank1_end:
