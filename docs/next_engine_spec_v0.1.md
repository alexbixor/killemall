# Kill'em all — Spectrum Next engine ("option A"), contract v0.1 (4 Nov 2026, 21:45Z)

This document is the ONE source of truth shared by all lanes working on the Next engine tonight.
Every number here is exact integer arithmetic. The Python reference (`tools/nx_ref.py`) and the Z80N code
(`src/next/*.asm`) must produce IDENTICAL frame bytes for the same inputs. If something here is ambiguous,
the Python reference decides and this file gets corrected (orchestrator only edits this file).

## 0. Vocabulary
- cell: one map square, side 1.0. heights are measured in cells.
- Q8: fixed point, value*256 stored in 16 bits (unsigned unless said signed). Q12: value*4096 (16 bits).
- H32: a height in 1/32 cell, signed 8-bit (int8). 0.25 cell step = 8, hall floor -0.5 = -16, hall ceiling 2.0 = 64.
- row: screen row 0..95 of the LoRes layer; column c: 0..127.
- smul_shr(a, b, s) = sign-magnitude multiply then shift: r = (|a|*|b|) >> s ; result = -r if exactly one of a,b is negative else r.
  (All signed products use THIS definition, never floor division, so Z80 and Python agree bit for bit.)
- ROW(y_q8) = clamp((y_q8 + 127) >> 8, 0, 96) with y_q8 a signed value; a surface from y_a (top) to y_b (bottom) covers rows [ROW(y_a), ROW(y_b)) (half-open).

## 1. Screen, palette
- LoRes layer 128x96, 8 bits per pixel (nextreg 0x15 bit 7 = 1), CPU 28 MHz (nextreg 7 = 3).
- Row r address: r < 48: 0x4000 + r*128 ; r >= 48: 0x6000 + (r-48)*128. Pixel (c, r) = row address + c.
- Palette: 256 entries, index = material*16 + level (16 materials, 16 brightness levels, level 15 = brightest).
  Asset `build/next/assets/palette.bin` = 256 x 2 bytes in Next 9-bit write order (byte0 RRRGGGBB, byte1 bit0 = blue lsb).
  Programmed through nextreg 0x43 (select ULA/LoRes palette, auto-inc), 0x40 (index 0), 0x44 (two writes per entry).
- Palette index 0 = "void" (black). Material ids are in `build/next/assets/manifest.json` (lane B publishes it).

## 2. Camera and rays
- Player position px, py: Q8 unsigned (cells). Map is 32 x 16 cells (x 0..31, y 0..15). Angle a: 0..1023, 0 = +x (east), 256 = +y (south, map row increasing).
- SIN[a] = round(256*sin(2*pi*a/1024)), COS[a] = round(256*cos(2*pi*a/1024)) (int16, tables of 1024 words each, stored little-endian).
- dirx = COS[a], diry = SIN[a]; plane half-vector plx = -SIN[a], ply = COS[a] (length 1.0 -> 90 degree field of view, F = 64 rows per cell at distance 1).
- cam_c = 2*c + 1 - 128 (c = 0..127; odd numbers -127..127; units of 1/128).
- Ray for column c: rx = dirx + smul_shr(plx, cam_c, 7) ; ry = diry + smul_shr(ply, cam_c, 7). (signed Q8, range about -512..512)
- RECIP[i] = min(65535, 65536 // i) for i = 1..4095, RECIP[0] = 65535. (8 KB table of 16-bit words, index 0..4095)
- ddx = RECIP[min(4095, |rx|)] ; ddy = RECIP[min(4095, |ry|)]  (Q8 of 1/|rx|, capped). If |rx| == 0 use 65535.
- sx = -1 if rx < 0 else +1 ; sy likewise.
- Initial side distances (Q8, saturating at 65535): fx = px & 255, fy = py & 255 (fractions).
  sdx = (fx * ddx) >> 8 if rx < 0 else ((256 - fx) * ddx) >> 8 ; sdy likewise with fy, ry.
- Start cell mx = px >> 8, my = py >> 8. eye = floor(cell(mx,my)) + 22 (H32; i.e. eye is 0.6875 cell above the floor the player stands on).
- Horizon row HOR = 48 (constant tonight; later HOR = 48 - pitch).

## 3. Projection
- For a boundary at perpendicular depth d (Q8, clamped to 8..4095): R(d) = min(65535, 2 * RECIP[d]).
- A height h (H32) at depth d appears at y_q8 = 48*256 - (h - eye) * R(d)   [exact integer product; (h - eye) is a signed int, R unsigned].
  y_q8 is clamped to the signed 16-bit range [-32768, 32767] before further use (both sides).
- Texture rows per screen row for a vertical face at depth d: dv_q8 = d >> 1  (because 32 texels per cell and 64/d rows per cell).

## 4. The column walk (one per column c, done for c = 0..127)
State: ytop = 0, ybot = 96 (rows [ytop, ybot) still open), cur = cell(mx, my), dprev = 8, step counter 0.
Loop (at most 48 steps):
  1. if sdx < sdy: d = sdx ; sdx = sat_add(sdx, ddx) ; mx += sx ; side = 0
     else:         d = sdy ; sdy = sat_add(sdy, ddy) ; my += sy ; side = 1
     d = max(d, 8). If d > 4095 (or mx/my outside the map): go to EXHAUST.
  2. FLOOR of cur: ya = ROW(y(cur.floor, d)), yb = ROW(y(cur.floor, dprev)); a = max(ya, ytop), b = min(yb, ybot);
     if a < b: PLANE_ADD(c, cur.floor, cur.ftex, a, b). Then ybot = min(ybot, max(ytop, ya)).
  3. CEILING of cur: ya = ROW(y(cur.ceil, dprev)), yb = ROW(y(cur.ceil, d)); a = max(ya, ytop), b = min(yb, ybot);
     if a < b: PLANE_ADD(c, cur.ceil, cur.ctex, a, b). Then ytop = max(ytop, min(ybot, yb)).
  4. nxt = cell(mx, my) (outside the map = solid stone).
     Texture column: hit = (py + smul_shr(ry, d, 8)) if side == 0 else (px + smul_shr(rx, d, 8)) ; u = (hit & 255) >> 3   (0..31).
     Shade: s = 0 if d < 384 else 1 if d < 768 else 2 if d < 1536 else 3 ; if side == 1: s = min(3, s + 1).
  5. if nxt.solid: WALL(c, cur.ceil, cur.floor, nxt.wtex, d, u, s); ZBUF[c] = d; STOP.
  6. if nxt.floor > cur.floor: WALL(c, nxt.floor, cur.floor, nxt.wtex, d, u, s); ybot = min(ybot, max(ytop, ROW(y(nxt.floor, d)))).
  7. if nxt.ceil < cur.ceil: WALL(c, cur.ceil, nxt.ceil, nxt.ltex, d, u, s); ytop = max(ytop, min(ybot, ROW(y(nxt.ceil, d))))   (ltex = the cell's lintel texture).
  8. if ytop >= ybot: ZBUF[c] = d; STOP.
  9. cur = nxt; dprev = d; continue.
EXHAUST (48 steps or d > 4095 or left the map): if ytop < ybot: VOID(c, ytop, ybot) (solid palette index 0). ZBUF[c] = 4095. STOP.

WALL(c, h_top, h_bot, tex, d, u, s) — split into 1-cell texture tiles aligned to world height 0:
  t_top = h_top
  while t_top > h_bot:
      tile_base = ((t_top - 1) // 32) * 32          (floor division; the tile that contains the height just below t_top)
      t_bot = max(h_bot, tile_base)
      y_a = y(t_top, d), y_b = y(t_bot, d)          (signed, clamped to int16)
      ra = max(ROW(y_a), ytop), rb = min(ROW(y_b), ybot)
      if ra < rb:
          v_top = tile_base + 32 - t_top            (0..31 texel rows)
          dv = d >> 1                                (Q8)
          v_first = v_top*256 + smul_shr((ra*256 + 128) - y_a, dv, 8)
          count = rb - ra
          v_last = v_first + (count - 1) * dv ; if v_last > 8191: v_first -= (v_last - 8191) ; if v_first < 0: v_first = 0
          DRAW_PIECE(c, ra, count, tex, s, u, v_first, dv)
      t_top = t_bot
  Pixel i (0..count-1) of a piece = WALLTEX[tex][s][u][ (v_first + i*dv) >> 8 ]   (texel row 0..31 guaranteed by the guard above).

## 5. Planes (floors and ceilings) and their fill
- PLANE_ADD(c, h, tex, a, b): rows a..b-1 of column c show the horizontal surface at height h with texture tex.
  Bookkeeping is free (Doom-style visplanes: top[128]/bottom[128] per (h, tex); split when a column is used twice),
  because the pixel colour depends only on (h, tex, c, row). Suggested capacity: 12 planes of 258 bytes.
- For a plane row y: dy = 2*(y - 48) + 1 (odd, signed), dh = eye - h (H32, signed). Floors: dh > 0 and dy > 0; ceilings: dh < 0 and dy < 0 (anything else is empty by construction).
  RD[k] = min(65535, 65536 // k) for k = 1..255, RD[0] = 65535 (Q8 of 256/k).  d = (|dh| * RD[|dy|]) >> 6  (24-bit product; d is Q8 depth) ; if d > 4095: the row is painted palette index 0 (too far) and the maths below is skipped.
  Shade s from d with the same thresholds as walls (no side darkening).
  DX = smul_shr(d, plx, 14) (signed Q8, cells per column) ; DY = smul_shr(d, ply, 10) (signed Q12).
  XB = (px + smul_shr(d, dirx, 8) - smul_shr(DX, 127, 1)) & 0xFFFF ; YB = ((py << 4) + smul_shr(d, diry, 4) - smul_shr(DY, 127, 1)) & 0xFFFF.
  Pixel (c, y): wx = (XB + c*DX) & 0xFFFF ; wy = (YB + c*DY) & 0xFFFF ; u = (wx >> 4) & 15 ; v = (wy >> 8) & 15 ;
  colour = FLOORTEX[tex][s][u*16 + v].   (Z80: index byte = (L and F0h) or (D and 0Fh) with HL = wx, DE = wy — the benchmark's trick.)
- VOID(c, a, b): rows a..b-1 of column c = palette index 0.
- Draw order inside a frame does not matter for the result (ranges never overlap); suggested: wall pieces during the walk, planes after.

## 6. Assets (lane B writes them, everyone reads them)
- `build/next/assets/walls.bin`: 16 wall textures x 4 shades x 4 pages x 256 bytes (64 KB).
  Byte offset of texel (tex t, shade s, column u, row v) = ((t*4 + s)*4 + (u >> 3))*256 + (u & 7)*32 + v.
  (A 256-byte page holds 8 texture columns of 32 rows: Z80 reads it with D = page, H = v + 32*(u & 7) as in the benchmark.)
- `build/next/assets/floors.bin`: 8 floor/ceiling textures x 4 shades x 256 bytes (8 KB). Offset of texel (f, s, u, v) = (f*4 + s)*256 + u*16 + v.
- Shades: s = 0 full brightness; s = 1, 2, 3 = each palette level reduced by 3, 6, 9 (never below level 1 unless the texel was level 0). Lane B may refine but must document in manifest.json.
- `build/next/assets/palette.bin` (see 1), `build/next/assets/manifest.json`: {"materials": {name: id}, "walls": {name: id}, "floors": {name: id}, "shade_rule": "..."}.
- Textures must follow the pixel-art rule from the mock-up reviews: ONE tone per brick/slab (no per-texel noise), mortar lines, bevel highlights, moss as whole-brick patches; vault ceiling as ribs (no gold studs).

## 7. Map (lane R writes `build/next/assets/level0.bin` + `level0.json` with `tools/nx_level.py` from the ASCII below)
- 32 x 16 cells, 4 bytes per cell, row-major (offset = (my*32 + mx)*4): byte0 floor H32 (int8), byte1 ceil H32 (int8),
  byte2 = (solid << 7) | (ltex << 4) | wtex   (wtex 0..15 = riser/wall texture, ltex 0..7 = lintel texture), byte3 = ftex (bits 0-3) | ctex << 4.
- Outside the map = solid stone (wtex 0). Solid cells: byte0 = byte1 = 0, byte3 = 0.
- Fixed texture ids (lane B implements exactly these): WALLS 0 stone, 1 brick, 2 moss (stone with moss patches), 3 iron, 4 wood door,
  5 dais (riser face: gold nosing at the top, dark shadow line, bone blocks), 6 lintel (dark course, gold trim, stone), 7 altar face (bone, gold diamond),
  8 blue stone, 9 bone wall (skulls), 10 banner (red cloth on stone), 11 iron-banded door, 12 torch bracket on stone, 13 crumbling stone, 14 vines on stone, 15 black.
  FLOORS 0 flag (grey flagstones), 1 plaster ceiling with beams, 2 vault ceiling (ribs, no studs), 3 tread (bone slabs), 4 altar top (gold diamond on bone), 5 water, 6 cobble, 7 blood-stained flag.
- Legend (floor H32, ceil H32, ftex, ctex, wtex, ltex): '.' corridor (0, 32, 0, 1, 5, 6) ; 'a' step (-8, 64, 3, 2, 5, 6) ; 'H' hall (-16, 64, 0, 2, 5, 6) ;
  's' dais step 1 (-8, 64, 3, 2, 5, 6) ; 't' dais step 2 (0, 64, 3, 2, 5, 6) ; 'U' altar (8, 64, 4, 2, 7, 6) ; 'w' water (-24, 64, 5, 2, 0, 6) ; 'L' low passage (0, 20, 0, 1, 0, 6) ;
  solid: '#' stone 0, 'B' brick 1, 'M' moss 2, 'P' moss 2, 'I' iron 3, 'W' wood 4.
```
BBBBBBBBBBBBBBBBBBBBBBBB########
B......BMMMMMMMMMMMMMMMM#......#
B......WMMMMMMMUUUUUMMMM#......#
B......BMMMMMMtttttttMMM#......#
BBBB.BBBMMMMMsssssssssMM#......#
#..#.MMMMMMMMHHHHHHHHHMM#......#
#..#.......aHHHHHHHHHHHM#......#
#..#.......aHHHHHHHwwHHM#......#
#..#.......aHHHHHHHwwHHM##..####
#..#.MMMMMMMMHHHHHHHHHMM#......#
#..#.MMMMMMMHHHHHHHHHMMM#......#
#..LLLL#################.......#
#.......I.....I................#
#########IIIIIIIIIIIIIIII......#
###########################....#
################################
```
(16 rows x 32 columns; `nx_level.py` must assert that.)

## 8. Memory map of the running engine (8 KB MMU slots; nextreg 0x50..0x57 select 8K banks; 16K bank n = 8K banks 2n, 2n+1)
- slot 0 (0x0000-0x1FFF) = 8K bank 8: 0x0000 `jp start_stub` (3 bytes, unused), 0x0038 the IM1 ISR (below), 0x0800 SIN (1024 words), 0x1000 COS (1024 words),
  0x1800 RD (256 words), 0x1A00 ZBUF (128 words), 0x1B00-0x1FFF free. (ALREADY DONE by the orchestrator: `tools/nx_tables.py` -> `build/next/tables_bank4.bin` = 16 KB for 16K bank 4 = 8K banks 8 and 9; importable lists SIN, COS, RD, RECIP.)
- slot 1 (0x2000-0x3FFF) = 8K bank 9: RECIP (4096 words = exactly 8 KB).
- slots 2,3 (0x4000-0x7FFF) = 16K bank 5: LoRes screen (0x4000-0x57FF rows 0-47, 0x6000-0x77FF rows 48-95); 0x5800-0x5FFF variables (see `src/next/nx_vars.inc`) + stacks;
  0x7800-0x7FFF free.
- slots 4,5 (0x8000-0xBFFF) = 16K bank 2: code from 0x8000; planes table at 0xA800 (15 planes x 258 B = 0xA800-0xB71F); level data at 0xB800 (2 KB).
- slot 6 (0xC000-0xDFFF) = wall texture bank, switched per piece: 8K bank 16 + (t >> 1) holds textures 2k and 2k+1; page byte = 0xC0 + (t & 1)*16 + s*4 + (u >> 3). (nextreg 0x56.)
- slot 7 (0xE000-0xFFFF) = 8K bank 24 = floors.bin (8 KB): page byte = 0xE0 + f*4 + s. (nextreg 0x57.)
- The .nex loads 16K banks: 5 (screen+vars), 2 (code), 4 (tables), 8..11 (= 8K 16..23: walls.bin, 64 KB), 12 (= 8K 24,25: floors.bin in the first 8 KB). Entry PC = 0x8000, SP = 0x5F00.
  After entry the code itself sets nextreg 0x50 = 8, 0x51 = 9, 0x56 = 16, 0x57 = 24 (the .nex loader leaves ROM in slots 0,1).
- ISR (IM1, at 0x0038 in bank 8), exact code — SP may point into screen RAM while the floor drawer runs, so it swaps stacks:
```
        ld (isr_sp),sp
        ld sp,ISR_STACK
        push hl
        ld hl,(ticks)
        inc hl
        ld (ticks),hl
        pop hl
        ld sp,(isr_sp)
        ei
        reti
```
  ticks = 0x5808, isr_sp = 0x580C, ISR_STACK = 0x5FF0 (see nx_vars.inc). Main stack top 0x5F00. fps = frames*50/ticks.
- Frame start: `planes_reset`; for each column call the walker (which calls draw_piece / plane_add / void_fill); then `planes_flush`; frames += 1. Single-buffered for now (tearing accepted tonight; double-buffering with the 2nd LoRes bank is a later lane).

## 9. Test interface between lanes
- The reference writes, per scene, `build/night/ref/<scene>.frame.bin` (12288 bytes, row-major 128x96 palette indices), `<scene>.png` (4x, palette applied), `<scene>.records.json` (ordered list of DRAW_PIECE / PLANE_ADD / VOID calls with all arguments and ZBUF), `<scene>.camera.json` (px, py, a, eye, mx, my).
- Scenes: `hall` (px=0x0F80 (15.5), py=0x0780 (7.5), a=512 (looking -x, back up the step into the corridor)), `corridor` (px=0x0480 (4.5), py=0x0680 (6.5), a=0 (down the corridor towards the step and the hall)), `steps_down` (px=0x0A60 (10.375), py=0x0733 (7.2), a=40), `altar` (px=0x0F4D (15.3), py=0x0766 (7.4), a=768 (looking -y at the dais)).
- Lane D1 (walker) compares its DRAW_PIECE/PLANE_ADD/VOID call list with `<scene>.records.json` (same order per column; within a column the order is: floor plane, ceiling plane, then wall pieces top-down per WALL call, in the order of section 4).
- Lane D2 (drawers) replays `<scene>.records.json` through its routines and compares the LoRes screen with `<scene>.frame.bin` (0 differing bytes required).

## 10. Call interface between the walker (lane D1) and the drawers (lane D2) — `src/next/nx_vars.inc` has the addresses
- The walker fills a parameter block in RAM and CALLs: `draw_piece` (pc_c, pc_ra, pc_count, pc_tex, pc_s, pc_u, pc_v word, pc_dv word),
  `plane_add` (pl_c, pl_h int8, pl_tex, pl_a, pl_b), `void_fill` (vd_c, vd_a, vd_b). The drawers may destroy all registers except SP (and IY if they say so in a comment); the walker saves what it needs.
- Frame-level: `planes_reset` before the first column, `planes_flush` after the last. `walk_frame` (lane D1) does the whole frame including those two calls and writes ZBUF.
- Both lanes assemble stand-alone test programs with stubs for the other side; the orchestrator links the real ones in `src/next/main.asm` (`include` of walk.asm and draw.asm).
- Source files contain NO `org`; `src/next/main.asm` / the test wrappers set `org 8000h` and include `nx_vars.inc` first.
