; walk_b_vars.inc - lane N1: scratch equates of the edition B walker (src/next/walk_b.asm) inside 5B00h..5BFFh
; (spec v0.2; WALK_VARS 5840h..58FFh belongs to option A's walk.asm and is NOT used, so both walkers can coexist)
; plus the test-only equates of src/next/test_walk_b.asm / tools/nx_test_walk_b.py.  Include AFTER nx_vars.inc.
; No code here, only equates.

; ---- level parameters (bytes; the build tool / test wrapper stores them; spec v0.2 section 1)
wb_ceil     equ 5B00h          ; byte  CEIL: ceiling height H32 (32 or 64)
wb_ftex     equ 5B01h          ; byte  FTEX: floor texture id (floors.bin)
wb_ctex     equ 5B02h          ; byte  CTEX: ceiling texture id
; ---- per frame (walk_frame_b prologue)
wb_aplx     equ 5B04h          ; word  |plx|  (0..256)
wb_aply     equ 5B06h          ; word  |ply|
wb_splx     equ 5B08h          ; byte  1 if plx < 0 else 0
wb_sply     equ 5B09h          ; byte  1 if ply < 0 else 0
wb_fx       equ 5B0Ah          ; byte  fx = px & 255
wb_fy       equ 5B0Bh          ; byte  fy = py & 255
wb_ptr0     equ 5B0Ch          ; word  LEVEL + 8 + my0*32 + mx0 (cell pointer of the camera cell)
; ---- per column
wb_c        equ 5B10h          ; byte  column 0..127
wb_side     equ 5B11h          ; byte  0 = hit an x boundary, 1 = a y boundary
wb_rx       equ 5B12h          ; word  rx (signed Q8)
wb_ry       equ 5B14h          ; word  ry
wb_sdy      equ 5B16h          ; word  initial sdy (parked while sdx is computed)
wb_d        equ 5B18h          ; word  d (Q8, 8..4095) of the hit
wb_r        equ 5B1Ah          ; word  R(d) = 2*RECIP[d]
wb_rowa     equ 5B1Ch          ; byte  a = ROW(y_floor(d))
wb_rowb     equ 5B1Dh          ; byte  b = ROW(y_ceil(d))
wb_row32    equ 5B1Eh          ; byte  ROW(y(32, d))   (CEIL = 64 only: the row between the two wall tiles)
wb_plo      equ 5B1Fh          ; byte  low byte of px / py used for the texture column
wb_yc       equ 5B20h          ; word  y(CEIL, d) exact (clamped int16)
wb_y32      equ 5B22h          ; word  y(32, d) exact (CEIL = 64 only)
wb_pra      equ 5B24h          ; byte  piece: ra
wb_prb      equ 5B25h          ; byte  piece: rb
wb_pya      equ 5B26h          ; word  piece: y_a
wb_vraw     equ 5B28h          ; word  piece: v_first before the 8191 guard
wb_mp0      equ 5B2Ah          ; word  umul32 scratch
wb_mp3      equ 5B2Ch          ; word  umul32 scratch
wb_sxn      equ 5B2Eh          ; byte  1 if rx < 0 (sx = -1) else 0
wb_syn      equ 5B2Fh          ; byte  1 if ry < 0 (sy = -1) else 0
wb_ddy      equ 5B30h          ; word  ddy = RECIP[|ry|] (parked while the x axis is set up)
wb_rmax     equ 5B32h          ; byte  lane N4 (8 Nov 2026): first row the engine must NOT write (96 = whole frame; 88 when
                               ;       game_frame draws the HUD band at rows 88..95, which then persists between frames).
                               ;       0 (bank 5 zero at load) is read as 96 by walk_frame_b.
wb_wclip    equ 5B33h          ; word  lane N4: 0 = none, else -> 64 bytes: top[32], bottom[32] of the weapon's opaque run per
                               ;       screen column 48..79 (0,0 = unclipped column). Columns whose run ends at row 88 are
                               ;       clipped at top[c]: the engine never paints under the weapon there (bug 1, no flash).
wb_rmaxc    equ 5B35h          ; byte  per-column row limit of the current column (wb_rmax or the weapon clip)

; ---- test wrapper / stubs only (test_walk_b.asm, tools/nx_test_walk_b.py)
WB_T_CAL    equ 5BF0h          ; word  ticks of the calibration loop
WB_T_TICK0  equ 5BF2h          ; word  ticks before the timing frames
WB_T_DTICKS equ 5BF4h          ; word  ticks spent in the N timing frames
WB_T_N      equ 5BF6h          ; byte  timing frames still to run
WB_LOG_ON   equ 5BF7h          ; byte  0 = stubs return at once, 1 = stubs log
WB_LOG_COUNT equ 5BF8h         ; word  records logged in the current frame (dropped ones included)
WB_LOG_PTR  equ 5BFAh          ; word  next free byte of the log
WB_DONE     equ 5BFFh          ; byte  1 when test_walk_b has finished
WB_LOG_BASE equ 0C000h         ; call log in slots 6,7 = 8K banks WB_LOG_BANK, WB_LOG_BANK+1 (16K bank 6, unused by the engine)
WB_LOG_END  equ 0FF00h
WB_LOG_BANK equ 12
WB_SCENE    equ 9F00h          ; px word, py word, ang word, nframes byte, ceil byte, ftex byte, ctex byte (poked by the tool)
