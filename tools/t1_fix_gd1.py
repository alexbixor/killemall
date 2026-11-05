#!/usr/bin/env python3
"""t1_fix_gd1.py - clean wait_frames (game_d.asm); add bump_action call + includes (game_a / kea48)."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "src/common/game_d.asm"
s = P.read_text()
i0 = s.index("wait_frames:\n")
i1 = s.index("msg_clear:")
new = """wait_frames:
        ld hl,(ticks)
        ld e,b
        ld d,0
        add hl,de              ; HL = target tick
wf_l:   ld de,(ticks)
        push hl
        or a
        sbc hl,de              ; target - now, > 0 while waiting
        pop hl
        ret z
        jp m,wf_ret
        jr wf_l
wf_ret: ret
"""
s = s[:i0] + new + s[i1:]
P.write_text(s)
A = ROOT / "src/common/game_a.asm"
t = A.read_text()
old = "gt2:    ld a,(in_bits)\n        bit 0,a\n        jr z,gt3\n        ld a,(angle)\n        call move_by\n"
assert old in t
t = t.replace(old, "gt2:    ld a,(in_bits)\n        bit 0,a\n        jr z,gt3\n        ld a,(angle)\n        call move_by\n        call bump_action       ; doors auto-open when walked into\n")
t = t.replace("        call things_tick\n        call pickups\n        jp hud_update\n",
              "        call things_tick\n        call pickups\n        ld hl,door_cool\n        ld a,(hl)\n        or a\n        jr z,$+3\n        dec (hl)\n"
              "        ld a,(health)\n        or a\n        jp z,player_dead\n        jp hud_update\n")
A.write_text(t)
K = ROOT / "src/48k/kea48.asm"
k = K.read_text()
old = '        include "../common/game_b.asm"\n'
if '        include "../common/game_c.asm"\n' not in k:
    k = k.replace(old, old + '        include "../common/game_c.asm"\n        include "../common/game_d.asm"\n')
    K.write_text(k)
print("ok")
