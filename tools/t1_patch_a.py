#!/usr/bin/env python3
"""t1_patch_a.py - T1 milestone A edits to src/48k/kea48.asm (idempotent: refuses to run twice)."""
import pathlib, re, shutil
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "src/48k/kea48.asm"
s = P.read_text()
if "zbuf" in s:
    raise SystemExit("already patched")
shutil.copy(P, ROOT / "build/kea48_pre_t1a.asm")

# 1. factor the perp -> height lookup into perp_h (HL = perp -> A) and write zbuf[col] after rh_set
old_start = s.index("rh1:    ld hl,(perp)")
old_end = s.index("rh_set: ld (hcol),a")
s = s[:old_start] + "rh1:    ld hl,(perp)\n        call perp_h\n" + s[old_end:]
s = s.replace("rh_set: ld (hcol),a\n        cp 97\n",
              "rh_set: ld (hcol),a\n        ld hl,zbuf\n        ld c,a\n        ld a,(col)\n        add a,l\n        ld l,a\n"
              "        jr nc,$+3\n        inc h\n        ld (hl),c\n        ld a,c\n        cp 97\n", 1)

# 2. render: things (sprites) + weapon after the walls, before the burst copy
s = s.replace("        jr c,col_loop\n        jp COPYBUF",
              "        jr c,col_loop\n        call draw_things       ; T1: scaled masked sprites with zbuf depth test\n"
              "        jp COPYBUF", 1)

# 3. init_game: load the thing list into the runtime table
s = s.replace("        ld (posx),a\n        ld (posy),a\n        ret\n",
              "        ld (posx),a\n        ld (posy),a\n        jp things_init\n", 1)

# 4. main loop: game tick (in_read contract, doors, enemies, hud) instead of the M1 read_input
s = s.replace("        call render\n        call read_input\n        jp main",
              "        call render\n        call game_tick\n        jp main", 1)

# 5. includes (grouped at the end, before the level data)
s = s.replace('        include "gen/tables48.asm"\nlevel_data:',
              '        include "gen/tables48.asm"\n'
              '        include "../common/state.asm"\n'
              '        include "../common/stubs.asm"\n'
              '        include "../common/beeper.asm"\n'
              '        include "../common/game_a.asm"\n'
              '        include "../common/sprites.asm"\n'
              '        include "../common/hud.asm"\n'
              '        include "gen/sprites48.asm"\n'
              'level_data:', 1)
P.write_text(s)
print("patched", P, len(s.splitlines()), "lines")
