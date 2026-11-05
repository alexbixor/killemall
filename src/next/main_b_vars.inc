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
