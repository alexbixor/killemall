# Kill'em All — content architecture v1 (Next edition B) — lane C1, 8 Nov 2026

Scope: MANY enemy types (>= 24), weapons (>= 8), ammo types (>= 4), items (>= 16) on edition B WITHOUT touching the raycast
engine (walk_b.asm / draw_b.asm) and without costing fps when the content is not on screen. Spec + mocks only; every number
below carries its file:line. Mocks: build/night/C1_hud_mock.png, build/night/C1_weapon_mock.png (generator build/night/C1_mocks.py).

## 1. Today's hard limits (sourced)

| limit | today | where | target |
|---|---|---|---|
| enemy type byte | 1..6; anything >= 7 is "item" (no AI, shots pass, no hp) | game_b_next.asm:99 `cp 7` (things_init), :511 (things_tick), :837 (hitscan), :867 (melee_scan); main_b_vars.inc:74 | 1..63 |
| ETAB width | 8 B/type (`add a,a` x3) | game_b_next.asm:102-104, :525-527 (etab_row), :947-956 | 16 B/type |
| hp | byte in units of 10 hp ("pistol hits"), max 255 = 2550 hp; dec by 1 per hit | game_b_next.asm:111, :934-935 | keep (units of 10) |
| sprite base per type | SPRBASE_B byte table, 7 entries | game_b_next.asm:957-958 | bank + slot in ETAB v2 |
| frames per enemy type | 4, FIXED offsets +0 walk A, +1 walk B, +2 attack, +3 dead | sprites_next.asm:15, :571-587 | 6..8, table-driven |
| boss death | state 3 shows base+3 = id 33 "fall" for ever; id 34 never drawn | sprites_next.asm:573, docs/enemies_v1.md roster | fall then dead (flag) |
| sprite id address range | ids < 18 -> bank 26 C000h+id*512; 18..29 -> bank 27 E800h+(id-18)*512; >= 30 -> bank 30 C000h+(id-30)*512 (so ids 30..45 max) | sprites_next.asm:594-618 | per-type bank page |
| item types | 16..22 (ITSPR_B 7 entries); pickups 16..20 only; 21/22 decor | game_b_next.asm:429-432, :470-500, :959-960 | 64..127 (>= 16 real) |
| pickup effects | hard-coded: 16 health +25, 17 ammo +20 cap 99, 18/19 keys, 20 shield +50 | game_b_next.asm:467-500 | ITAB kind/param/amount |
| weapons | 1 (pistol), hard-coded cooldown 12, 1 hit, fire frame 5 steps (12 -> 7) | game_b_next.asm:783-786, :264-267 | 8, WTAB |
| ammo | one counter g_ammo 0..99 | main_b_vars.inc:84; game_b_next.asm:33, :178, :481-486 | 4 word counters |
| weapon art | pistol only: idle E000h, fire E400h (32 cols x 32 B) in bank 27 | main_b_vars.inc:156; sprites_next.asm:855-857; hwspr_next.asm:58-60 | per-weapon slots |
| level thing capacity | NTHINGS_B = 48 (silently truncated at 48; mapc allows 96 for "next") | main_b_vars.inc:78; game_b_next.asm:85-90; tools/mapc.py:23 | 64 (48 level + 16 projectile) |
| distinct enemy types per level | 8 (mapc cap) | tools/mapc.py:22 | 16 |
| level thing byte | u8 type, u8 x, u8 y; letters i z s c b k h a r u m o l only | tools/mapc.py:12, :21 | names via manifest |
| vis list | 16 entries/frame, far -> near | main_b_vars.inc:79-80 | keep |
| sprite banks in the .nex | 16K 2,4,5,8..15 = 8K pages 4,5,8..11,16..31 (header bitmap read from build/next/killemall_b.nex, RAM flag 0 = 768K) | tools/nx_build.py:219-234; tools/nx_nex.py header bytes 8,9,18+b | + content banks 32.. |
| free 8K pages | 0..3, 6, 7, 12..15 (12/13 = WB_LOG debug only, walk_b_vars.inc:58-60), 32..95 on a 768K Next (header RAM flag 0), 32..223 fully expanded | nx_nex.py:17; registers.txt:600 ("Pages range from 0 to 223") | use 32.. |
| hardware sprite patterns | 16 of 64 used: 0..7 weapon (idle/fire quadrants), 8..15 HUD band; pattern RAM 16 KB | hwspr_next.asm:9-15, :26-29; registers.txt:485 | 8 HUD + active weapon |
| hardware sprites | 12 of 128 (0..3 weapon, 4..11 band) | hwspr_next.asm:9-12; registers.txt:490 | 12 (or 14 at 48x32) |
| HUD fields | health 2.., shield 18.., ammo 44.. (2 digits), kills 84.., M 94..97, fps 100.. (FPSHUD), keys 112/120 | hud_next.asm:5-7, :51-93, :158-165 | + weapon icon, 3-digit ammo, 4 columns |
| free RAM for new vars | 5E22h..5EBFh (hud shadows 5EC0h..5EC8h, FPSHUD 5EE0h..5EE4h, hook 5EF0h..); 7A00h..7BFFh (THINGS_B 7800h..797Fh, HW_PBUF 7C00h) | hud_next.asm:17, :102-103; main_b_vars.inc:39, :74-78 | see section 3.7 |
| code room | code_end 9DF3h (< PALETTE 9E00h, 13 B left); 0A200h block ends 0A65Ch (420 B left below PLANES 0A800h) | build/next/main_b_n6.sym; N6_QUESTIONS.md section 7; main_b.asm:455-461 | new code goes to a paged bank or 0A65Ch.. |

Target: >= 24 enemy types, >= 8 weapons, >= 4 ammo types, >= 16 item types, 6..8 frames per enemy, engine untouched, 0 T when
off screen (tables are read only for things that are ticked or drawn; a type that is not placed costs only its bank in RAM).

## 2. Design

### 2.1 Type byte (THINGS_B +0 and the level file)
```
0        none
1..63    enemies   -> ETAB2[type]        (today's 1..6 keep their numbers and their first 8 table bytes)
64..127  items     -> ITAB[type-64]       (64..70 = today's 16..22 in the same order: health, ammo(bullets), red key, blue key, shield, barrel, lamp)
128..143 projectiles -> PTAB[type-128]   (runtime only: never in a level file)
144..255 reserved (decor without a table, scripted things)
```
The four `cp 7` tests become `cp 64` (ENEMY_END); pickups test `64 <= t < 128` and read ITAB.kind instead of 16..20. The level
.txt sources do not change: tools/mapc.py maps letters -> ids through assets/content.json (`CONTENT2`: items 16..22 -> 64..70).

### 2.2 ETAB v2 — 16 B per enemy type, 64 rows = 1 KB (index = type, `add a,a` x4)
```
+0  hp        units of 10 hp (255 max)      = ETAB_B +0  (game_b_next.asm:948)   unchanged
+1  step_q8   cells/step * 256               = +1                                  unchanged
+2  melee     damage                         = +2                                  unchanged
+3  ranged    damage (near)                  = +3                                  unchanged
+4  range     cells                          = +4                                  unchanged
+5  timer     steps                          = +5                                  unchanged
+6  wake      cells                          = +6                                  unchanged
+7  flags     b0 floating b1 ranged b2 melee b3 boss(fall frame) b4 fast(2 steps/tick) b5 noLOSneeded b6 explodes b7 reserved
+8  spr_bank  8K page holding the frames (26, 27, 30, 32..)
+9  spr_slot  first frame slot in that page: art = C000h + slot*512 (16 cols x 32 B column-major, 0 transparent, as today)
+10 frames    b0..b2 = count-1 (4..8); b3 attack B present (slot+4) b4 pain present (slot+5) b5 fall present (slot+6) b6 spare (slot+7)
              slot order: +0 walk A, +1 walk B, +2 attack A, +3 dead  (= today's fixed order, sprites_next.asm:571-587), +4 attack B,
              +5 pain, +6 fall, +7 spare  -> a 4-frame type is byte-for-byte today's behaviour
+11 proj      projectile type 0 = hit-scan (today's et_ranged), 128..143 = spawn PTAB[proj-128] at `timer`
+12 drop      item type 64..127 dropped at death (0 none), placed into the dead thing's own slot? no: a free slot 48..63 (else nothing)
+13 sound     sound id (future, AY lane): 0 none
+14 ranged_far damage beyond 3 cells (docs/enemies_v1.md: shotgunner 10) ; 0 = use +3 with the 50 % miss rule as today
+15 reserved  0
```
Rows 1..6 = docs/enemies_v1.md values + (bank, slot): imp (26,0) zombie (26,4) shotgunner (27,4) floater (27,8) brute (27,12) boss (30,0). Boss: the
frozen page 30 holds 30 31 32 33(fall) 34(dead), so flag b3 (boss) means "slot+3 = fall for the first 5 steps of state 3, then slot+4 = dead"
(docs/enemies_v1.md rule; today sprites_next.asm:573 shows 33 for ever) — the generic +6 fall slot is for NEW types only; the generator refuses b3
together with b5.
Cost: etab_row becomes 4 shifts (+4 T); every `(iy+n)` read is unchanged.

### 2.3 Sprite memory — one 8K page = 16 frames of 16x24 (512 B each)
- 2 enemy types at 8 frames per page; 24 types = 12 pages = 96 KB. Items 16 frames = 1 page (today's page 26 slots 8..13 hold 6 items).
- Frames stay where they are (G1 addresses frames by id): page 26 = ids 0..13 (slots 0..13), slots 14/15 free (2 items); page 27 = pistol idle
  slots 0/1, pistol fire slots 2/3 (1024 B each: 32 cols), ids 18..29 = slots 4..15; page 30 = boss ids 30..34 slots 0..4, slots 5..15 free
  (nx_sprites_b.py:33-36 BANK26/BANK27/BANK30). Ids 16/17 (shotgun) and 35/36 (chaingun) are in NO bank today (nx_sprites_b.py:12-13).
- New pages: 32 = weapons (shotgun idle 0/1, fire 2/3, chaingun idle 4/5, fire 6/7, weapons 4/5 at 8..15), 33 = weapons 6/7 + 4 spare slots,
  34..45 = enemy types 7..30 (two per page), 46 = items 64+8..64+23 (16 slots), 47 = projectiles (16 frames: 4 types x 4). .nex: 16K banks 16..23
  (= 8K pages 32..47), RAM flag 0 (768K) still true, header bitmap has room to bank 111.
- Paging rule in draw_sprite_b: `ld a,(iy+8) ; nextreg 56h,a` before computing sd_art = C000h + slot*512 (replaces the id compares of
  sprites_next.asm:594-618), slot 6 restored ONCE after draw_vis (today: per boss entry, :601-603). Cost: nextreg a = 17 T, nextreg imm = 20 T
  -> 16 entries worst case 16 x 17 + 20 = 292 T per frame (< 1 % of one 64x96 sprite blit). Do NOT sort VIS_B by bank: VIS_B is drawn far -> near
  (sprites_next.asm:14) and nearer sprites overwrite farther ones; a bank sort would break that order. Items/projectiles: ITAB/PTAB carry the same
  (bank, slot) pair, so the painter has one path for all three.
- Weapon art stays in slot 7 (E000h) during sprites (sprites_next.asm:44-45 page SPR_BANK1 there); under HWSPR_B it is only read at init / weapon
  switch, so slot 7 can be re-paged for the upload and restored to FLOOR_BANK.

### 2.4 WTAB — 16 B per weapon, 8 rows = 128 B (index = weapon 0..7, keys 1..8)
```
+0  ammo_type   0 bullets 1 shells 2 cells 3 rockets ; 0FFh = none (fists/chainsaw)
+1  ammo_shot   rounds per shot (pistol 1, shotgun 1, chaingun 1, plasma 1, rocket 1, BFG 40)
+2  cooldown    steps (pistol 12, shotgun 18, chaingun 3, plasma 4, rocket 20)                 (today: game_b_next.asm:783)
+3  damage      units of 10 hp per hit/pellet (pistol 1, shotgun 1 per pellet, chaingun 1, plasma 2, rocket 8 splash)
+4  pellets     1, shotgun 7
+5  spread      half-width in screen columns of the pellet fan (shotgun 12: pellet k aims at column 64 + ((k*7+ticks) mod 25) - 12)
+6  kind        b0 projectile (else hit-scan) b1 auto (hold M) b2 melee (range 1) b3 splash b4 pierce b5 silent b6 fire-frame 2 (alternating) b7 res.
+7  range       cells (0 = unlimited, hit-scan today is unlimited: game_b_next.asm:800-825)
+8  proj        projectile type 128.. for kind b0
+9  art_bank    8K page of the 32x24 (or 48x32) software frames (pistol 27, shotgun/chaingun 32)
+10 art_slot    idle at slot, fire at slot+2 (1024 B each at 32x24; 1536 B = 3 slots each at 48x32: idle slot, fire slot+3)
+11 hw_pats     N6 path: pattern base of the 8 (4 idle + 4 fire) patterns, or 0FFh = upload-on-switch into patterns 0..7
+12 hud_icon    12x6 icon id in the HUD icon strip (one 8K page slot shared: 16 icons x 72 B)
+13 sound       fire sound id
+14 fire_steps  fire frame shown for N steps (5 today: game_b_next.asm:264-267, cooldown-7)
+15 reserved
```
Hardware-sprite weapon (N6): 64 patterns - 8 HUD = 56 -> 7 weapons resident at 8 patterns each (weapon 8 does not fit), OR re-upload the active
weapon's 8 patterns on switch: 8 x 256 B through port 5Bh with `otir` (21 T/byte) = 2048 x 21 + 8 index outs ~= 43.2k T = 1.5 ms at 28 MHz (12 ms at
3.5 MHz) once per switch; hwspr_update (hwspr_next.asm:171-203) is unchanged because the patterns keep numbers 0..7. CHOSEN: upload-on-switch
(unbounded weapon count, zero attribute changes). At 48x32: 3x2 = 6 patterns per frame, 12 per weapon, 3 KB upload (~65k T), 4 resident otherwise;
sprites 0..5 instead of 0..3 (hw_attr_tab grows by 2 rows, HW_SPR_B0 = 6).
Keys 1..8: rows F7FEh (1..5) and EFFEh (6..0) added to read_keys (main_b.asm); weapon switch sets g_fire_cool = 5 (no instant double fire).

### 2.5 Ammo
```
AMMO_MAX: db/dw 200, 50, 300, 50      (bullets, shells, cells, rockets)  x2 with the backpack flag (g_backpack)
g_ammo16  4 words  (cells 300 > 255 -> words; HUD prints 3 digits)
g_ammo (5DB1h, main_b_vars.inc:84) stays as the LOW byte MIRROR of ammo[WTAB[g_weapon].ammo_type] so the OFF-build HUD/oracle code is untouched.
```
fire_action: `ammo[wt.ammo_type] >= wt.ammo_shot` else click; subtract; cooldown = wt.cooldown. Pickups: ITAB kind 2 (ammo) with param = ammo
type, amount = count (bullets clip 10 / box 50, shells 4 / 20, cells 20 / 100, rockets 1 / 5 = 8 of the 16 item types); kind 7 backpack: max x2 and
+1 clip of each. HUD: weapon icon at columns 28..39, current ammo 3 digits at 44..55 (gold 143), 4 one-pixel columns at 58/60/62/64 rows 1..6 (gold
= current type, bone 222 others, 6 rows = full), everything else where it is (hud_next.asm:5-7).

### 2.6 Projectiles (floater spit, boss cannon, rockets, plasma)
THINGS_B slots 48..63 (NTHINGS_B 48 -> 64 = 512 B at 7800h..79FFh; 7A00h..7BFFh stays free, HW_PBUF at 7C00h untouched: main_b_vars.inc:39, :74).
things_init_b keeps copying <= 48 level things (game_b_next.asm:88-90) and zeroes 48..63. Record: +0 type 128..143, +1/+2 x, +3/+4 y (Q8), +5 owner
(0 player, 1 enemy) | frame phase b4..b7, +6 angle (0..255, 256/turn), +7 ttl steps. PTAB 8 B: +0 speed_q8 (64 = 0.25 cell/step), +1 damage,
+2 spr_bank, +3 spr_slot (4 frames: fly A/B, hit, fade), +4 flags (b0 splash b1 gravity b2 light), +5 radius_q8, +6 sound, +7 res. proj_tick runs after
things_tick: move, cell_ptr_bc solid -> hit frame + ttl 2; near_player (owner 1) -> e_hurt; owner 0 -> any living enemy within radius -> enemy_hit x
damage. build_vis draws them through the same (bank, slot) path (they are depth-sorted for free). 16 in flight max; spawn fails silently when full.

### 2.7 RAM map of the new variables (free area hud_next.asm:17 "5E22h..5EDFh free")
```
5E30h g_weapon (0..7)   5E31h g_owned (bit per weapon)   5E32h g_backpack   5E33h g_wsw_dbnc (key debounce)
5E34h..5E3Bh g_ammo16[4] words   5E3Ch hud_sh_weapon   5E3Dh..5E44h hud_sh_ammo16[4] words   5E45h g_nproj
```
Tables: ETAB2 1 KB + ITAB 64 x 8 = 512 B + WTAB 128 B + PTAB 16 x 8 = 128 B + AMMO_MAX 8 B = 1.8 KB: too big for the 13 B below PALETTE and the 420 B
below PLANES -> page them: 8K page 3 (16K bank 1, free, loaded by the .nex) at slot 1? No: slot 1 is RECIP (main_b.asm:51). Put them in page 31 (16K
bank 15 upper half, in the .nex already, all zero: nx_build.py:230-234 pads sprites2 to 16K) and read them through slot 6 while the game ticks
(game_tick runs before game_frame pages the sprite banks; slot 6 is WALL_BANK0 then, restored by nextreg 56h,16 at the end of game_tick: +40 T).
Simplest alternative (C2 decides with a measurement): ETAB2 at 7A00h..7BFFh is only 512 B = 32 types; not enough -> page 31.

### 2.8 Level format (tools/mapc.py) — what the tool must accept
- Cells unchanged. Things: the existing letters (mapc.py:21) keep their meaning; items emit 64..70 under `--content2` (16..22 otherwise).
- New header lines `#thing=<char>=<name>` bind any free printable char (not in CELL/THING/'@') to a manifest name for that level; `#thing=T=cyberdemon`.
- Names resolve through assets/content.json (`enemies[].name` -> id, `items[].name` -> 64 + index); unknown name = compile error.
- Caps from the manifest: distinct enemy types per level 16 (today 8, mapc.py:22), things 48 (= NTHINGS_B; today 96 is a lie: game_b_next.asm:88-90).
- Reserved and frozen: type ids 1..6 and 64..70, frame ids 0..36 at today's (bank, slot) (section 2.3) so no placed thing and no G1 frame moves.

### 2.9 Manifest — assets/content.json (one file; tools/nx_content.py generates everything from it)
Generates: src/gen/content_b.inc (ETAB2, ITAB, WTAB, PTAB, AMMO_MAX as `db`, plus EQUs ENEMY_END 64, NTHINGS_B2 64), build/next/assets_b/bank_NN.bin per
8K page (tools/nx_sprites_b.py --from-manifest), build/next/assets_b/frames.json = the G1 pipeline's frame list (id, file, bank, slot, w, h) so G1 reads it
instead of its hard-coded 0..36, and tools/mapc.py's name table. Schema with the six existing enemies:
```json
{"version": 1, "edition": "b",
 "frames": {"size": [16, 24], "weapon_size": [32, 24], "frozen_ids": 37},
 "ammo": [{"id": 0, "name": "bullets", "max": 200}, {"id": 1, "name": "shells", "max": 50},
          {"id": 2, "name": "cells", "max": 300}, {"id": 3, "name": "rockets", "max": 50}],
 "enemies": [
  {"id": 1, "name": "imp", "letter": "i", "hp": 30, "step": 0.06, "melee": 10, "ranged": 0, "range": 0, "timer": 25, "wake": 10,
   "flags": ["melee"], "bank": 26, "slot": 0, "frames": {"walk_a": 0, "walk_b": 1, "attack": 2, "dead": 3}, "ink": 174},
  {"id": 2, "name": "zombie", "letter": "z", "hp": 30, "step": 0.06, "melee": 15, "timer": 25, "wake": 10, "flags": ["melee"],
   "bank": 26, "slot": 4, "frames": {"walk_a": 4, "walk_b": 5, "attack": 6, "dead": 7}, "ink": 94},
  {"id": 3, "name": "shotgunner", "letter": "s", "hp": 30, "step": 0.05, "ranged": 20, "ranged_far": 10, "range": 6, "timer": 20, "wake": 10,
   "flags": ["ranged"], "bank": 27, "slot": 4, "frames": {"walk_a": 18, "walk_b": 19, "attack": 20, "dead": 21}, "ink": 142},
  {"id": 4, "name": "floater", "letter": "c", "hp": 60, "step": 0.04, "ranged": 15, "range": 8, "timer": 30, "wake": 10,
   "flags": ["floating", "ranged"], "projectile": "spit", "bank": 27, "slot": 8, "frames": {"walk_a": 22, "walk_b": 23, "attack": 24, "dead": 25}, "ink": 190},
  {"id": 5, "name": "brute", "letter": "b", "hp": 120, "step": 0.07, "melee": 25, "timer": 20, "wake": 10, "flags": ["melee"],
   "bank": 27, "slot": 12, "frames": {"walk_a": 26, "walk_b": 27, "attack": 28, "dead": 29}, "ink": 206},
  {"id": 6, "name": "boss", "letter": "k", "hp": 400, "step": 0.05, "melee": 35, "ranged": 20, "range": 8, "timer": 15, "wake": 10,
   "flags": ["ranged", "melee", "boss"], "projectile": "cannon", "bank": 30, "slot": 0,
   "frames": {"walk_a": 30, "walk_b": 31, "attack": 32, "dead": 34, "fall": 33}, "ink": 222},
  {"id": 7, "name": "<new>", "letter": null, "bank": "auto", "frames": {"walk_a": "auto", "...": "G1 pipeline allocates ids >= 37"}}],
 "items": [
  {"id": 64, "legacy_id": 16, "name": "health", "letter": "h", "kind": "health", "amount": 25, "bank": 26, "slot": 8},
  {"id": 65, "legacy_id": 17, "name": "ammo", "letter": "a", "kind": "ammo", "param": "bullets", "amount": 20, "bank": 26, "slot": 9},
  {"id": 66, "legacy_id": 18, "name": "red_key", "letter": "r", "kind": "key", "param": 1, "bank": 26, "slot": 10},
  {"id": 67, "legacy_id": 19, "name": "blue_key", "letter": "u", "kind": "key", "param": 2, "bank": 26, "slot": 11},
  {"id": 68, "legacy_id": 20, "name": "shield", "letter": "m", "kind": "shield", "amount": 50, "bank": 26, "slot": 8},
  {"id": 69, "legacy_id": 21, "name": "barrel", "letter": "o", "kind": "decor", "bank": 26, "slot": 12},
  {"id": 70, "legacy_id": 22, "name": "lamp", "letter": "l", "kind": "decor", "bank": 26, "slot": 13},
  {"id": 71, "name": "shells", "kind": "ammo", "param": "shells", "amount": 4, "bank": 46, "slot": 0}, "... 72..79: ammo boxes, weapons, backpack, powerups"],
 "weapons": [
  {"id": 0, "key": "1", "name": "pistol", "ammo": "bullets", "per_shot": 1, "cooldown": 12, "damage": 1, "pellets": 1, "spread": 0, "kind": ["hitscan"],
   "bank": 27, "slot": 0, "frames": {"idle": 14, "fire": 15}, "hw_pats": "switch", "icon": 0},
  {"id": 1, "key": "2", "name": "shotgun", "ammo": "shells", "per_shot": 1, "cooldown": 18, "damage": 1, "pellets": 7, "spread": 12, "kind": ["hitscan"],
   "bank": 32, "slot": 0, "frames": {"idle": 16, "fire": 17}, "icon": 1},
  {"id": 2, "key": "3", "name": "chaingun", "ammo": "bullets", "per_shot": 1, "cooldown": 3, "damage": 1, "pellets": 1, "spread": 2, "kind": ["hitscan", "auto"],
   "bank": 32, "slot": 4, "frames": {"idle": 35, "fire": 36}, "icon": 2},
  {"id": 3, "key": "4", "name": "rocket", "ammo": "rockets", "cooldown": 20, "kind": ["projectile", "splash"], "projectile": "rocket", "bank": 32, "slot": 8},
  {"id": 4, "key": "5", "name": "plasma", "ammo": "cells", "cooldown": 4, "kind": ["projectile", "auto"], "projectile": "plasma", "bank": 32, "slot": 12},
  {"id": 5, "key": "6", "name": "...", "bank": 33, "slot": 0}, {"id": 6, "key": "7", "bank": 33, "slot": 4}, {"id": 7, "key": "8", "bank": 33, "slot": 8}],
 "projectiles": [
  {"id": 128, "name": "spit", "speed": 0.25, "damage": 15, "bank": 47, "slot": 0}, {"id": 129, "name": "cannon", "speed": 0.3, "damage": 20, "bank": 47, "slot": 4},
  {"id": 130, "name": "rocket", "speed": 0.5, "damage": 8, "flags": ["splash"], "bank": 47, "slot": 8}, {"id": 131, "name": "plasma", "speed": 0.6, "damage": 2, "bank": 47, "slot": 12}],
 "banks": {"26": "frozen ids 0..13", "27": "frozen pistol + ids 18..29", "30": "frozen boss 30..34", "32": "weapons 1,2,3,4", "33": "weapons 5..7",
           "34-45": "enemies 7..30 two per page", "46": "items 71..86", "47": "projectiles 128..131"}}
```
Generator invariants (oracles of lane C2): for ids 1..6 the first 8 bytes of ETAB2 == ETAB_B (game_b_next.asm:950-956); the frozen (bank, slot)
pairs reproduce nx_sprites_b.py's BANK26/BANK27/BANK30 offsets; frames.json lists exactly ids 0..36 at those offsets before any new type is added.

## 3. Sprite-bank budget (from the .nex header of build/next/killemall_b.nex: 16K banks 2,4,5,8..15)
| 8K page | content | status |
|---|---|---|
| 4,5 | code image (16K bank 2) | used |
| 8,9 | tables + ISR, RECIP (16K bank 4) | used |
| 10,11 | screen + variables (16K bank 5) | used |
| 16..23 | walls.bin (16K banks 8..11) | used |
| 24,25 | floors.bin (16K bank 12) | used |
| 26,27 | sprites_b.bin: 14 + 12 frames + pistol (16K bank 13) | used: 26 slots 14,15 free; 27 full |
| 28,29 | 8 level slots (16K bank 14) | used |
| 30,31 | sprites2_b.bin: boss (16K bank 15) | 30 slots 5..15 free; 31 EMPTY (8 KB zero) -> tables (2.7) |
| 0..3, 6, 7, 14, 15 | not in the .nex (12/13 = WB_LOG debug) | free but low: leave alone |
| 32..95 | not in the .nex; 768K-Next range (nx_nex.py:17 RAM flag 0) | 64 pages = 512 KB free |
| 96..223 | only on a 1792K/2 MB Next (registers.txt:600) | not used by design |
After 24 enemy types at 8 frames (12 pages 34..45) + 2 weapon pages (32, 33) + 1 item page (46) + 1 projectile page (47): 16 new pages = 128 KB
= 16K banks 16..23 -> .nex grows from 11 to 19 banks (176 -> 304 KB), 48 pages (384 KB) still free below the 768K line. 32x48 "Doom-class" frames
(G1b) would quadruple: 4 frames per page -> 24 types x 8 frames = 48 pages: still inside 32..95 but with nothing left; decide before C6.

## 4. Migration plan — every lane byte-identical when `CONTENT2` is undefined (pasmo --equ CONTENT2=1 via nx_build.py --equ)
Reference durations: N4 2 h 52 (N4_clock.txt 10:04 -> 12:56), N5 2 h 39 (13:01 -> 15:40), N6 3 h 32 (15:46 -> 19:18): ~3 h per code lane with oracles.
| lane | work | h | oracles |
|---|---|---|---|
| C2 tables + manifest | assets/content.json (6 enemies, 7 items, pistol), tools/nx_content.py -> src/gen/content_b.inc + frames.json + bank .bins; ETAB2 at page 31; etab_row x16; `cp 7` -> `cp ENEMY_END` (64) with items 64..70 (mapc --content2); nx_build.py --banks DIR (any 8K page) | 3 | A identity: killemall_b.nex md5 unchanged without CONTENT2. B generator: ETAB2[1..6][0..7] == bytes of game_b_next.asm:950-956 (Python reads both); frozen offsets == nx_sprites_b.py tables. C nx_test_game_b.py --only ab ALL PASS with CONTENT2 (same frames). D 8 levels compiled both ways: things identical except 16..22 -> 64..70 |
| C3 weapons + ammo | WTAB, 4 x word ammo, fire_action table-driven (pellets/spread, auto), keys 1..3 pistol/shotgun/chaingun with frames 14..17, 35/36 in page 32, HUD icon + 3-digit ammo + 4 columns (software band and HW_PBUF both, hud_next.asm painters), HW pattern upload-on-switch | 5 | A identity. B unit (kosarev z80 as nx_test_hwspr.py): pistol path -> same g_ammo/g_fire_cool/g_wframe sequence as today for 100 steps. C shotgun 7 pellets: a Python model of the fan vs the Z80 on 20 seeded shots. D emulator: switch 1-2-3, screenshots of the 3 weapons + band (oracle E-style save-screen), fps gate unchanged (25) |
| C4 bank map + paging | draw_sprite_b reads (iy+8)/(iy+9), one nextreg 56h per entry, restore once per draw_vis; ITAB/PTAB art path; nx_sprites_b.py --from-manifest writes 16 frames/page | 3 | A identity. B frames: reference renderer (nx_test_game_b.py) ALL PASS on 8 levels. C T: oracle-E style count of nextreg sites per frame <= g_nvis + 1. D boss on level 08 draws from page 30 as before (frame md5 vs N3F) |
| C5 projectiles | NTHINGS_B 64, PTAB, proj_tick, spawn from et_ranged when ETAB2+11 != 0 and from WTAB kind b0, 4 frames in page 47 | 4 | A identity. B Python model of a spit: position per step, wall stop, hit -> e_hurt equals the Z80 (nx_test_game_b.py style ticks). C 7A00h..7BFFh and HW_PBUF untouched (sym + memory diff). D floater on level 03 visibly spits (video frames) |
| C6 new enemy types 7..12 | content.json rows 7..12, G1 pipeline art via frames.json (8 frames each), pages 34..36, level 06/07 placements with `#thing=` | 4 (+G1 art time) | A identity. B frames.json round trip: every new frame at its (bank, slot). C reference renderer ALL PASS. D level 06 video: new types visible, fps >= 25 with 6 on screen |
Total ~19 h over 5 lanes; C2 first, C3 || C4 after it, C5 after C4, C6 last.

## 5. Mocks (looked at with the image tool; details in build/night/C1_QUESTIONS.md)
- build/night/C1_hud_mock.png — band at 4x: digits (health 100 red, shield 50 blue, ammo 300/24 gold, kills 12 bone) read clearly; weapon icons
  (12x6) read as "some gun" only: chaingun = bumpy bar, shotgun = bar + tab; the 4 one-pixel ammo columns are visible but their heights are
  guesswork (6 rows of range); key icons read as colour blocks only; M legible. At 1x (128x96 inside 4x) nothing new is readable except the digits.
- build/night/C1_weapon_mock.png — N6 composed frame with pistol erased: shotgun 32x24 and 48x32 both read as "a vertical black thing" (today's
  1-bit shotgun art is drawn barrel-up; it does not read at any size — redraw with a receding barrel), chaingun reads at 32x24 and well at 48x32
  (3 barrel ends + belt). 48x32 is NOT blocky (same pixel grid) but covers a third of the view height and reaches the wall base; no erase seam visible.
  Recommendation: keep 32x24 for v1 (zero sprite/pattern changes), make 48x32 an art-size option in the manifest (`frames.weapon_size`) for later.
