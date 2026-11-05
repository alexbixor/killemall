#!/usr/bin/env python3
"""t1_patch_c.py - wire milestone C: remove placeholders from game_d, add includes, fire cooldown tick, ammo 50 start."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "src/common/game_d.asm"
s = D.read_text()
s = s.replace("fire_action: ret\nthings_tick: ret\n", "")
D.write_text(s)
A = ROOT / "src/common/game_a.asm"
t = A.read_text()
old = "        ld hl,door_cool\n        ld a,(hl)\n        or a\n        jr z,$+3\n        dec (hl)\n"
assert old in t
t = t.replace(old, old + "        ld hl,fire_cool\n        ld a,(hl)\n        or a\n        jr z,$+3\n        dec (hl)\n"
              "        cp 7\n        jr nz,$+5\n        xor a\n        ld (weapon_frame),a    ; fire frame shown for 5 frames\n")
A.write_text(t)
K = ROOT / "src/48k/kea48.asm"
k = K.read_text()
old = '        include "../common/game_d.asm"\n'
if '        include "../common/game_e.asm"\n' not in k:
    k = k.replace(old, old + '        include "../common/game_e.asm"\n        include "../common/game_f.asm"\n        include "../common/game_g.asm"\n')
    K.write_text(k)
S = ROOT / "src/common/state.asm"
u = S.read_text()
u = u.replace("ammo:       defb 20\n", "ammo:       defb 50\n")
S.write_text(u)
print("ok")
