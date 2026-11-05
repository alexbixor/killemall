; main.asm - Kill'em all Spectrum Next engine: the first runnable program (lane M: game loop, input, collision).
; Built by tools/nx_build.py: pasmo --bin src/next/main.asm build/next/main.bin build/next/main.sym ; the tool pokes
; build/next/assets/palette.bin at PALETTE (9E00h) and level0.bin at LEVEL (0B800h) into the 16K code image (bank 2) and
; packs build/next/killemall_next.nex (banks 5 screen+vars, 2 code, 4 tables, 8..11 walls, 12 floors; PC 8000h SP 5F00h).
; Start-up (spec section 8): nextreg 7 = 3 (28 MHz), 15h = 80h (LoRes 128x96 8bpp), MMU slot 0/1 = 8K banks 8/9 (tables +
; the IM1 ISR that counts ticks at 5808h), slot 6 = 8K bank 16 (walls), slot 7 = 8K bank 24 (floors), the 256-entry palette
; from PALETTE through nextreg 43h/40h/44h, im 1 / ei.
; Game loop: read the keyboard once per frame (Q/7 forward, A/6 back, O/5 turn left, P/8 turn right), simulate one step per
; 50 Hz tick elapsed since the previous frame (TURN_SPEED angle units, MOVE_SPEED Q8 cells; collision: the destination
; pushed WALL_MARGIN ahead along each moving axis must be a non-solid cell whose floor is within MAX_STEP H32 of the current
; floor - steps yes, walls and big drops no; blocked diagonal moves slide along x then y), setup_camera when px/py/ang
; changed, walk_frame (lane D1's proven walker; it increments frames at 5800h).
; Drawers: draw_flat.asm = flat-colour stand-ins (lane M); the textured draw.asm replaces it by changing the include below.
; Z80N opcodes as db: nextreg r,v = 0EDh,091h,r,v ; nextreg r,a = 0EDh,092h,r.
        org 8000h
        include "nx_vars.inc"
        include "walk_vars.inc"
        include "main_vars.inc"
WALK_COALESCE equ 1             ; lane S: walk.asm merges touching plane spans of a column before calling plane_add

start:
        di
        ld sp,MAIN_STACK
        db 0EDh,091h,07h,03h            ; nextreg 7,3 : CPU 28 MHz
        db 0EDh,091h,15h,80h            ; nextreg 15h,80h : LoRes layer on (128x96, 8 bpp), sprites off
        db 0EDh,091h,50h,TABLE_BANK0    ; nextreg 50h,8 : slot 0 = 8K bank 8 (IM1 ISR, SIN, COS, RD, ZBUF)
        db 0EDh,091h,51h,TABLE_BANK0+1  ; nextreg 51h,9 : slot 1 = 8K bank 9 (RECIP)
        db 0EDh,091h,56h,WALL_BANK0     ; nextreg 56h,16 : slot 6 = wall textures 0/1 (the drawers re-page per piece)
        db 0EDh,091h,57h,FLOOR_BANK     ; nextreg 57h,24 : slot 7 = floor textures
        ; ---- palette: 256 entries x 2 bytes from PALETTE (spec section 1)
        db 0EDh,091h,43h,00h            ; nextreg 43h,0 : select the ULA/LoRes palette for writing, auto-increment on
        db 0EDh,091h,40h,00h            ; nextreg 40h,0 : palette index 0
        ld hl,PALETTE
        ld b,0                          ; 256 entries
pal_loop:
        ld a,(hl)
        inc hl
        db 0EDh,092h,44h                ; nextreg 44h,a : byte 0 (RRRGGGBB)
        ld a,(hl)
        inc hl
        db 0EDh,092h,44h                ; nextreg 44h,a : byte 1 (bit 0 = blue lsb), index auto-increments
        djnz pal_loop
        ; ---- variables
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        ld (g_last_tick),hl
        ld hl,START_PX
        ld (px),hl
        ld hl,START_PY
        ld (py),hl
        ld hl,START_ANG
        ld (ang),hl
        xor a
        ld (g_keys),a
        ld a,1
        ld (g_moved),a                  ; force setup_camera before the first frame
        im 1
        ei

; ---------------------------------------------------------------------------------------------------------------
; main loop: elapsed = ticks - g_last_tick (capped at MAX_TICKS) ; read keys ; elapsed x tick ; setup_camera if moved ;
; walk_frame (draws the frame through the drawers and increments frames)
; ---------------------------------------------------------------------------------------------------------------
main_loop:
        ld hl,(ticks)
        ld de,(g_last_tick)
        ld (g_last_tick),hl
        or a
        sbc hl,de                       ; HL = ticks since the previous frame start (modulo 65536)
        ld a,h
        or a
        jr nz,ml_cap
        ld a,l
        cp MAX_TICKS+1
        jr c,ml_ticks_ok
ml_cap:
        ld a,MAX_TICKS
ml_ticks_ok:
        ld (g_dticks),a
        call read_keys
ml_tick_loop:
        ld a,(g_dticks)
        or a
        jr z,ml_sim_done
        dec a
        ld (g_dticks),a
        call tick
        jr ml_tick_loop
ml_sim_done:
        ld a,(g_moved)
        or a
        jr z,ml_draw
        xor a
        ld (g_moved),a
        call setup_camera               ; dirx/diry/plx/ply, mx0/my0, eye for the new px/py/ang
ml_draw:
        call walk_frame
        jp main_loop

; ---------------------------------------------------------------------------------------------------------------
; read_keys - port 0FEh rows (active low) -> g_keys bits KEY_FWD/KEY_BACK/KEY_LEFT/KEY_RIGHT.
;   Q (row 0FBh bit 0) / cursor up 7 (row 0EFh bit 3)     = forward
;   A (row 0FDh bit 0) / cursor down 6 (row 0EFh bit 4)   = back
;   O (row 0DFh bit 1) / cursor left 5 (row 0F7h bit 4)   = turn left
;   P (row 0DFh bit 0) / cursor right 8 (row 0EFh bit 2)  = turn right
; destroys A, C
; ---------------------------------------------------------------------------------------------------------------
read_keys:
        ld c,0
        ld a,0FBh
        in a,(0FEh)                     ; Q W E R T
        bit 0,a
        jr nz,rk_1
        set KB_FWD,c
rk_1:
        ld a,0FDh
        in a,(0FEh)                     ; A S D F G
        bit 0,a
        jr nz,rk_2
        set KB_BACK,c
rk_2:
        ld a,0DFh
        in a,(0FEh)                     ; P O I U Y
        bit 1,a
        jr nz,rk_3
        set KB_LEFT,c
rk_3:
        bit 0,a
        jr nz,rk_4
        set KB_RIGHT,c
rk_4:
        ld a,0F7h
        in a,(0FEh)                     ; 1 2 3 4 5
        bit 4,a
        jr nz,rk_5
        set KB_LEFT,c
rk_5:
        ld a,0EFh
        in a,(0FEh)                     ; 0 9 8 7 6
        bit 4,a
        jr nz,rk_6
        set KB_BACK,c
rk_6:
        bit 3,a
        jr nz,rk_7
        set KB_FWD,c
rk_7:
        bit 2,a
        jr nz,rk_8
        set KB_RIGHT,c
rk_8:
        ld a,c
        ld (g_keys),a
        ret

; ---------------------------------------------------------------------------------------------------------------
; tick - one 50 Hz step of the player: turn (ang +- TURN_SPEED, wrap 0..1023, setup_camera so dirx/diry follow at once),
;        then move by step = smul_shr(dir, MOVE_SPEED, 8) forward or back with collision (can_move); a blocked diagonal
;        move is retried along x only, then y only (wall sliding). Sets g_moved when px/py/ang changed.
; ---------------------------------------------------------------------------------------------------------------
tick:
        ld a,(g_keys)
        ld b,a
        and KEY_LEFT | KEY_RIGHT
        jr z,tk_move
        ld hl,(ang)
        bit KB_LEFT,b
        jr z,tk_no_left
        ld de,1024-TURN_SPEED
        add hl,de                       ; ang -= TURN_SPEED (mod 1024)
tk_no_left:
        bit KB_RIGHT,b
        jr z,tk_no_right
        ld de,TURN_SPEED
        add hl,de                       ; ang += TURN_SPEED
tk_no_right:
        ld a,h
        and 3
        ld h,a                          ; wrap 0..1023
        ld (ang),hl
        ld a,1
        ld (g_moved),a
        call setup_camera
tk_move:
        ld a,(g_keys)
        and KEY_FWD | KEY_BACK
        ret z
        cp KEY_FWD | KEY_BACK
        ret z                           ; both pressed: cancel
        ld hl,(dirx)
        ld de,MOVE_SPEED
        ld a,8
        call smul_shr                   ; HL = (dirx * MOVE_SPEED) >> 8, signed (|result| <= MOVE_SPEED)
        ld (g_dx),hl
        ld hl,(diry)
        ld de,MOVE_SPEED
        ld a,8
        call smul_shr
        ld (g_dy),hl
        ld a,(g_keys)
        bit KB_BACK,a
        jr z,tk_dir_ok
        ld hl,(g_dx)                    ; back: negate the step
        call neg_hl
        ld (g_dx),hl
        ld hl,(g_dy)
        call neg_hl
        ld (g_dy),hl
tk_dir_ok:
        ld hl,(g_dx)                    ; margins: push the test point WALL_MARGIN ahead along each moving axis
        call margin_of
        ld (g_mgx),hl
        ld hl,(g_dy)
        call margin_of
        ld (g_mgy),hl
        ld a,(px+1)
        ld b,a
        ld a,(py+1)
        ld c,a
        call cell_ptr
        ld a,(hl)
        ld (g_cfloor),a                 ; floor of the cell the player stands on
        ld hl,(px)                      ; try the full move (px + dx, py + dy)
        ld de,(g_dx)
        add hl,de
        ld (g_npx),hl
        ld hl,(py)
        ld de,(g_dy)
        add hl,de
        ld (g_npy),hl
        call can_move
        jr nc,tk_commit
        ld hl,(py)                      ; blocked: slide along x only (px + dx, py)
        ld (g_npy),hl
        ld hl,0
        ld (g_mgy),hl
        call can_move
        jr nc,tk_commit
        ld hl,(px)                      ; slide along y only (px, py + dy)
        ld (g_npx),hl
        ld hl,(py)
        ld de,(g_dy)
        add hl,de
        ld (g_npy),hl
        ld hl,0
        ld (g_mgx),hl
        ld hl,(g_dy)
        call margin_of
        ld (g_mgy),hl
        call can_move
        ret c                           ; fully blocked: stay
tk_commit:
        ld hl,(g_npx)
        ld (px),hl
        ld hl,(g_npy)
        ld (py),hl
        ld a,1
        ld (g_moved),a
        ret

; margin_of - HL = +WALL_MARGIN if HL > 0, -WALL_MARGIN if HL < 0, 0 if HL = 0. destroys A
margin_of:
        bit 7,h
        jr nz,mo_neg
        ld a,h
        or l
        ret z
        ld hl,WALL_MARGIN
        ret
mo_neg:
        ld hl,-WALL_MARGIN
        ret

; ---------------------------------------------------------------------------------------------------------------
; can_move - collision rule for the candidate (g_npx, g_npy): the test point (candidate + margin per axis) must lie in a
;            non-solid cell (outside the map = solid, via cell_ptr) whose floor is within MAX_STEP of g_cfloor, AND the
;            candidate's own cell must pass the same rule (so a diagonal move cannot cut a corner).
;            out: carry clear = allowed, carry set = blocked. destroys A, B, C, DE, HL
; ---------------------------------------------------------------------------------------------------------------
can_move:
        ld hl,(g_npx)
        ld de,(g_mgx)
        add hl,de
        ld (g_tx),hl
        ld hl,(g_npy)
        ld de,(g_mgy)
        add hl,de
        ld (g_ty),hl
        ld a,(g_tx+1)
        ld b,a
        ld a,(g_ty+1)
        ld c,a
        call cell_ok
        ret c
        ld a,(g_npx+1)
        ld b,a
        ld a,(g_npy+1)
        ld c,a
        ; fall into cell_ok
; cell_ok - cell (B, C): carry clear = non-solid and |floor - g_cfloor| <= MAX_STEP, carry set = blocked. destroys A, HL
cell_ok:
        call cell_ptr                   ; B >= 32 / C >= 16 (also wrapped negatives) -> solid_cell
        inc hl
        inc hl
        bit 7,(hl)                      ; byte2 bit 7 = solid
        jr nz,cm_blocked
        dec hl
        dec hl
        ld a,(g_cfloor)
        sub (hl)                        ; A = cur.floor - nxt.floor (floors are -24..8: no overflow)
        jp p,cm_abs
        neg
cm_abs:
        cp MAX_STEP+1                   ; carry when |diff| <= MAX_STEP
        ccf                             ; -> carry clear = allowed
        ret
cm_blocked:
        scf
        ret

        include "walk.asm"
        include "../../build/night/pre_S/draw.asm"        ; textured drawers (lane D2); draw_flat.asm = flat stand-ins
code_end:
        if code_end gt PALETTE
        .error "main.asm code overlaps the palette block at 9E00h"
        endif
