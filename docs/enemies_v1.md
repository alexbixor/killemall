# Kill'em all — enemy roster v1 (lane E, 5 Nov 2026)

Six enemy types for the 128K / Next editions (the 48K gets types 1..3). Types 1 and 2 are EXACTLY today's behaviour,
read from the code: `src/common/sprites.asm` things_init sets hp = 30 for every thing; `game_f.asm` step_axis moves
15/256 = 0.0586 ≈ 0.06 cell per 10 Hz step; `game_e.asm` wakes within Chebyshev distance < 10 cells with LOS
(los_check, 8 samples), attacks when |dx|,|dy| < 0.7 cell (near_player07), timer 25 steps, damage 10 (imp) / 15 (zombie),
snd 8 at the hit then snd 4 (player hurt), shield absorbs first. Types 3..6 follow build/night/E_BRIEF.md.

## Roster (numbers lane G puts into the table)

| type | name | hp | step (cells/step) | step_q8 | melee dmg | ranged dmg | ranged range (cells) | attack timer (steps) | wake radius (cells) | sprite base | frames (walk A, walk B, attack, dead[, fall]) | height class | 48K/128K ink |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | imp (bloater) | 30 | 0.06 | 15 | 10 | 0 | 0 | 25 | 10 | 0 | 0, 1, 2, 3 | feet on floor | magenta (today) |
| 2 | zombie | 30 | 0.06 | 15 | 15 | 0 | 0 | 25 | 10 | 4 | 4, 5, 6, 7 | feet on floor | green (today) |
| 3 | shotgunner | 30 | 0.05 | 13 | 0 | 20 at <= 3 cells, 10 at 4..6 | 6 (holds at 2..6) | 20 | 10 | 18 | 18, 19, 20 (muzzle flash), 21 | feet on floor | yellow 0x60 |
| 4 | floater | 60 | 0.04 | 10 | 0 | 15 (spit) | 8 | 30 | 10 | 22 | 22, 23 (bob), 24 (mouth open), 25 (deflated) | floating (no feet, 2 empty bottom rows) | cyan 0x50 |
| 5 | brute | 120 | 0.07 | 18 | 25 | 0 | 0 | 20 | 10 | 26 | 26, 27, 28 (claws up), 29 | feet on floor, 24 rows | red 0x20 |
| 6 | boss | 400 | 0.05 | 13 | 35 | 20 (cannon) | 8 | 15 | 10 | 30 | 30, 31, 32 (cannon fires), 34 dead, 33 fall | feet on floor, 24 rows, wide pose | white 0x70 |

step_q8 = round(step x 256): 0.06 -> 15 (the value step_axis uses today, so types 1/2 move exactly as before), 0.05 -> 13,
0.04 -> 10, 0.07 -> 18.  Wake radius 10 for every type (the brief fixes it for 1/2; nothing asked for a different one).

### Rules the table implies (for lane G's state machine, smallest change to game_e.asm)
- idle -> chase: distance < wake AND LOS (as today; a hit also wakes, game_g.asm enemy_hit).
- chase: melee types walk to adjacency (near_player07) then attack. Ranged-only types (flags bit1 set, bit2 clear) STOP
  walking when distance <= 2 cells and LOS (the shotgunner "holds at 2..6"); they still fire when the player is closer.
  The boss (melee + ranged) keeps walking to adjacency and fires its cannon on the way.
- attack timer: +1 per step while in range; at `timer` -> hit, timer = 0 (as today). Melee hit = adjacent; ranged hit =
  distance <= range AND LOS (see 'Ranged attacks' below). Boss: adjacent -> melee 35, else ranged 20 (that is the
  'alternating' of the brief in its simplest reading: the situation picks the attack; a strict A/B toggle would need
  bit 7 of the timer byte).
- dead: state 3 shows frame base+3 as today. Boss only (flags bit3): base+3 is the FALL frame for the first 5 steps of
  state 3 (timer counts), then base+4 (dead) for ever. Everything else is unchanged.
- The sprite ids follow today's THSPR convention (base + 0/1 walk, +2 attack, +3 dead), so vis_add needs only the
  boss exception above. THSPR for types 3..6 = 18, 22, 26, 30; INKTAB 0x60, 0x50, 0x20, 0x70.

### hp byte (lane G must decide - see E_QUESTIONS.md)
Record byte +6 holds hp in bits 0..4 (0..31) and the red-flash counter in bits 6..7 (blood.asm). 60/120/400 do not fit.
Proposal: store hp in units of 10 = "pistol hits to kill" (enemy_hit does hp -= 10): 3, 3, 3, 6, 12, 40 fit in bits 0..5
(0..63); the flash counter stays in bits 6..7. The ETAB below therefore carries hp/10 in its first byte and the raw hp in
the comment. If lane G prefers raw hp, boss hp needs a second byte or a 255 cap.

## Ranged attacks - proposal (the orchestrator decides)

A. Hit-scan (RECOMMENDED, no projectile sprite, no thing slot): when the ranged timer expires and distance <= range
   and los_check carries, the enemy goes to state 2 and the attack frame (muzzle flash / open mouth / glowing cannon)
   is what the player sees for the next 4 steps (0.4 s, timer < 4 -> frame base+2, else walk frame). The damage is
   applied at once, through the same shield-then-health code as melee (eh_hp), snd 8 then 4. Player feedback = the
   existing hurt sound plus a hurt flash: one attribute write that makes the HUD health cell (or the window's bottom
   cell row) BRIGHT red for 3 frames, the same trick as the pistol's BRIGHT yellow muzzle cells (attr.asm M2.6) -
   about 20 bytes. Shotgunner damage is 20 at <= 3 cells and 10 at 4..6 (two constants, one compare). Optional dodge
   rule so far shots are not a guaranteed hit: at > 3 cells the shot misses when bit 0 of `ticks` is set (50 %),
   1 compare. Cost estimate: ~80-100 bytes of Z80 in game_e (the attack branch becomes table-driven anyway) and the
   8 x 6 = 48 bytes of ETAB; zero extra RAM, zero extra sprites, works on 48K.
B. Projectile: each shot is a thing (type 7 'fireball', 8-byte slot) that moves 0.25 cell/step along a stored
   direction (the record has no velocity field: byte +7 would hold the 8-bit angle, +5/+6 unused), dies on a wall
   (cell_at) or on near_player07 (then damage), needs a sprite (16x8, 33 bytes, drawn per frame through the normal
   vis list so it is depth sorted for free). Cost: ~150-180 bytes of code, 33 bytes of sprite, and ONE THING SLOT PER
   SHOT IN FLIGHT. The 48K levels already use up to NTHINGS = 16 slots, so shots would often find no free slot (silent
   misfire) unless lane G raises NTHINGS (8 bytes + draw time each). On 128K/Next (48/96 things) it is affordable and
   looks better (dodgeable fireballs). Recommendation: A for phase 2 on all editions; B as a later 128K/Next upgrade
   of the floater and boss only (the shotgunner is a hit-scan weapon by nature).

## Sprites (assets/sprites_m4, compiled to build/sprites_m4_data.asm, sheet build/sprites_m4_sheet.png)
Ids 0..17 = today's set unchanged. New: 18-21 shotgunner, 22-25 floater, 26-29 brute, 30-34 boss, 35-36 chaingun
(32x24 weapon, same drawing idiom as the pistol/shotgun). Bytes (build/night/E_sizes.out): 16x24 frame 97 B, 16x20
81 B, 16x16 65 B, 16x8 corpse 33 B, 32x24 weapon 193 B. Per type: shotgunner 324 B, floater 276 B, brute 324 B,
boss 389 B, chaingun 386 B; all new data 1699 B + 38 B of table; the whole 37-sprite set incl. table 3559 B.
48K phase 2 (shotgunner only): 324 B + 8 B table. 128K types 3..6: 1313 B + 32 B table (+ 386 B chaingun).

## ETAB (machine block - paste into the game logic)
```
; ETAB: 8 bytes per type (index = type 1..6): hp, step_q8, melee, ranged, range, timer, wake, flags (bit0 floating, bit1 ranged, bit2 melee, bit3 boss)
; hp is stored as hp/10 = pistol hits to kill (record +6 bits 0..5; bits 6..7 stay the red-flash counter) - raw hp in the comment.
ETAB:   defb 3,15,10,0,0,25,10,0x04      ; 1 imp        hp 30  step 0.06 melee 10            timer 25 wake 10  THSPR 0  ink magenta
        defb 3,15,15,0,0,25,10,0x04      ; 2 zombie     hp 30  step 0.06 melee 15            timer 25 wake 10  THSPR 4  ink green
        defb 3,13,0,20,6,20,10,0x02      ; 3 shotgunner hp 30  step 0.05 ranged 20 (10 beyond 3 cells) range 6 timer 20 wake 10  THSPR 18 ink yellow 0x60
        defb 6,10,0,15,8,30,10,0x03      ; 4 floater    hp 60  step 0.04 ranged 15 range 8   timer 30 wake 10  THSPR 22 ink cyan 0x50, floating
        defb 12,18,25,0,0,20,10,0x04     ; 5 brute      hp 120 step 0.07 melee 25            timer 20 wake 10  THSPR 26 ink red 0x20
        defb 40,13,35,20,8,15,10,0x0E    ; 6 boss       hp 400 step 0.05 melee 35 ranged 20 range 8 timer 15 wake 10  THSPR 30 ink white 0x70, 2-frame death
; THSPR additions (type -> base sprite id): 3 -> 18, 4 -> 22, 5 -> 26, 6 -> 30.  INKTAB additions: 0x60, 0x50, 0x20, 0x70.
```
Shotgunner near/far damage: `ranged` = 20 is the <= 3 cells value; beyond 3 cells the code halves it (10). This keeps the
table at 8 bytes; if lane G prefers two bytes, add a 'ranged_far' column (10, 15, -, 20).
