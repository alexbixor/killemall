; test_walk.asm - lane D1 stand-alone test program for the column walker (spec sections 2-4, 9, 10).
; Built by tools/nx_test_walk.py: pasmo --bin src/next/test_walk.asm build/next/test_walk.bin build/next/test_walk.sym
; .nex banks: 5 (screen+vars, zero), 2 (this code; LEVEL at 0B800h copied in by the tool), 4 (tables), 6 (call log, zero).
; Sequence: nextreg 7 = 3 (28 MHz), MMU slots 0/1 = 8K banks 8/9 (tables + ISR), slots 6/7 = log banks, im 1 / ei,
;   1. smul_shr / umul32 vectors from MULTEST -> MULRES ; 2. yproj + row_of vectors from YTEST -> YRES ;
;   3. px, py, ang from the SCENE block -> setup_camera ; walk_frame once with logging on ;
;   4. SCENE.nframes more walk_frames with the stubs disabled, ticks measured around them (T_DTICKS) ;
;   5. DONE_FLAG = 1 ; jr $.
        org 8000h
        include "nx_vars.inc"
        include "walk_vars.inc"

start:
        di
        ld sp,MAIN_STACK
        db 0EDh,091h,07h,03h            ; nextreg 7,3 : CPU 28 MHz
        db 0EDh,091h,50h,TABLE_BANK0    ; nextreg 50h,8 : slot 0 = 8K bank 8 (ISR, SIN, COS, RD, ZBUF)
        db 0EDh,091h,51h,TABLE_BANK0+1  ; nextreg 51h,9 : slot 1 = 8K bank 9 (RECIP)
        db 0EDh,091h,56h,LOG_BANK       ; nextreg 56h,12 : slot 6 = log bank (test only)
        db 0EDh,091h,57h,LOG_BANK+1     ; nextreg 57h,13 : slot 7 = log bank + 1
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        xor a
        ld (DONE_FLAG),a
        im 1
        ei
        ; ---- 1. multiply vectors: n x (a lo, a hi, b lo, b hi, s) -> n x (L, H, E, D)
        ld hl,MULTEST
        ld a,(hl)
        inc hl
        ld ix,MULRES
        or a
        jr z,mul_done
        ld b,a
mul_loop:
        push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        inc hl
        push hl
        ex de,hl                        ; HL = a
        ld d,b
        ld e,c                          ; DE = b
        cp 0FFh
        jr z,mul_unsigned
        call smul_shr
        jr mul_store
mul_unsigned:
        call umul32
mul_store:
        ld (ix+0),l
        ld (ix+1),h
        ld (ix+2),e
        ld (ix+3),d
        inc ix
        inc ix
        inc ix
        inc ix
        pop hl
        pop bc
        djnz mul_loop
mul_done:
        ; ---- 2. projection vectors: n x (h, eye, d lo, d hi) -> n x (y lo, y hi, row)
        ld hl,YTEST
        ld a,(hl)
        inc hl
        ld ix,YRES
        or a
        jr z,y_done
        ld b,a
y_loop:
        push bc
        ld a,(hl)
        inc hl
        ld c,a                          ; C = h
        ld a,(hl)
        inc hl
        ld (eye),a
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        ld a,c
        call yproj
        ld (ix+0),l
        ld (ix+1),h
        call row_of
        ld (ix+2),a
        inc ix
        inc ix
        inc ix
        pop hl
        pop bc
        djnz y_loop
y_done:
        ; ---- 3. the logged frame
        ld hl,(SCENE+0)
        ld (px),hl
        ld hl,(SCENE+2)
        ld (py),hl
        ld hl,(SCENE+4)
        ld (ang),hl
        call setup_camera
        ld hl,0
        ld (LOG_COUNT),hl
        ld hl,LOG_BASE
        ld (LOG_PTR),hl
        ld a,1
        ld (LOG_ON),a
        call walk_frame
        ; ---- 4. timing frames (stubs disabled): T_DTICKS = ticks spent in SCENE.nframes frames
        xor a
        ld (LOG_ON),a
        ld a,(SCENE+6)
        ld (T_N),a
        or a
        jr z,t_done
        ld hl,(ticks)
        ld (T_TICK0),hl
t_loop:
        call walk_frame
        ld hl,T_N
        dec (hl)
        jr nz,t_loop
        ld hl,(ticks)
        ld de,(T_TICK0)
        or a
        sbc hl,de
        ld (T_DTICKS),hl
t_done:
        ; ---- 4b. tick calibration: 16 x 65536 x (dec bc 6 + ld a,b 4 + or c 4 + jr nz 12/7) = 27263093 T-states -> T_CAL ticks
        ld hl,(ticks)
        ld (T_TICK0),hl
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
        ld de,(T_TICK0)
        or a
        sbc hl,de
        ld (T_CAL),hl
        ; ---- 5. done
        ld a,1
        ld (DONE_FLAG),a
park:
        jr park

        include "walk.asm"
        include "walk_stubs.asm"
code_end:
        if code_end gt 9C00h
        .error "test_walk code overlaps the test blocks at 9C00h"
        endif
