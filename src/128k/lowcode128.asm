; lowcode128.asm - lane K1 (6 Nov 2026, 128K, pasmo --equ LEVELS8=1): the low code block of src/common/lowcode.asm assembled
; STANDALONE at its run-time address LOWCODE (5BC0h, state.asm) -> build/lowcode128.bin + .sym (tools/lev128.py). The 128K
; level_data slot grew to LEVEL_BLK = 1141 B (36 things) and pushed the block out of the low block tail (7B40h + 1141 = 7FB5h:
; 75 B left below 8000h), so it lives in the dead 128K editor page below the FLIP stack instead (5BC0h..; only BANKM 5B5Ch and
; the vis list 5B60h..5BBFh share that page). The tape image starts at 6C00h, so the bytes travel inside bank 1 (bank1.asm
; incbin) and b1_load copies them to LOWCODE at every load_level (new_game loads level 1 unconditionally under LEVELS8, so the
; block is in place before the first frame). The engine sees the block's symbols through src/128k/gen/lowcode128_equ.asm
; (generated from build/lowcode128.sym by tools/lev128.py, included by kea48.asm instead of lowcode.asm under LEVELS8).
; Externals (pasmo --equ from tools/lev128.py): LOWCODE, CMIN; with hr_pass (HIRES / BANK3): fl_wait, BANKM, fl_pg0,
; draw_sprite - pass 1 with zeros (the block's layout does not depend on them), pass 2 (lev128.py --fix <engine.sym>) with
; the engine's addresses; lev128.py asserts that the .sym of both passes agree.
        org LOWCODE
lowcode_start:
        include "../common/lowcode.asm"
lowcode_len equ low_end - lowcode_start
        end
