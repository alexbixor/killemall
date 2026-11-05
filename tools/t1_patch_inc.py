#!/usr/bin/env python3
"""t1_patch_inc.py - set the final include list in kea48.asm (idempotent), drop the stub snd_* when beeper.asm is used."""
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "src/48k/kea48.asm"
s = P.read_text()
i0 = s.index('        include "../common/state.asm"')
i1 = s.index("level_data:")
inc = ["../common/state.asm", "../common/stubs.asm", "../common/beeper.asm", "../common/game_a.asm", "../common/game_b.asm",
       "../common/sprites.asm", "../common/sprites_b.asm", "../common/sprites_c.asm", "../common/sprites_d.asm",
       "../common/sprites_e.asm", "../common/sprites_f.asm", "../common/hud.asm", "gen/sprites48.asm"]
s = s[:i0] + "".join('        include "%s"\n' % f for f in inc) + s[i1:]
P.write_text(s)
# stubs: remove the snd_* stand-ins (beeper.asm provides them)
S = ROOT / "src/common/stubs.asm"
t = S.read_text()
t2 = re.sub(r"^snd_fx:.*\n|^snd_music:.*\n|^snd_menu_tick:.*\n|^snd_isr:.*\n", "", t, flags=re.M)
if t2 != t:
    S.write_text(t2); print("stubs: snd_* removed")
print("includes set")
