; walk_vars.inc - lane D1 (column walker) scratch equates inside 5840h..58FEh (WALK_VARS, nx_vars.inc)
; plus the test-only call-log layout used by walk_stubs.asm / test_walk.asm / tools/nx_test_walk.py.
; Include AFTER nx_vars.inc. No code here, only equates.

; ---- per-column ray state (spec section 2)
w_c         equ 5840h          ; byte  column c 0..127
w_rx        equ 5842h          ; word  rx = dirx + smul_shr(plx, cam_c, 7)   (signed Q8)
w_ry        equ 5844h          ; word  ry = diry + smul_shr(ply, cam_c, 7)
w_ddx       equ 5846h          ; word  ddx = RECIP[min(4095, |rx|)]
w_ddy       equ 5848h          ; word  ddy
w_sdx       equ 584Ah          ; word  side distance x (Q8, saturating at 65535)
w_sdy       equ 584Ch          ; word  side distance y
w_sx        equ 584Eh          ; byte  +1 / -1 stored as 01h / 0FFh
w_sy        equ 584Fh          ; byte
; ---- walk state (spec section 4)
w_mx        equ 5850h          ; byte  current cell x (unsigned; >= 32 means outside the map)
w_my        equ 5851h          ; byte  current cell y (>= 16 means outside)
w_ytop      equ 5852h          ; byte  rows [ytop, ybot) are still open
w_ybot      equ 5853h          ; byte
w_side      equ 5854h          ; byte  0 = crossed an x boundary, 1 = a y boundary
w_steps     equ 5855h          ; byte  remaining steps (48 down to 1)
w_d         equ 5856h          ; word  depth of the boundary just crossed (Q8, 8..4095)
w_dprev     equ 5858h          ; word  previous depth (8 at the start)
w_cur       equ 585Ah          ; 4 bytes: copy of cur = (floor, ceil, byte2, byte3)
w_nxt       equ 585Eh          ; 4 bytes: copy of nxt
w_u         equ 5862h          ; byte  texture column 0..31
w_s         equ 5863h          ; byte  shade 0..3
w_ya        equ 5864h          ; byte  plane row ya
w_yb        equ 5865h          ; byte  plane row yb
; ---- WALL() arguments and locals (spec section 4, WALL pseudo-code)
w_htop      equ 5866h          ; byte  int8 h_top
w_hbot      equ 5867h          ; byte  int8 h_bot
w_wtex      equ 5868h          ; byte  texture id passed to DRAW_PIECE
w_ttop      equ 5869h          ; byte  int8 t_top
w_tbot      equ 586Ah          ; byte  int8 t_bot
w_tbase     equ 586Bh          ; byte  int8 tile_base
w_ra        equ 586Ch          ; byte  ra
w_rb        equ 586Dh          ; byte  rb
w_yaq       equ 586Eh          ; word  y_a (signed Q8, clamped to int16)
w_vraw      equ 5870h          ; word  v_first before the 8191 guard (magnitude saturated at 0FFFFh)
w_dv        equ 5872h          ; word  dv = d >> 1
w_vtop      equ 5874h          ; byte  v_top = tile_base + 32 - t_top
; ---- multiply scratch (umul32)
mul_p0      equ 5876h          ; word  al*bl
mul_p3      equ 5878h          ; word  ah*bh
w_camc      equ 587Ah          ; word  cam_c = 2*c + 1 - 128 sign-extended

; ---- test wrapper / stubs only (not used by the engine proper)
T_CAL       equ 58F2h          ; word  ticks taken by the calibration loop (27263093 T-states; ~48 ticks at 28 MHz)
T_TICK0     equ 58F4h          ; word  ticks before the timing frames
T_N         equ 58F6h          ; byte  timing frames still to run
LOG_COUNT   equ 58F8h          ; word  number of records logged in the current frame (dropped ones included)
LOG_PTR     equ 58FAh          ; word  next free byte of the log
T_DTICKS    equ 58FCh          ; word  ticks spent in the N timing frames
LOG_ON      equ 58FEh          ; byte  0 = stubs return at once (timing frames), 1 = stubs log
DONE_FLAG   equ 58FFh          ; byte  1 when test_walk has finished
; call log: slots 6,7 (0C000h..0FFFFh) are mapped to 8K banks LOG_BANK, LOG_BANK+1 by test_walk.asm.
; (Not 0A000h as first planned: the steps_down scene produces 14.4 KB of records, which would overrun LEVEL at 0B800h.)
LOG_BASE    equ 0C000h
LOG_END     equ 0FF00h         ; a record is dropped (but still counted) when LOG_PTR >= LOG_END
LOG_BANK    equ 12             ; 8K banks 12,13 = 16K bank 6 (unused by the engine)
; test blocks in the code bank, poked into the .nex image by tools/nx_test_walk.py
SCENE       equ 9F00h          ; px word, py word, ang word, nframes byte (timing frames after the logged one)
MULTEST     equ 9E00h          ; byte n (<= 48), then n x (a lo, a hi, b lo, b hi, s): smul_shr vectors; s = 0FFh -> umul32(a, b)
MULRES      equ 9F10h          ; n x 4 bytes: DEHL result little-endian (L, H, E, D)
YTEST       equ 9C00h          ; byte n (<= 64), then n x (h, eye, d lo, d hi): yproj + row_of vectors
YRES        equ 9D10h          ; n x 3 bytes: y lo, y hi, row
