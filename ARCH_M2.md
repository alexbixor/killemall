# Kill'em all — M2 architecture & lane contracts (27 Oct 2026, 01:45Z)

Doom-style raycaster for the ZX Spectrum. Three editions share one code base: 48K (`src/48k/kea48.asm`, M1.1 engine,
12.2 fps start view / 9.5 fps face-to-wall, flicker-free back buffer), 128K (same engine + banks, AY music, shadow-screen flip),
Next later. Toolchain on this host: pasmo 0.5.3 (`pasmo --tapbas`), Python Z80 core in `.venv` (cycle-exact tests),
ZEsarUX 13.0 at `tools/zesarux/zesarux` driven over ZRCP (see `tools/run48.py`, `tools/demo48.py`, `tools/verify_m11.sh`), PIL 13 in `.venv`.
z88dk 2.4 exists in `tools/z88dk` but the game is hand assembly. Fuse headless does NOT work here — never try it.
Name is "Kill'em all" (never "Doom" anywhere in text, art or file names). The game will be loaded from SD card → file size and load time
are NOT constraints; RAM is (48K: ~8.3 KB free today, see memory map). Everything deterministic, measured, honest.

## Lanes (parallel, no file overlap). Each lane owns ONLY the files listed; never edit another lane's files.
| lane | owns | delivers |
|---|---|---|
| T1 gameplay | `src/48k/kea48.asm`, `tools/gen48.py`, `src/common/game.asm`, `src/common/sprites.asm`, `src/common/hud.asm`, `tools/test_game*.py` | z-buffer, scaled masked sprites, enemies (imp, zombie) with AI, pistol/shotgun fire, doors (auto-open on bump; locked need key), pickups, damage/death, exit → level clear, HUD (health/ammo/keys/kills, message line, weapon graphic). Calls `snd_fx`, `in_read`, `fe_*` only via the contracts below (use stub files `src/common/stubs.asm` with the same labels until integration). |
| T2 frontend+input | `src/common/frontend.asm`, `src/common/input.asm`, `tools/test_frontend.py`, `tools/fe_*.py` | menu over the title screen (START, MUSIC on/off, SOUND FX on/off, DETAIL high/low, FPS on/off, CONTROLS: redefine 6 keys / Kempston), `in_read`, options + key table in RAM, `fe_message`. |
| T3 sound | `src/common/beeper.asm`, `src/128k/ay.asm`, `tools/music/*`, `tools/test_sound.py` | 48K: beeper SFX (ids below) + a short original beeper menu tune; 128K: AY player (own compact format), 2 original tracks (menu, in-game), AY SFX on channel C; MP3 previews rendered from the register stream. |
| T4 128K build | `src/128k/kea128.asm`, `src/128k/loader128.asm`, `tools/make128.py`, `tools/build128.sh`, `tools/test_128.py` | 128K memory/bank map, tape loader (BASIC + bank loader, autostart), shadow-screen page flip from the ISR (no tearing, no COPYBUF to the visible screen), `snd_isr` hook, extra levels resident in banks. `make128.py` must transform ANY future `kea48.asm` mechanically (anchor on labels `start`, `isr`, `COPYBUF`, `render`, the `include` lines) — T1 keeps changing kea48.asm in parallel. |
| T5 content | `assets/**`, `tools/spritec.py`, `tools/scrconv.py`, `tools/mapview.py` (exists), `tools/test_content.py` | title screen 256x192 → `build/title.scr` (6912 B) + PNG preview, sprite art → `src/gen/sprites_data.asm` (format below), weapon art, levels 02 + 03 (`assets/levels/0N_*.txt`, compiled by `tools/mapc.py`, overhead PNGs via mapview, reachability clean), all original. |
| T6 integration (after T1–T5) | everything | merges, builds `build/killemall48_m2.tap` + `build/killemall128_m2.tap`, runs every lane test + geo48 + emulator runs (48k and 128k machines), PNG/MP4, `build/m2_report.md`. |

## Shared contracts (fixed now; a lane that MUST deviate writes the deviation at the top of its report)
### Labels every lane may call (implementations by the owning lane; `src/common/stubs.asm` = T1-written no-op stubs for local testing)
- `in_read` → A = action bits: b0 forward, b1 back, b2 turn left, b3 turn right, b4 fire, b5 use/open, b6 strafe left, b7 strafe right (optional). Reads keyboard via `in_keys` table or Kempston port 31 when `opt_joy`=1. ≤ 600 T. Pause/menu key is fixed: BREAK (CAPS+SPACE) → `in_read` also sets `in_break`=1.
- `in_keys`: 8 entries × 2 bytes (port high byte for the half-row, bit mask), order = action bits. Defaults Q A O P M SPACE Z X (write Z/X also if strafe unimplemented).
- `snd_fx` A = 1 shot, 2 door, 3 pickup, 4 player hurt, 5 enemy die, 6 menu tick, 7 locked door/no key, 8 enemy attack, 9 level clear, 10 player death. 48K: blocking beeper ≤ 40 ms, DI inside, EI on return, honours `opt_sfx`. 128K: enqueue, ISR plays, honours `opt_sfx`.
- `snd_music A` (0 = stop, 1 = menu track, 2 = game track) honours `opt_music`. 48K: in-game music is NOT required (CPU); 48K menu tune is driven by `snd_menu_tick` called from the menu loop every frame (non-blocking, ≤ 3,000 T).
- `snd_isr` (128K only, called from the IM2 ISR every frame, ≤ 4,000 T; 48K: `ret`).
- `fe_run` → runs the menu until START; returns with options set. `fe_message HL=text` (0-terminated, ≤ 28 chars) → HUD message line (T1's `hud_message` does the drawing; `fe_message` just forwards).
- `hud_init`, `hud_update` (redraw changed values only), `hud_message HL`, `hud_weapon A` (0 idle, 1 fire frame).
- State block (one file `src/common/state.asm`, written by T1 FIRST within its first 30 minutes, then frozen — other lanes read it; until it exists use these exact names): `health` (byte, 0..100), `ammo` (byte), `keys` (byte: b0 red, b1 blue), `kills` (byte), `level` (byte, 0-based), `opt_music`, `opt_sfx`, `opt_detail` (1 = dithered floor, 0 = plain), `opt_fps`, `opt_joy` (0 keyboard, 1 Kempston), `in_break`, `zbuf` (64 bytes: per ray column the wall virtual height clamped 0..255; 0 = none), `frames`, `ticks` (existing).
### Sprite data format (T5 produces with `tools/spritec.py`, T1 consumes)
Each sprite: 16 px wide (2 byte-columns), H rows (8..24). Layout column-major like the back buffer: for byte-column 0 then 1: H mask bytes (bit 1 = transparent) then H pixel bytes. Header per sprite: `db H`. Table `spr_table`: `dw` addresses, ids: 0 imp walk A, 1 imp walk B, 2 imp attack, 3 imp dead, 4 zombie walk A, 5 zombie walk B, 6 zombie attack, 7 zombie dead, 8 health, 9 ammo, 10 red key, 11 blue key, 12 barrel, 13 lamp. Weapon: 32 px wide (4 columns) × 24 rows, same layout, ids 14 pistol idle, 15 pistol fire, 16 shotgun idle, 17 shotgun fire. Sprites are 1-bit; colour comes from the window attributes (T1 may set BRIGHT/ink per cell for near enemies).
### Level format: existing `tools/mapc.py` output (K,1,w,h,sx,sy,angle,n_things + 1024 cells + things). Doors: cell 8 unlocked, 9 red, 10 blue, 11 secret, 12 exit. Max 16 things per level on 48K; 128K may hold 3+ levels resident.
### Front end flow: tape loads `title.scr` directly into 16384 (shown during load and kept), then the code block; `start` → `fe_run` (menu drawn in the bottom 6 attribute rows over the title screen) → game loop; BREAK in game → `fe_run` again (RESUME/options/QUIT); death → "YOU DIED" → restart level; exit → "LEVEL CLEARED" → next level or menu.

## 48K memory map today (M1.1) — T1 owns changes, must stay below 65008
BASIC loader 23755 (71 B) · BUF 24576..26623 · FTX 26624..27135 · (free 27136..27391) · FTY 27392..27903 · **free 27904..32767 (4.8 KB)** ·
code 32768..35331 · bands 35331..51979 · tables 51979..58111 · TEX 58112..60415 · level 60416..61479 · **free 61480..65007 (3.5 KB)** ·
stack top 65008 · IM2 65024..65280. Budget guidance: game+sprites+hud code ≤ 4 KB, sprite+weapon data ≤ 2 KB (T5 targets this), frontend+input ≤ 1.5 KB,
beeper ≤ 0.8 KB. If it does not fit: `gen48.py` knob to drop the BANDC_160/192 routines and even bands above 64 (generic loop fallback),
drop the fps text when `opt_fps`=0 builds, shrink FTX/FTY. Loading screen costs no RAM (lives in screen memory).
128K: T4 defines the bank map (bank 7 = shadow screen; 0xC000 window paged; everything the engine touches during a frame must be reachable).

## Verification (every lane): Python Z80-core unit test `tools/test_<lane>.py` exit 0 with printed T-state costs; T1 also `tools/geo48.sh` = 0 wrong columns at
all 9 views and `tools/verify_m11.sh`-style tearing grabs; emulator PNG via ZRCP for anything visual; `vision_analyze` on PNGs; reports ≤ 25 lines, real numbers,
explicit "not done" list. Pitfalls: inline heredocs via the terminal tool are fragile (write files, then run); outputs sometimes collapse to one line (redirect to
build/*.out and read back); foreground commands ≤ 600 s (background + notify for longer); edit asm via Python patch scripts or full rewrites, never sed; keep
backups in build/. No SSH, no Slack/Telegram/email, no package installs, no new downloads.
