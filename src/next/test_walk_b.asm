; test_walk_b.asm - lane N1 stand-alone test program for the edition B column walker (spec v0.2 section 3, 5).
; Built by tools/nx_test_walk_b.py: pasmo --bin src/next/test_walk_b.asm build/next/test_walk_b.bin build/next/test_walk_b.sym
; .nex banks: 5 (screen+vars, zero), 2 (this code; the mapc level copied to LEVEL = 0B800h by the tool), 4 (tables),
; 6 (call log, zero).  Sequence: nextreg 7 = 3 (28 MHz), MMU slots 0/1 = 8K banks 8/9 (tables + ISR), slots 6/7 = log
; banks, im 1 / ei ; px, py, ang, CEIL, FTEX, CTEX from the WB_SCENE block -> setup_camera_b ; walk_frame_b once with the
; logging stubs on ; WB_SCENE.nframes more frames with the stubs disabled, ticks measured around them (WB_T_DTICKS) ;
; tick calibration loop (WB_T_CAL) ; WB_DONE = 1 ; jr $.
; The drawer stubs live in this file (same log format as walk_stubs.asm: 1 = piece (10 bytes pc_c..pc_dv+1),
; 2 = plane (5 bytes pl_c..pl_b), 3 = void (3 bytes vd_c..vd_b)).
        org 8000h
        include "nx_vars.inc"
        include "walk_b_vars.inc"

start:
        di
        ld sp,MAIN_STACK
        db 0EDh,091h,07h,03h            ; nextreg 7,3 : CPU 28 MHz
        db 0EDh,091h,50h,TABLE_BANK0    ; nextreg 50h,8 : slot 0 = 8K bank 8 (ISR, SIN, COS, RD, ZBUF)
        db 0EDh,091h,51h,TABLE_BANK0+1  ; nextreg 51h,9 : slot 1 = 8K bank 9 (RECIP)
        db 0EDh,091h,56h,WB_LOG_BANK    ; nextreg 56h,12 : slot 6 = log bank (test only)
        db 0EDh,091h,57h,WB_LOG_BANK+1  ; nextreg 57h,13 : slot 7 = log bank + 1
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        xor a
        ld (WB_DONE),a
        im 1
        ei
        ; ---- 1. the logged frame
        ld hl,(WB_SCENE+0)
        ld (px),hl
        ld hl,(WB_SCENE+2)
        ld (py),hl
        ld hl,(WB_SCENE+4)
        ld (ang),hl
        ld a,(WB_SCENE+7)
        ld (wb_ceil),a
        ld a,(WB_SCENE+8)
        ld (wb_ftex),a
        ld a,(WB_SCENE+9)
        ld (wb_ctex),a
        call setup_camera_b
        ld hl,0
        ld (WB_LOG_COUNT),hl
        ld hl,WB_LOG_BASE
        ld (WB_LOG_PTR),hl
        ld a,1
        ld (WB_LOG_ON),a
        call walk_frame_b
        ; ---- 2. timing frames (stubs disabled): WB_T_DTICKS = ticks spent in WB_SCENE.nframes frames
        xor a
        ld (WB_LOG_ON),a
        ld a,(WB_SCENE+6)
        ld (WB_T_N),a
        or a
        jr z,t_done
        ld hl,(ticks)
        ld (WB_T_TICK0),hl
t_loop:
        call walk_frame_b
        ld hl,WB_T_N
        dec (hl)
        jr nz,t_loop
        ld hl,(ticks)
        ld de,(WB_T_TICK0)
        or a
        sbc hl,de
        ld (WB_T_DTICKS),hl
t_done:
        ; ---- 3. tick calibration: 16 x 65536 x (dec bc 6 + ld a,b 4 + or c 4 + jr nz 12/7) = 27263093 T-states -> WB_T_CAL
        ld hl,(ticks)
        ld (WB_T_TICK0),hl
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
        ld de,(WB_T_TICK0)
        or a
        sbc hl,de
        ld (WB_T_CAL),hl
        ; ---- 4. done
        ld a,1
        ld (WB_DONE),a
park:
        jr park

        include "walk_b.asm"

; ---- drawer stubs (spec section 10 entry points): log a record per call; WB_LOG_ON = 0 -> return at once
planes_reset:
        ret
planes_flush:
        ret
draw_piece:
        ld a,(WB_LOG_ON)
        or a
        ret z
        ld a,1
        ld b,10
        ld hl,pc_c
        jr log_rec
plane_add:
        ld a,(WB_LOG_ON)
        or a
        ret z
        ld a,2
        ld b,5
        ld hl,pl_c
        jr log_rec
void_fill:
        ld a,(WB_LOG_ON)
        or a
        ret z
        ld a,3
        ld b,3
        ld hl,vd_c
log_rec:                        ; A = record type, B = payload length, HL = payload source
        ld c,a
        ld de,(WB_LOG_COUNT)
        inc de
        ld (WB_LOG_COUNT),de
        ld de,(WB_LOG_PTR)
        ld a,d
        cp WB_LOG_END / 256
        ret nc                  ; log full: count it, drop the bytes
        ld a,c
        ld (de),a
        inc de
        ld c,b
        ld b,0
        ldir
        ld (WB_LOG_PTR),de
        ret
code_end:
        if code_end gt 9F00h
        .error "test_walk_b code overlaps the scene block at 9F00h"
        endif
