; main_b.asm - Kill'em all Spectrum Next EDITION B program (lane N1M): main.asm's structure (lane M: start-up, palette,
; 50 Hz time base, keys, collision) linked with lane N1's walker (walk_b.asm) and lane N1D's drawers (draw_b.asm).
; Built by tools/nx_build.py:
;   .venv/bin/python tools/nx_build.py --src src/next/main_b.asm --out build/next/killemall_b.nex --assets build/next/assets_b
;        --level build/night/N1_level01.bin --level-txt assets/levels/01_entry.txt
; The tool pokes <assets>/palette.bin at PALETTE (9E00h), ONE mapc level at LEVEL (0B800h: spec v0.2 section 1 layout,
; 'K',1,32,32,sx,sy,start_angle,n_things + 1024 cells) and the level's #ceil/#ftex/#ctex bytes at CEIL_B/FTEX_B/CTEX_B
; (db bytes below, inside the code image) and packs the .nex (banks 5 screen+vars, 2 code, 4 tables + IM1 ISR, 8..11 walls,
; 12 floors; PC 8000h SP 5F00h).
; Start-up (spec v0.1 section 8, unchanged): nextreg 7 = 3 (28 MHz), 15h = 80h (LoRes 128x96 8bpp), MMU slot 0/1 = 8K banks
; 8/9 (tables + the IM1 ISR that counts ticks at 5808h), slot 6 = 8K bank 16 (walls), slot 7 = 8K bank 24 (floors), the
; 256-entry palette from PALETTE through nextreg 43h/40h/44h, im 1 / ei. Camera from the mapc header (spec v0.2 section 1):
; px = sx*256 + 128, py = sy*256 + 128, ang = start_angle*4. CEIL/FTEX/CTEX copied to walk_b_vars.inc's bytes.
; Game loop (main.asm's): read the keyboard once per frame (Q/7 forward, A/6 back, O/5 turn left, P/8 turn right), simulate
; one step per 50 Hz tick elapsed since the previous frame (TURN_SPEED, MOVE_SPEED; collision: the destination pushed
; WALL_MARGIN ahead along each moving axis AND the destination cell itself must be walkable = mapc code 0; outside the map
; is solid; blocked diagonal moves slide along x then y), setup_camera_b when px/py/ang changed, then one frame =
; walk_frame_b (planes_reset, 128 columns through draw_piece/plane_add/void_fill, planes_flush, frames += 1).
; frames/px/py/ang/ticks stay at 5800h..5809h (nx_vars.inc) so tools/nx_walk_video.py works unchanged.
; Plane tier: planes-FLAT by default (see the `if defined` block below); pasmo --equ PLANES_HI=1 / PLANES_LO=1 selects another
; tier (build/night/N1M_build_tier.py does that for tools/nx_build.py; tools/nx_test_full_b.py for the oracle).
; Test hook: tools/nx_test_full_b.py assembles src/next/test_full_b.asm, which defines TEST_FULL_B and includes THIS file;
; the start-up then jumps to tfb_main (forced camera, one compared frame, timed frames) instead of main_loop.
; Z80N opcodes as db: nextreg r,v = 0EDh,091h,r,v ; nextreg r,a = 0EDh,092h,r ; mul d,e = 0EDh,030h ; add hl,a = 0EDh,031h.
        org 8000h
        include "nx_vars.inc"
        include "walk_b_vars.inc"
; ---- plane tier (spec v0.2 section 6: hi, then lo, then flat; the first tier >= 25 fps along the scripted path ships; none did
; (build/night/N1M_result.out: hi 12.7 fps, lo 14.6 fps, flat 20.5 fps) so the DEFAULT build of this file is planes-flat.
; Override from the command line: pasmo --equ PLANES_HI=1 (or PLANES_LO=1 / PLANES_FLAT=1) - build/night/N1M_build_tier.py and
; tools/nx_test_full_b.py do exactly that; tools/nx_build.py alone always builds this default (flat).
        if defined PLANES_HI
        else
        if defined PLANES_LO
        else
        if defined PLANES_FLAT
        else
PLANES_FLAT equ 1
        endif
        endif
        endif
        include "draw_b_vars.inc"
        include "main_b_vars.inc"

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
        ; ---- level parameters (poked by tools/nx_build.py into the code image) -> the walker's bytes
        ld a,(CEIL_B)
        ld (wb_ceil),a
        ld a,(FTEX_B)
        ld (wb_ftex),a
        ld a,(CTEX_B)
        ld (wb_ctex),a
        ; ---- variables ; camera from the mapc header (spec v0.2 section 1)
        ld hl,0
        ld (ticks),hl
        ld (frames),hl
        ld (g_last_tick),hl
        ld a,(LV_SX)
        ld h,a
        ld l,128
        ld (px),hl                      ; px = sx*256 + 128
        ld a,(LV_SY)
        ld h,a
        ld l,128
        ld (py),hl                      ; py = sy*256 + 128
        ld a,(LV_ANGLE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld (ang),hl                     ; ang = start_angle * 4 (0..1020)
        xor a
        ld (g_keys),a
        ld a,1
        ld (g_moved),a                  ; force setup_camera_b before the first frame
        xor a
        ld (g_draw_off),a               ; lane N2: sprites/weapon/HUD drawn (1 = engine frame only, oracle A)
        ld (g_hold),a
        ld (g_held),a
        ld (g_hold_tk),a
        ld (g_hold_tk+1),a
        ld a,7
        ld (g_draw_mask),a              ; lane N2: sprites + weapon + HUD (the oracles clear bits)
        xor a
        ld (g_lvreq),a                  ; lane N3: no level request pending (tools/nx_game_video.py --level K sets it)
        IF DEFINED MOUSE_B
        ld (vl_pad),a                   ; lane N5: horizon_q8 = horizon_row*256 (pad byte 0), horizon_row = 48, mouse OFF
        ld (opt_mouse_b),a
        ld (mouse_btn),a
        ld (mouse_dbnc),a
        ld a,VL_DEF
        ld (horizon_row),a
        ENDIF
        call game_init                  ; lane N2: health/ammo/keys, things from the mapc level, door log (game_b_next.asm)
        im 1
        ei
        if defined TEST_FULL_B
        jp tfb_main                     ; test_full_b.asm: forced camera, one compared frame, timed frames
        endif
        if defined TEST_GAME_B
        jp tgb_main                     ; test_game_b.asm (lane N2): scene/things poked by tools/nx_test_game_b.py, game_frame on demand
        endif

; ---------------------------------------------------------------------------------------------------------------
; main loop: elapsed = ticks - g_last_tick (capped at MAX_TICKS) ; read keys ; elapsed x tick ; setup_camera_b if moved ;
; walk_frame_b (draws the frame through the drawers and increments frames)
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
        IF DEFINED MOUSE_B
        call look_keys_b                ; lane N5: I toggles the mouse, W/S/E vertical look (mouse_next.asm)
        call mouse_look_b               ; lane N5: Kempston/PS2 mouse -> ang (g_moved), horizon_row, click latch
        ENDIF
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
        call setup_camera_b             ; dirx/diry/plx/ply, mx0/my0, eye = 22 for the new px/py/ang
ml_draw:
        ld a,(g_lvreq)                  ; lane N3 tool hook: g_lvreq = 1 -> load level g_level from bank 14 + restart_level
        or a
        call nz,level_request
        call game_steps                 ; lane N2: 0..2 game steps of 0.1 s (kea48.asm steps model; game_b_next.asm)
        call game_frame                 ; lane N2: walk_frame_b, then sprites + weapon + HUD into the LoRes frame (sprites_next.asm)
        jp main_loop

; ---------------------------------------------------------------------------------------------------------------
; read_keys - port 0FEh rows (active low) -> g_keys bits KEY_FWD/KEY_BACK/KEY_LEFT/KEY_RIGHT (exactly main.asm's).
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
        ld a,7Fh
        in a,(0FEh)                     ; SPACE SYM M N B (lane N2: M fire, SPACE use - main.asm's keys)
        bit 2,a
        jr nz,rk_9
        set KB_FIRE,c
rk_9:   bit 0,a
        jr nz,rk_10
        set KB_USE,c
rk_10:
        ld a,c
        IF DEFINED MOUSE_B
        ld hl,mouse_btn                 ; lane N5: OR the click latch (KEY_FIRE / KEY_USE) into g_keys; clear it only in a
        or (hl)                         ; frame that runs a game step (game_steps: ticks - g_step_t >= STEP_B), so a click
        ld c,a                          ; between two 0.1 s steps is never lost (game_tick consumes g_keys, not read_keys)
        ld a,(ticks)
        ld hl,g_step_t
        sub (hl)
        cp STEP_B
        ld a,c
        jr c,rk_11
        ld hl,mouse_btn
        ld (hl),0
rk_11:
        ENDIF
        ld (g_keys),a
        ret

; ---------------------------------------------------------------------------------------------------------------
; tick - one 50 Hz step of the player (main.asm's): turn (ang +- TURN_SPEED, wrap 0..1023, setup_camera_b so dirx/diry
;        follow at once), then move by step = smul_shr(dir, MOVE_SPEED, 8) forward or back with collision (can_move);
;        a blocked diagonal move is retried along x only, then y only (wall sliding). Sets g_moved when px/py/ang changed.
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
        call setup_camera_b
tk_move:
        ld a,(g_keys)
        and KEY_FWD | KEY_BACK
        ret z
        cp KEY_FWD | KEY_BACK
        ret z                           ; both pressed: cancel
        ld hl,(dirx)
        call mb_step                    ; HL = smul_shr(dirx, MOVE_SPEED, 8), signed (|result| <= MOVE_SPEED)
        ld (g_dx),hl
        ld hl,(diry)
        call mb_step
        ld (g_dy),hl
        ld a,(g_keys)
        bit KB_BACK,a
        jr z,tk_dir_ok
        ld hl,(g_dx)                    ; back: negate the step
        call wb_neg_hl
        ld (g_dx),hl
        ld hl,(g_dy)
        call wb_neg_hl
        ld (g_dy),hl
tk_dir_ok:
        ld hl,(g_dx)                    ; margins: push the test point WALL_MARGIN ahead along each moving axis
        call margin_of
        ld (g_mgx),hl
        ld hl,(g_dy)
        call margin_of
        ld (g_mgy),hl
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

; mb_step - HL = smul_shr(HL, MOVE_SPEED, 8) (spec v0.1 section 0: sign * ((|a| * |b|) >> s)); |HL| <= 256. destroys A, C, DE
mb_step:
        ld c,0
        bit 7,h
        jr z,mbs_pos
        call wb_neg_hl                  ; HL = |dir|
        inc c
mbs_pos:
        ld a,h
        or a
        jr nz,mbs_256                   ; |dir| = 256: (256 * MOVE_SPEED) >> 8 = MOVE_SPEED
        ld d,l
        ld e,MOVE_SPEED
        db 0EDh,030h                    ; mul d,e : DE = |dir| * MOVE_SPEED (<= 255 * 24)
        ld l,d                          ; >> 8
        ld h,0
        jr mbs_sign
mbs_256:
        ld hl,MOVE_SPEED
mbs_sign:
        dec c
        ret nz                          ; dir >= 0
        jp wb_neg_hl                    ; dir < 0: negative step

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
;            walkable cell (mapc code 0; outside the map = solid), AND the candidate's own cell must be walkable too
;            (so a diagonal move cannot cut a corner). Edition B has no heights: no MAX_STEP rule.
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
; cell_ok - cell (B = mx, C = my): carry clear = walkable (code 0), carry set = blocked (code != 0, or outside the 32x32
;           map - a wrapped negative coordinate is >= 32 too). destroys A, DE, HL
cell_ok:
        ld a,b
        cp MAPC_W
        jr nc,co_blocked
        ld a,c
        cp MAPC_H
        jr nc,co_blocked
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                       ; HL = my * 32
        ld a,b
        db 0EDh,031h                    ; add hl,a : + mx
        ld de,LV_CELLS
        add hl,de
        ld a,(hl)
        or a                            ; code 0 -> Z and carry clear
        ret z
co_blocked:
        scf
        ret

; ---- level parameters poked by tools/nx_build.py (--level-txt header lines #ceil= #ftex= #ctex=; spec v0.2 defaults)
CEIL_B: db 32                           ; ceiling height H32 (32 or 64)
FTEX_B: db 0                            ; floor texture id (manifest "flag")
CTEX_B: db 1                            ; ceiling texture id (manifest "plaster")

        include "walk_b.asm"            ; lane N1: setup_camera_b, walk_frame_b (spec v0.2 section 3)
        include "draw_b.asm"            ; lane N1D: draw_piece, plane_add, planes_reset, planes_flush, void_fill (tiers)
        include "game_b_next.asm"       ; lane N2: game rules (steps, doors, pickups, enemy AI, pistol), ETAB data
        include "sprites_next.asm"      ; lane N2: things -> vis list -> software sprites with ZBUF occlusion, weapon
code_end:
        if code_end gt PALETTE
        .error "main_b.asm code overlaps the palette block at 9E00h"
        endif
; lane N4 (8 Nov 2026): the HUD (dirty-flag redraw, bug 1) no longer fits below PALETTE (9E00h): code_end would be 9F20h.
; It is assembled into the free area between PALETTE+512 and PLANES (0A800h), ABOVE the test wrappers (test_full_b.asm /
; test_game_b.asm: org 0A010h, ends <= 0A095h): 0A200h..0A7FFh. tools/nx_build.py pads the code image to 16K, so the bytes land.
        org 0A200h
        include "hud_next.asm"          ; lane N2: LoRes HUD band (rows 88..95) ; lane N4: dirty-flag redraw
        include "mouse_next.asm"        ; lane N5: mouse look + vertical look (empty unless --equ MOUSE_B=1)
hud_end:
        if hud_end gt PLANES
        .error "hud_next.asm overlaps the PLANES block at 0A800h"
        endif
        org code_end                    ; the test wrappers (org 0A010h) and nx_build's code length see code_end again
