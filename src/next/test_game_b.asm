; test_game_b.asm - lane N2 test program: THE REAL EDITION B GAME (main_b.asm included verbatim) driven by commands from
; tools/nx_test_game_b.py over ZRCP instead of main_loop:
;   TGB_CMD 1: setup_camera_b + game_frame (one full frame: engine + sprites/weapon/HUD per g_draw_mask) -> TGB_RES = ticks
;   TGB_CMD 2: TGB_N game ticks (game_tick each; g_keys as poked by the tool) -> TGB_RES = ticks
;   TGB_CMD 3: restart_level
;   TGB_CMD 4: build_vis only (banks paged like game_frame) -> VIS_B readable
; After each command TGB_DONE = 1 and TGB_CMD = 0. The tool pokes px/py/ang, THINGS_B, g_keys, g_draw_off/g_draw_mask
; directly (bank 5 RAM). Palette/level/CEIL_B pokes exactly as tools/nx_build.py (the tool reuses nx_build's helpers).
TEST_GAME_B equ 1
        include "main_b.asm"

tgb_main:
        xor a
        ld (TGB_CMD),a
        ld a,1
        ld (TGB_DONE),a
tgb_wait:
        ld a,(TGB_CMD)
        or a
        jr z,tgb_wait
        xor a
        ld (TGB_DONE),a
        ld hl,(ticks)
        ld (g_tmp),hl
        ld a,(TGB_CMD)
        cp 1
        jr z,tgb_frame
        cp 2
        jr z,tgb_ticks
        cp 3
        jr z,tgb_restart
        cp 4
        jr z,tgb_vis
        jr tgb_done
tgb_frame:
        call setup_camera_b
        call game_frame
        jr tgb_done
tgb_ticks:
        ld a,(TGB_N)
        or a
        jr z,tgb_done
tgb_tl: push af
        call game_tick
        pop af
        dec a
        jr nz,tgb_tl
        jr tgb_done
tgb_restart:
        call restart_level
        jr tgb_done
tgb_vis:
        call setup_camera_b
        db 0EDh,091h,56h,SPR_BANK0
        db 0EDh,091h,57h,SPR_BANK1
        call build_vis
        db 0EDh,091h,56h,WALL_BANK0
        db 0EDh,091h,57h,FLOOR_BANK
tgb_done:
        ld hl,(ticks)
        ld de,(g_tmp)
        or a
        sbc hl,de
        ld (TGB_RES),hl
        xor a
        ld (TGB_CMD),a
        ld a,1
        ld (TGB_DONE),a
        jr tgb_wait
tgb_end:
        if tgb_end gt PALETTE
        .error "test_game_b code overlaps the palette block at 9E00h"
        endif
