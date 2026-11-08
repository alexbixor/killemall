; main_b_vars.inc - lane N1M: game-loop variables of the edition B program (src/next/main_b.asm) in 5A00h..5AFFh
; (the lane M scratch area; option A's main.asm is a different program, so the addresses may coincide) and game constants.
; Include AFTER nx_vars.inc, walk_b_vars.inc and draw_b_vars.inc. No code here, only equates.
; CEIL_B / FTEX_B / CTEX_B are NOT here: they are `db` bytes inside main_b.asm (code image 8000h..BFFFh) because
; tools/nx_build.py pokes the level's #ceil/#ftex/#ctex values into the code image at those symbols (N1A_QUESTIONS.md Q4).

; ---- game loop state (main_b.asm)
g_last_tick equ 5A00h          ; word  value of ticks (5808h, IM1 ISR) seen at the previous frame start
g_keys      equ 5A02h          ; byte  KEY_* bits read once per frame (1 = pressed)
g_moved     equ 5A03h          ; byte  1 = px/py/ang changed since the last setup_camera_b
g_npx       equ 5A04h          ; word  candidate position x (Q8) for the collision test
g_npy       equ 5A06h          ; word  candidate position y (Q8)
g_dticks    equ 5A08h          ; byte  ticks still to simulate in this frame
g_dx        equ 5A0Ah          ; word  per-tick step x = smul_shr(dirx, MOVE_SPEED, 8)  (signed Q8)
g_dy        equ 5A0Ch          ; word  per-tick step y = smul_shr(diry, MOVE_SPEED, 8)
g_mgx       equ 5A0Eh          ; word  collision margin x: +WALL_MARGIN / -WALL_MARGIN / 0 following the sign of g_dx
g_mgy       equ 5A10h          ; word  collision margin y
g_tx        equ 5A12h          ; word  collision test point x = candidate + margin (Q8)
g_ty        equ 5A14h          ; word  collision test point y
; ---- lane N5 (8 Nov 2026): mouse look + vertical look (src/next/mouse_next.asm; every use is inside IF DEFINED MOUSE_B).
; Bank 5 is zero at load, so opt_mouse_b defaults OFF (never auto-detected: floating-bus junk without an interface);
; horizon_row is set to 48 by start (main_b.asm).
opt_mouse_b equ 5A16h          ; byte  0 = mouse look OFF (default), 1 = ON (toggled by the I key)
mouse_last  equ 5A17h          ; byte  Kempston X counter (port 0FBDFh) seen at the previous frame
mouse_frac  equ 5A18h          ; byte  1/256 angle units not yet turned ((ang:mouse_frac) accumulator)
mouse_btn   equ 5A19h          ; byte  click latch: KEY_FIRE (left) / KEY_USE (right) bits, ORed into g_keys by read_keys
horizon_q8  equ 5A1Ah          ; word  horizon_row * 256: the low byte (5A1Ah, vl_pad) is ALWAYS 0, so `ld hl,(horizon_q8)`
vl_pad      equ 5A1Ah          ; byte  = 0 (set by start, never written again)
horizon_row equ 5A1Bh          ; byte  y-shear horizon row (default 48, clamped VL_MIN..VL_MAX): walk_b.asm wb_yproj_r,
                               ;       sprites_next.asm feet projection and draw_b.asm dr_row_params all project through it
mouse_ylast equ 5A1Ch          ; byte  Kempston Y counter (port 0FFDFh) seen at the previous frame
vl_frac     equ 5A1Dh          ; byte  1/256 rows of vertical look not yet applied ((horizon_row:vl_frac) accumulator)
mouse_dbnc  equ 5A1Eh          ; byte  I-key debounce: frames the key must be released before the next toggle (10)
VL_DEF      equ 48             ; default horizon row (= the pre-N5 constant 48*256 / 12288)
; ---- lane N6 (8 Nov 2026): HUD band + weapon as Next hardware sprites (src/next/hwspr_next.asm; every use is inside
; IF DEFINED HWSPR_B). Bank 5 is zero at load.
hw_key      equ 5A1Fh          ; byte  sprite attribute state on the FPGA: g_draw_mask bits 2,1 | 80h when g_wframe = 1
hw_dirty    equ 5A20h          ; byte  bit i = band sprite i (LoRes columns 16i..16i+15) repainted in HW_PBUF, upload pending
HW_PBUF     equ 7C00h          ; 1 KB  7C00h..7FFFh (free above THINGS_B 7800h..797Fh): the HUD band rows 88..95 painted here
                               ;       (128-byte stride, like the screen) and re-packed into sprite patterns 8..15 on upload
; ---- lane N7 (8 Nov 2026): zxnDMA / zxnDDMA plane pre-fill (src/next/dma_next.asm; every use is inside IF DEFINED DMAFILL).
; g_dma 5E2Bh (reserved by N4), dmf_rmax 5E2Ch, dmf_key 5E2Dh, dmf_y 5E2Fh, dmf_coltab 5E30h..5E8Fh: equates in dma_next.asm
; (5E22h..5EBFh were free; hud_next.asm uses 5EC0h.., FPSHUD 5EE0h.., the test hook 5EF0h..). Bank 5 is zero at load.
VL_MIN      equ 16             ; clamp: the horizon never reaches the top rows ...
VL_MAX      equ 80             ; ... nor the HUD band (rows 88..95, wb_rmax = 88)

; ---- code bank blocks poked by tools/nx_build.py
PALETTE     equ 9E00h          ; 512 bytes: <assets>/palette.bin (256 entries x 2 bytes, Next 9-bit write order)
; LEVEL (0B800h, nx_vars.inc) holds ONE mapc level (spec v0.2 section 1): 'K',1,32,32,sx,sy,start_angle,n_things + 1024 cells
LV_SX       equ LEVEL+4        ; byte  start cell x
LV_SY       equ LEVEL+5        ; byte  start cell y
LV_ANGLE    equ LEVEL+6        ; byte  start angle, 256 units per turn (E 0, S 64, W 128, N 192) -> ang = angle*4
LV_CELLS    equ LEVEL+8        ; 1024 cell codes, offset my*32 + mx ; 0 = walkable floor, anything else = solid
MAPC_W      equ 32
MAPC_H      equ 32

; ---- game constants (as main.asm / main_vars.inc: same speeds, same margin; no MAX_STEP in edition B)
MOVE_SPEED  equ 24             ; Q8 cells per 50 Hz tick (0.09 cell): step = (dir * MOVE_SPEED) >> 8
TURN_SPEED  equ 12             ; angle units per tick (1024 units = a full turn), ang wraps 0..1023
WALL_MARGIN equ 48             ; Q8 (0.1875 cell): the collision test point is the candidate pushed this far ahead
MAX_TICKS   equ 50             ; at most this many ticks (1 s) are simulated per frame

; ---- key bits in g_keys (bit numbers for bit/set, masks for and/cp)
KB_FWD      equ 0              ; Q or cursor up (7)
KB_BACK     equ 1              ; A or cursor down (6)
KB_LEFT     equ 2              ; O or cursor left (5)
KB_RIGHT    equ 3              ; P or cursor right (8)
KEY_FWD     equ 1
KEY_BACK    equ 2
KEY_LEFT    equ 4
KEY_RIGHT   equ 8

; ================================================================================================================
; lane N2 (5 Nov 2026): the GAME on edition B - things, vis list, door log, game state, sprite/HUD scratch.
; RAM 5C00h..5EFFh (free between the drawers' 5900h.., the walker's 5B00h.. and MAIN_STACK 5F00h).
; ================================================================================================================
THINGS_B    equ 7800h          ; 48 x 8: +0 type (0 none, 1..6 enemies, 16..22 items) +1/+2 x Q8 +3/+4 y Q8 +5 state (0 idle
                               ;         1 chase 2 attack 3 dead) +6 hp (ETAB col 0; items 30) +7 timer      (7800h..797Fh)
                               ; lane N3: moved from 5C00h (32 x 8) to the 2 KB above SCR_BOT (6000h + 48*128 = 7800h) that
                               ; build/next/main_b.sym showed unused (no symbol in 7800h..7FFFh); 5C00h..5CFFh is free now.
NTHINGS_B   equ 48             ; lane N3: level 08 places 36 things (N2 capped at 32 and dropped 4 silently)
VIS_B       equ 5D00h          ; 16 x 8: +0 depth Q8 word, +2 c0 word (s16), +4 w cols, +5 h rows, +6 feet row, +7 thing idx
VISMAX_B    equ 16             ; sorted far -> near (depth descending)                                      (5D00h..5D7Fh)
DOOR_LOG_B  equ 5D80h          ; 16 x 3: (cell ptr word, original code) of opened doors                     (5D80h..5DAFh)
; ---- game state (5DB0h..)
g_health    equ 5DB0h          ; byte  0..100
g_ammo      equ 5DB1h          ; byte  0..99
g_kkeys     equ 5DB2h          ; byte  b0 red key, b1 blue key
g_kills     equ 5DB3h          ; byte
g_level     equ 5DB4h          ; byte  0-based (NLEVELS_B = 8 since lane N3)
g_shield    equ 5DB5h          ; byte  0..100
g_door_cool equ 5DB6h          ; byte  steps until the next NEED A KEY message
g_fire_cool equ 5DB7h          ; byte  steps until the pistol may fire again (12 per shot)
g_wframe    equ 5DB8h          ; byte  weapon frame 0 idle 1 fire
g_step_t    equ 5DB9h          ; byte  low byte of ticks at the last game step
g_door_n    equ 5DBAh          ; byte  entries in DOOR_LOG_B
g_nvis      equ 5DBBh          ; byte  entries in VIS_B (from the last drawn frame)
g_draw_off  equ 5DBCh          ; byte  1 = sprites, weapon and HUD are NOT drawn (oracle A: pure engine frame)
g_msg       equ 5DBDh          ; byte  HUD message: 0 none, 1 NEED A KEY, 2 YOU DIED, 3 LEVEL CLEARED
g_msg_t     equ 5DBEh          ; byte  message ticks left (HUD band colour)
g_msg_tick  equ 5DBFh          ; byte  last ticks low byte seen by the HUD timer
g_music_tk  equ 5DC0h          ; word  ticks value at the last snd_isr call (music hook)
g_dead      equ 5DC2h          ; byte  deaths (statistics; oracle C reads it)
g_clears    equ 5DC3h          ; byte  level clears (statistics)
; ---- sprite transform / draw scratch (5DD0h..5DFFh, 5E00h..5E3Fh)
sp_dx       equ 5DD0h          ; word  tx - px
sp_dy       equ 5DD2h          ; word  ty - py
sp_p0       equ 5DD4h          ; 3 B   24-bit product scratch
sp_sign     equ 5DD7h          ; byte
sp_depth    equ 5DD8h          ; word
sp_lat      equ 5DDAh          ; word
sp_r        equ 5DDCh          ; word  R(d) = 2*RECIP[depth]
sp_feet     equ 5DDEh          ; byte
sp_h        equ 5DDFh          ; byte
sp_w        equ 5DE0h          ; byte
sp_c0       equ 5DE1h          ; word  s16
sp_idx      equ 5DE3h          ; byte  thing index
um_a        equ 5DE4h          ; word  umul16 scratch
um_b        equ 5DE6h          ; word
um_r0       equ 5DE8h          ; word
um_r1       equ 5DEAh          ; word
um_r3       equ 5DECh          ; byte
sd_depth    equ 5DEEh          ; word  draw_sprite_b: depth
sd_c0       equ 5DF0h          ; word  s16
sd_w        equ 5DF2h          ; byte
sd_h        equ 5DF3h          ; byte
sd_feet     equ 5DF4h          ; byte
sd_top      equ 5DF5h          ; word  s16 feet - h
sd_ustep    equ 5DF7h          ; word  4096 / w
sd_vstep    equ 5DF9h          ; word  6144 / h
sd_uacc     equ 5DFBh          ; word
sd_vacc0    equ 5DFDh          ; word  v accumulator at the first drawn row
sd_c        equ 5DFFh          ; byte  current column
sd_cend     equ 5E00h          ; byte  end column (exclusive)
sd_rstart   equ 5E01h          ; byte  first drawn row
sd_nrows    equ 5E02h          ; byte  rows drawn
sd_art      equ 5E03h          ; word  art base (C000h + id*512 or E800h + (id-18)*512)
sd_scr      equ 5E05h          ; word  screen address of (rstart, c)
g_tmp       equ 5E07h          ; word  scratch
e_dx        equ 5E09h          ; word  enemy AI: thing - player delta x
e_dy        equ 5E0Bh          ; word
l_x         equ 5E0Dh          ; word  los_check sample point
l_y         equ 5E0Fh          ; word
l_sx        equ 5E11h          ; word  los_check step
l_sy        equ 5E13h          ; word
g_ax        equ 5E15h          ; word  ahead_cell x
g_ay        equ 5E17h          ; word
hud_x       equ 5E19h          ; byte  HUD cursor column
hud_tmp     equ 5E1Ah          ; byte
; ---- keys (extends g_keys bits of read_keys)
KB_FIRE     equ 4              ; M (row 7Fh bit 2)
KB_USE      equ 5              ; SPACE (row 7Fh bit 0)
KEY_FIRE    equ 16
KEY_USE     equ 32
; ---- level things (mapc: after the 1024 cells)
LV_THINGS   equ LEVEL+8+1024   ; n_things (LEVEL+7) records of 3 bytes: type, x cell, y cell
; ---- sprite data: 16K bank 13 = 8K banks 26 (slot 6 while drawing sprites) and 27 (slot 7): tools/nx_sprites_b.py
SPR_BANK0   equ 26             ; ids 0..13 at C000h + id*512 (16 cols x 32 B, column-major, 0 = transparent)
SPR_BANK1   equ 27             ; pistol idle E000h, pistol fire E400h (32 cols x 32 B); ids 18..29 at E800h + (id-18)*512
SPR_BANK2   equ 30             ; lane N3: 16K bank 15 = 8K bank 30: boss ids 30..34 at C000h + (id-30)*512 (nx_sprites_b.py --out2),
                               ; paged into slot 6 only while draw_sprite_b draws a boss frame (draw_vis restores SPR_BANK0)
NLEVELS_B   equ 8              ; lane N3: 8 levels in 16K bank 14 (tools/nx_build.py --levels), loaded by load_level_b
LEVEL_BANK0 equ 28             ; 8K bank of level slots 0..3 (16K bank 14); slots 4..7 are in 8K bank 29; slot k at
                               ; 8K bank 28 + (k >> 2), offset (k & 3) * 2048; bytes 2045..2047 of a slot = ceil, ftex, ctex
LV_HDR3     equ LEVEL+2045     ; the 3 header bytes of the loaded slot (ceil, ftex, ctex) after load_level_b
g_lvreq     equ 5DCAh          ; byte  tool hook (tools/nx_game_video.py --level K): 1 = load level g_level + restart_level
                               ;       before the next game step; main_loop clears it
ms_best     equ 5DCCh          ; word  melee_scan: best (smallest) depth so far
ms_ptr      equ 5DCEh          ; word  melee_scan: THINGS_B pointer of the best candidate (0 = none)
STEP_B      equ 5              ; ticks per game step (10 Hz), kea48.asm STEP
g_freeze    equ 5DC4h          ; byte  game steps still frozen after YOU DIED / LEVEL CLEARED (20 = 2 s)
hud_col     equ 5E1Bh          ; byte  HUD drawing colour
e_dist      equ 5E1Ch          ; byte  enemy AI: Chebyshev distance in cells
sd_cnt      equ 5E1Dh          ; byte  draw_sprite_b row counter
e_sx        equ 5E1Eh          ; word  lane N3: et_chase candidate step x (melee fix a: both steps known before moving)
e_sy        equ 5E20h          ; word  lane N3: et_chase candidate step y
; ---- test hook (src/next/test_game_b.asm, tools/nx_test_game_b.py): 5EF0h..5EFFh
TGB_CMD     equ 5EF0h          ; byte  0 idle, 1 = setup_camera_b + game_frame, 2 = N game_ticks (TGB_N), 3 = restart_level
TGB_N       equ 5EF1h          ; byte  ticks to run for command 2
TGB_DONE    equ 5EF2h          ; byte  1 when the command finished
TGB_RES     equ 5EF4h          ; word  50 Hz ticks spent in the last command
g_hold      equ 5DC5h          ; byte  tool hook: 1 = game_frame waits after drawing (clean frame grab, tools/nx_game_video.py)
g_held      equ 5DC6h          ; byte  1 while game_frame is waiting in the hold
g_hold_tk   equ 5DC7h          ; word  ticks spent in holds (subtracted from the engine speed measurement)
g_draw_mask equ 5DC9h          ; byte  bit 0 sprites, bit 1 weapon, bit 2 HUD drawn by game_frame (7 = everything, the game)
