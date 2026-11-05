# KILL'EM ALL — design (26 Oct 2026)

A first-person "Doom-look" shooter for the ZX Spectrum in three editions that share one game design and
one map/asset pipeline, each using everything its machine offers. Own title, own art, own code — no Doom
assets or trademarks.

| Edition | Machine | Renderer | Window | Target fps | Sound | Enemies | Output |
|---|---|---|---|---|---|---|---|
| 48K | 3.5 MHz Z80, 48 KB | ray-cast walls, 1-bit textures, attribute shading per 8×8 cell, fixed-point tables | 128×96 px (16×12 cells) + HUD | 8–10 | beeper: gunfire, door, hurt, pickup; title tune | 3 types, 2 frames each | `.tap` |
| 128K | 3.5 MHz Z80, 128 KB paged | same core; bigger window, double-buffered on the two shadow screens, enemy frames and levels in banks 1/3/4/6 | 160×120 px (20×15 cells) + HUD | 10–12 | AY-3-8912: 3-channel music (title + in-game), sampled-feel SFX on channel C | 6 types, 4 frames each, bosses | `.tap` |
| Next | Z80N 28 MHz, 1.75 MB, Layer 2, sprites, DMA, copper | ray-cast walls + floor/ceiling casting, 256-colour textures, Layer 2 320×256 framebuffer, hardware sprites for enemies/weapon/pickups, palette fades, DMA fills | 256×192 game + ULA/Layer 2 HUD | 25–30 | Turbo Sound Next (3× AY) music + 8-bit sample SFX via DAC | 8 types, 8 frames each, 3 bosses | `.nex` |

## Shared design
- **Map:** 32×32 grid per level, 8 levels; cells: wall textures 1–7, door (locked by red/blue key), secret
  door, exit; sprites: enemies, ammo, health, armour, keys, barrels (explode). Levels are text files in
  `assets/levels/*.txt` compiled to binary by `tools/mapc.py` for all three editions.
- **Player:** 16.16 fixed position, 8-bit angle (256 = 360°). Weapons: pistol, shotgun, chaingun. Keys:
  QAOP / cursor + M fire, SPACE open, Kempston & Sinclair joystick. Stats: health, armour, ammo, keys.
- **Ray engine (common idea, per-edition code):** one ray per screen column, DDA on the grid, lookup
  tables for sin/cos/tan/fisheye, wall-height table from distance. 48K/128K render to a hidden buffer
  and blit by `ldi`/`push` stacks; Next casts straight into Layer 2 with the floor/ceiling pass per row.
- **Enemies:** state machines (idle, chase, attack, pain, die), line-of-sight by ray, melee or
  projectile, 2.5D billboard sprites scaled from the same distance table as walls, depth-sorted vs walls
  per column (z-buffer of wall distances per column).
- **Attract / loading:** 48K/128K get a proper loading screen (SCR), ROM-timed loader, BASIC stub;
  Next boots from `.nex` with a Layer 2 title and palette fade.
- **Toolchain:** z88dk 2.4 (`zcc +zx`, `+zx -subtype=128`, `+zxn`) for game logic in C, hot loops in
  Z80/Z80N assembly (`z80asm`); `pasmo` for standalone asm bits; `tools/` Python for maps, textures,
  sprite packing, AY music conversion, tape building, and headless runs (Fuse + Xvfb → PNG/MP4, ZEsarUX
  for the Next). Each milestone: screenshots + MP4 + the `.tap`/`.nex` to Alex.

## Milestones
1. **M1 48K engine:** test map, textured walls, movement, HUD skeleton, fps counter → screenshots.
2. **M2 48K game:** enemies, weapons, doors/keys, pickups, beeper SFX, 3 levels, loading screen → tap + MP4.
3. **M3 128K:** paging, double buffer, bigger window, AY music/SFX, 6 enemies, 8 levels → tap + MP4.
4. **M4 Next:** Layer 2 renderer with floors/ceilings, sprites, Turbo Sound, samples, 8 levels → nex + MP4.
5. **M5 polish:** difficulty, secrets, end screens, README, release zip (3 files + manual).

## Layout
```
src/common/   game.h, map format, level logic shared (C)
src/48k/      render48.asm, beeper.asm, main48.c
src/128k/     render128.asm, ay.asm, bank.asm, main128.c
src/next/     renderL2.asm, sprites.asm, tsnext.asm, mainnext.c
assets/       levels/*.txt, textures/*.png, sprites/*.png, music/*
tools/        mapc.py, texpack.py, sprpack.py, tapbuild.py, run_fuse.sh, run_zesarux.sh, z88dk/, zesarux/
build/        48k/killemall48.tap  128k/killemall128.tap  next/killemall.nex  + png/mp4 per milestone
```
