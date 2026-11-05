; test_draw_b.asm - lane N1D stand-alone test program for the edition B pixel drawers (draw_b.asm, tier flags via pasmo --equ) (spec sections 5, 6, 8, 9, 10).
; Built by tools/nx_test_draw_b.py: pasmo [--equ PLANES_LO=1|PLANES_FLAT=1] --bin test_draw_b.asm build/next/test_draw_b.bin build/next/test_draw_b.sym (cwd src/next).
; .nex banks: 5 (screen+vars, zero), 2 (this code + palette copy at PAL_COPY), 4 (tables + ISR), 8..11 (walls.bin),
;   12 (floors.bin), 6 [+7] (the byte-coded record list in 8K chunks, see REC_BANK0).
; Sequence: nextreg 7 = 3 (28 MHz), 15h = 80h (LoRes), MMU slots 0/1 = 8K banks 8/9, slot 6 = 16, slot 7 = 24,
;   palette from PAL_COPY (512 bytes = palette.bin) via nextreg 43h/40h/44h, im 1 / ei,
;   one replayed frame (planes_reset, records, planes_flush), then 20 timed replays (T_RES = ticks), the tick calibration loop
;   (T_CAL, ~49 ticks at 28 MHz), DONE = 1, jr $.
; Record list: 1 = piece (c, ra, count, tex, s, u, v lo, v hi, dv lo, dv hi), 2 = plane (c, h, tex, a, b), 3 = void (c, a, b),
;   4 = continue in the next 8K chunk (next 8K bank mapped into slot 1 at REC_BASE), 0 = end of frame.
;   The list lives in 8K banks REC_BANK0.. (16K banks 6, 7) mapped into slot 1 (RECIP is not needed by the drawers):
;   the biggest scene (steps_down) needs 14.4 KB, more than the 6 KB free at 9000h..A7FFh in the code bank.
        org 8000h
        include "nx_vars.inc"

PAL_COPY    equ 8E00h           ; 512 bytes, palette.bin, poked in by the tool
REC_BANK0   equ 12              ; first 8K bank of the record list (16K bank 6)
REC_BASE    equ 2000h           ; slot 1
T0          equ 59F8h           ; word  ticks before the timed replays
CUR_BANK    equ 59FAh           ; byte  8K bank currently mapped into slot 1
T_RES       equ 59FCh           ; word  ticks for 20 replays
T_CAL       equ 59F6h           ; word  ticks of the calibration loop (expect ~49 at 28 MHz)
DONE        equ 59FFh           ; byte  1 when finished
NO_FLUSH    equ 59F5h           ; byte  1 = skip planes_flush (set by tools/nx_test_draw_timing.py only)

start:
        di
        ld sp,MAIN_STACK
        db 0EDh,091h,07h,03h            ; nextreg 7,3 : CPU 28 MHz
        db 0EDh,091h,15h,80h            ; nextreg 15h,80h : LoRes layer on (128x96, 8 bpp), sprites off
        db 0EDh,091h,50h,TABLE_BANK0    ; nextreg 50h,8 : slot 0 = tables + ISR
        db 0EDh,091h,51h,TABLE_BANK0+1  ; nextreg 51h,9 : slot 1 = RECIP (replaced by the record list below)
        db 0EDh,091h,56h,WALL_BANK0     ; nextreg 56h,16 : slot 6 = wall textures 0,1
        db 0EDh,091h,57h,FLOOR_BANK     ; nextreg 57h,24 : slot 7 = floors
        ; palette: 256 entries x 2 bytes (RRRGGGBB, then bit 0 = blue lsb) through nextreg 44h, auto-increment
        db 0EDh,091h,43h,00h            ; nextreg 43h,0 : ULA first palette for read/write, auto-increment on
        db 0EDh,091h,40h,00h            ; nextreg 40h,0 : palette index 0
        ld hl,PAL_COPY
        ld bc,512
pal_loop:
        ld a,(hl)
        inc hl
        db 0EDh,092h,44h                ; nextreg 44h,a
        dec bc
        ld a,b
        or c
        jr nz,pal_loop
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        xor a
        ld (DONE),a
        im 1
        ei
        call frame                      ; the frame that is compared with <scene>.frame.bin
        ld hl,(ticks)
        ld (T0),hl
        ld b,20
t_loop:
        push bc
        call frame
        pop bc
        djnz t_loop
        ld hl,(ticks)
        ld de,(T0)
        or a
        sbc hl,de
        ld (T_RES),hl
        ; tick calibration (same loop as test_walk): 16 x 65536 x (dec bc 6 + ld a,b 4 + or c 4 + jr nz 12) = 27263093 T -> ~48.8 ticks at 28 MHz
        ld hl,(ticks)
        ld (T0),hl
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
        ld de,(T0)
        or a
        sbc hl,de
        ld (T_CAL),hl
        ld a,1
        ld (DONE),a
park:
        jr park

; frame: planes_reset, replay the record list, planes_flush
frame:
        call planes_reset
        ld a,REC_BANK0
        ld (CUR_BANK),a
        db 0EDh,092h,51h                ; nextreg 51h,a
        ld hl,REC_BASE
rec_loop:
        ld a,(hl)
        inc hl
        or a
        jr z,rec_end
        cp 1
        jr z,rec_piece
        cp 2
        jr z,rec_plane
        cp 3
        jr z,rec_void
        ld a,(CUR_BANK)                 ; 4: next chunk
        inc a
        ld (CUR_BANK),a
        db 0EDh,092h,51h                ; nextreg 51h,a
        ld hl,REC_BASE
        jr rec_loop
rec_piece:
        ld de,pc_c
        ld bc,10
        ldir
        push hl
        call draw_piece
        pop hl
        jr rec_loop
rec_plane:
        ld de,pl_c
        ld bc,5
        ldir
        push hl
        call plane_add
        pop hl
        jr rec_loop
rec_void:
        ld de,vd_c
        ld bc,3
        ldir
        push hl
        call void_fill
        pop hl
        jr rec_loop
rec_end:
        ld hl,(frames)
        inc hl
        ld (frames),hl
        ld a,(NO_FLUSH)                 ; timing experiments only: 1 = skip planes_flush
        or a
        ret nz
        jp planes_flush

        include "draw_b_vars.inc"
        include "draw_b.asm"
code_end:
        if code_end gt PAL_COPY
        .error "test_draw code overlaps the palette copy at 8E00h"
        endif
