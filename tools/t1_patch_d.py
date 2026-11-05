#!/usr/bin/env python3
"""t1_patch_d.py - wire milestone D: hud_b include, hud_init at start, HUD attrs (rows 13..23 white on black), fps text row."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
K = ROOT / "src/48k/kea48.asm"
k = K.read_text()
old = '        include "../common/hud.asm"\n'
if '        include "../common/hud_b.asm"\n' not in k:
    k = k.replace(old, old + '        include "../common/hud_b.asm"\n')
# start: call hud_init after init_game (title text stays on row 0)
old = "        call cls\n        call init_game\n        ld hl,title_txt\n        ld de,16394\n        call print\n"
assert old in k
k = k.replace(old, "        call cls\n        call init_game\n        ld hl,title_txt\n        ld de,16394\n        call print\n        call hud_init\n")
# cls: attributes default 7 (white on black) already -> rows 13..23 fine. Nothing else.
K.write_text(k)
print("ok")
