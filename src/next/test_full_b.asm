; test_full_b.asm - lane N1M end-to-end test program: THE REAL EDITION B PROGRAM (main_b.asm, included verbatim: start-up,
; palette, level parameters, walk_b.asm + draw_b.asm) with the camera forced to a scene instead of entering main_loop.
; TEST_FULL_B makes main_b.asm's start-up `jp tfb_main` after im 1 / ei. tools/nx_test_full_b.py pokes the scene
; (px, py, ang words) at TFB_SCENE, the palette, the level and CEIL_B/FTEX_B/CTEX_B exactly like tools/nx_build.py.
; Sequence: px/py/ang := scene ; setup_camera_b ; walk_frame_b (the frame compared with the reference) ; 20 timed
; walk_frame_b calls (TFB_RES = ticks) ; calibration loop (TFB_CAL, ~49 ticks at 28 MHz) ; TFB_DONE = 1 ; park.
; Tier: pasmo --equ PLANES_LO=1 / --equ PLANES_FLAT=1 (draw_b_vars.inc), default planes-hi.
TEST_FULL_B equ 1
        include "main_b.asm"

TFB_SCENE   equ 9D00h           ; px word, py word, ang word (poked by the tool; below PALETTE = 9E00h)
TFB_T0      equ 59F8h           ; word  ticks before the timed frames (drawers' scratch area ends at 59F5h: see draw_b.asm)
TFB_RES     equ 59FCh           ; word  ticks for 20 frames
TFB_CAL     equ 59F6h           ; word  ticks of the calibration loop (expect ~49 at 28 MHz)
TFB_DONE    equ 59FFh           ; byte  1 when finished

tfb_main:
        ld hl,(TFB_SCENE+0)
        ld (px),hl
        ld hl,(TFB_SCENE+2)
        ld (py),hl
        ld hl,(TFB_SCENE+4)
        ld (ang),hl
        xor a
        ld (TFB_DONE),a
        call setup_camera_b
        call walk_frame_b               ; the frame that is compared with the reference
        ld hl,(ticks)
        ld (TFB_T0),hl
        ld b,20
tfb_loop:
        push bc
        call walk_frame_b
        pop bc
        djnz tfb_loop
        ld hl,(ticks)
        ld de,(TFB_T0)
        or a
        sbc hl,de
        ld (TFB_RES),hl
        ld hl,(ticks)
        ld (TFB_T0),hl
        ld d,16
tfb_cal_outer:
        ld bc,0
tfb_cal_inner:
        dec bc
        ld a,b
        or c
        jr nz,tfb_cal_inner
        dec d
        jr nz,tfb_cal_outer
        ld hl,(ticks)
        ld de,(TFB_T0)
        or a
        sbc hl,de
        ld (TFB_CAL),hl
        ld a,1
        ld (TFB_DONE),a
tfb_park:
        jr tfb_park
tfb_end:
        if tfb_end gt TFB_SCENE
        .error "test_full_b code overlaps the scene block at 9D00h"
        endif
