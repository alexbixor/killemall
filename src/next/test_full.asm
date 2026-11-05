; test_full.asm - lane S end-to-end test program: the real walker (walk.asm, with the plane-span coalescer on, exactly as
; main.asm builds it) plus the real drawers (draw.asm) render one frame of a spec section 9 scene into the LoRes screen;
; tools/nx_test_full.py compares the 12288 screen bytes with build/night/ref/<scene>.frame.bin (0 differing bytes required)
; and reads the ticks of 20 more frames (TF_RES) = the whole engine's cost per frame.
; .nex banks: 5 (screen+vars, zero), 2 (this code; LEVEL at 0B800h poked in by the tool), 4 (tables + ISR), 8..11 (walls.bin),
;   12 (floors.bin). Sequence: 28 MHz, MMU slots 0/1 = 8K banks 8/9, slot 6 = 16, slot 7 = 24, im 1 / ei, SCENE -> px/py/ang,
;   setup_camera, walk_frame (the compared frame), 20 timed walk_frames, calibration loop, DONE = 1.
        org 8000h
        include "nx_vars.inc"
        include "walk_vars.inc"
WALK_COALESCE equ 1             ; walk.asm: merge touching plane spans before plane_add (main.asm does the same)

; SCENE (9F00h: px word, py word, ang word, poked by the tool) comes from walk_vars.inc
TF_T0       equ 59F8h           ; word  ticks before the timed frames
TF_RES      equ 59FCh           ; word  ticks for 20 frames
TF_CAL      equ 59F6h           ; word  ticks of the calibration loop (expect ~49 at 28 MHz)
TF_DONE     equ 59FFh           ; byte  1 when finished

start:
        di
        ld sp,MAIN_STACK
        db 0EDh,091h,07h,03h            ; nextreg 7,3 : CPU 28 MHz
        db 0EDh,091h,15h,80h            ; nextreg 15h,80h : LoRes layer on
        db 0EDh,091h,50h,TABLE_BANK0    ; slot 0 = tables + ISR
        db 0EDh,091h,51h,TABLE_BANK0+1  ; slot 1 = RECIP
        db 0EDh,091h,56h,WALL_BANK0     ; slot 6 = wall textures 0,1
        db 0EDh,091h,57h,FLOOR_BANK     ; slot 7 = floors
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        xor a
        ld (TF_DONE),a
        ld hl,(SCENE+0)
        ld (px),hl
        ld hl,(SCENE+2)
        ld (py),hl
        ld hl,(SCENE+4)
        ld (ang),hl
        im 1
        ei
        call setup_camera
        call walk_frame                 ; the frame that is compared with <scene>.frame.bin
        ld hl,(ticks)
        ld (TF_T0),hl
        ld b,20
t_loop:
        push bc
        call walk_frame
        pop bc
        djnz t_loop
        ld hl,(ticks)
        ld de,(TF_T0)
        or a
        sbc hl,de
        ld (TF_RES),hl
        ld hl,(ticks)
        ld (TF_T0),hl
        ld d,16
cal_outer:
        ld bc,0
cal_inner:
        dec bc
        ld a,b
        or c
        jr nz,cal_inner
        dec d
        jr nz,cal_outer
        ld hl,(ticks)
        ld de,(TF_T0)
        or a
        sbc hl,de
        ld (TF_CAL),hl
        ld a,1
        ld (TF_DONE),a
park:
        jr park

        include "walk.asm"
        include "draw.asm"
code_end:
        if code_end gt 9F00h
        .error "test_full code overlaps the SCENE block at 9F00h"
        endif
