; main_vars.inc - lane M: game-loop variables (5A00h..5AFFh, the lane M scratch area) and game constants.
; Include AFTER nx_vars.inc and walk_vars.inc. No code here, only equates.

; ---- game loop state (main.asm)
g_last_tick equ 5A00h          ; word  value of ticks (5808h, IM1 ISR) seen at the previous frame start
g_keys      equ 5A02h          ; byte  KEY_* bits read once per frame (1 = pressed)
g_moved     equ 5A03h          ; byte  1 = px/py/ang changed since the last setup_camera
g_npx       equ 5A04h          ; word  candidate position x (Q8) for the collision test
g_npy       equ 5A06h          ; word  candidate position y (Q8)
g_dticks    equ 5A08h          ; byte  ticks still to simulate in this frame
g_cfloor    equ 5A09h          ; byte  floor (H32, int8) of the cell the player stands on (collision rule)
g_dx        equ 5A0Ah          ; word  per-tick step x = smul_shr(dirx, MOVE_SPEED, 8)  (signed Q8)
g_dy        equ 5A0Ch          ; word  per-tick step y = smul_shr(diry, MOVE_SPEED, 8)
g_mgx       equ 5A0Eh          ; word  collision margin x: +WALL_MARGIN / -WALL_MARGIN / 0 following the sign of g_dx
g_mgy       equ 5A10h          ; word  collision margin y
g_tx        equ 5A12h          ; word  collision test point x = candidate + margin (Q8)
g_ty        equ 5A14h          ; word  collision test point y

; ---- code bank blocks poked by tools/nx_build.py
PALETTE     equ 9E00h          ; 512 bytes: build/next/assets/palette.bin (256 entries x 2 bytes, Next 9-bit write order)

; ---- game constants
MOVE_SPEED  equ 24             ; Q8 cells per 50 Hz tick (0.09 cell): step = (dir * MOVE_SPEED) >> 8
TURN_SPEED  equ 12             ; angle units per tick (1024 units = a full turn), ang wraps 0..1023
MAX_STEP    equ 12             ; H32: the destination floor must be within +-MAX_STEP of the current floor (steps yes, walls/drops no)
WALL_MARGIN equ 48             ; Q8 (0.1875 cell): the collision test point is the candidate position pushed this far in the
                               ; direction of travel, so the eye never gets closer than this to a blocking cell (no wall clipping)
MAX_TICKS   equ 50             ; at most this many ticks (1 s) are simulated per frame (a stalled frame must not teleport the player)
START_PX    equ 0480h          ; start = the 'corridor' scene of spec section 9: (4.5, 6.5) facing east (a = 0)
START_PY    equ 0680h
START_ANG   equ 0

; ---- key bits in g_keys (bit numbers for bit/set, masks for and/cp)
KB_FWD      equ 0              ; Q or cursor up (7)
KB_BACK     equ 1              ; A or cursor down (6)
KB_LEFT     equ 2              ; O or cursor left (5)
KB_RIGHT    equ 3              ; P or cursor right (8)
KEY_FWD     equ 1
KEY_BACK    equ 2
KEY_LEFT    equ 4
KEY_RIGHT   equ 8
