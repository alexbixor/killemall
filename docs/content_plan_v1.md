# Kill'em all — content programme v1 (5 Nov 2026, 13:30Z), orchestrator-owned

Decision (Alex, 5 Nov 12:18Z): "2 and then let's add enemies, bosses and levels to all versions."
= first the Next edition B engine (docs/next_engine_spec_v0.2_flat.md), then content for the 48K, 128K and Next editions.

## What exists (5 Nov, v0.27.1 released 3 Nov)
- Editions: 48K tape (8.6 fps), 128K tape with AY music (8.3 fps), Next runs the 128K tape in 128 mode (33 fps at 28 MHz).
- Shared game logic src/common/*.asm: 10 Hz steps, 16 things (8-byte records), enemy AI for types 1 imp / 2 zombie only
  (game_e.asm: idle/chase/attack/dead, melee only), items 16-22, doors/keys, HUD, front end, 3 levels (NLEVELS = 3).
- Levels assets/levels/01..03 (.txt, 32x32, tools/mapc.py grammar). mapc already knows enemy letters i z s c b k = types 1..6
  and caps: distinct enemy types per level 48k 3 / 128k 6 / next 8; things per level 48k 24 / 128k 48 / next 96.
- Sprites assets/sprites/00..17 (imp x4, zombie x4, 6 items, 2 weapons x2), compiled by tools/spritec.py to src/gen/sprites_data.asm.
- 48K memory: 9 bytes free below 8000h in the low block, 41 bytes between hi_end and the stack top. Nothing fits without
  freeing memory first. 128K: bank 1 holds the AY player + music + the 3 level images; banks 3/4/6 unused.

## Target (DESIGN.md, unchanged)
- 48K: 3 enemy types (imp, zombie, shotgunner), 2+ frames each, 3 levels.
- 128K: 6 enemy types (imp, zombie, shotgunner, floater "cacodemon-like", brute "baron-like", boss), bosses, 8 levels.
- Next: same 6 types (the 2 Next-only extras come later), 3 bosses later, 8 levels, edition B engine.

## Phase 1 lanes (parallel, disjoint files; each lane owns ONLY the files listed; nobody touches build/release/*)
- N1  Next B walker + flat reference: tools/nx_ref_flat.py, src/next/walk_b.asm, src/next/walk_b_vars.inc,
      src/next/test_walk_b.asm, tools/nx_test_walk_b.py, build/night/ref_flat/, build/night/N1_*.
- N1D Next B drawers: src/next/draw_b.asm, src/next/test_draw_b.asm, tools/nx_test_draw_b.py, tools/nx_ref_planes.py,
      build/night/N1D_*. Oracle = the v0.1 records/frames in build/night/ref/ (read-only) + its own lo/flat variants.
- N1A Next B assets + build tool: tools/nx_textures.py, build/next/assets_b/ (NEW dir; build/next/assets/ stays
      byte-identical), tools/nx_build.py (new options, old defaults unchanged), build/night/N1A_*.
- L   Levels 04..08: assets/levels/04..08_*.txt, assets/levels/_gen_levels.py, tools/levelcheck.py, tools/mapc.py
      (only if a bug blocks; 01..03 output bytes must not change), build/night/L_*, build/levels_*.png.
- E   Enemy roster + art: assets/sprites_m4/ (NEW dir), tools/spritec.py (default run must still produce byte-identical
      src/gen/sprites_data.asm - prove it with a diff), docs/enemies_v1.md, build/night/E_*.
- G   Shared game logic to tables + memory: src/common/*.asm, src/48k/*.asm, src/128k/*.asm, src/gen/*, tools/build48.sh,
      tools/build128.sh and the gate scripts, build/night/G_*, build/night/pre_G/ (backups of every edited file).
      Behaviour of the shipped levels must not change; all 14 release gates green; 48K and 128K memory report.
- Then (sequential, after N1 + N1D + N1A): N1M = src/next/main_b.asm, tools/nx_test_full_b.py, build/next/killemall_b.nex,
  the 25 fps gate and the video. Then N2 (game logic + sprites + HUD + AY on edition B) and phase 2 content.
- M   Mouse look (added 5 Nov 14:40Z, Alex: "can we add mouse look too?"): Kempston mouse / Next PS/2 mouse ports 0FBDFh X,
      0FFDFh Y, 0FADFh buttons; menu option MOUSE: OFF/ON (default OFF -> shipped play byte-identical); per-frame turn from the
      X delta with a 16-bit fraction, left click = fire, right click = use. Owns src/common/input.asm, game_a.asm, state.asm,
      frontend.asm + ONE hook line per main. Runs AFTER G reports (same files). Brief: build/night/M_BRIEF.md. Edition B gets
      it through N2 (the hook line is filed in M_result.md).

## Phase 2 (after phase 1 reports): put the new types and levels into the editions
- 48K: shotgunner (type 3) + the memory it needs; 3 levels stay.
- 128K: types 3..6 with sprite frames paged from bank 3 (or copied per frame), levels 04..08 in banks 1/4/6, NLEVELS 8.
- Next B: everything the 128K has, software sprites with ZBUF occlusion, hardware-sprite HUD.
- Bosses: type 6 on level 08 (and 04 as a mid boss on 128K/Next). Ranged attacks need projectiles = a design decision
  for the orchestrator after lane E's proposal; phase 1 only reserves the table columns.

## Rules for every lane (same as the night of 4/5 Nov, build/night/LANE_BRIEF.md still applies)
- Evidence, not claims: every number comes from a command whose output is saved under build/night/<lane>_*.out.
- Reversibility: before editing an existing file copy it to build/night/pre_<lane>/ (keep paths). git is initialised
  in /home/ubuntu/work/killemall (commit "phase-1 start" = the state before the lanes); do not commit, the orchestrator does.
- Never run another lane's build or test; never write a file you do not own; outputs truncated -> redirect to a file.
- Foreground commands < 600 s with `timeout`; .venv/bin/python; pasmo; the ZEsarUX harnesses as in LANE_BRIEF.md.
- Final report in plain English, under 40 lines: what exists, what passes (numbers), what fails, decisions, questions.
