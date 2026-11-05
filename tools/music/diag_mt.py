#!/usr/bin/env python3
"""diag_mt.py - T3: inspect the snd_menu_tick port-254 write stream: separate the two multiplex slots and measure each
voice's toggle period against the expected counter values (first sounding steps)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from z80harness import Machine, ROOT, CALL_JP_T
mc = Machine(ROOT / "build/snd_test48.tap", ROOT / "build/snd_test48.sym")
S = mc.sym
model = json.loads((ROOT / "build/beeper_model.json").read_text())
mc.poke(S["opt_sfx"], [1]); mc.poke(S["opt_music"], [1])
mc.call("snd_music", a=1)
mc.poke(S["mt_outer"], [2])
for step in range(3):
    for f in range(12):
        n0 = len(mc.outs)
        t = mc.call("snd_menu_tick") - CALL_JP_T
        outs = [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]
        if f == 1:
            # slots alternate: even index = voice 1 slot, odd = voice 2 slot (first write of a pass is voice 1)
            v1 = [o for o in outs[0::2]]; v2 = [o for o in outs[1::2]]
            def toggles(seq):
                return [b[0] - a[0] for a, b in zip(seq, seq[1:]) if a[2] != b[2]]
            tg1 = []; last = v1[0]
            for o in v1[1:]:
                if o[2] != last[2]:
                    tg1.append(o[0] - last[0]); last = o
            tg2 = []; last = v2[0]
            for o in v2[1:]:
                if o[2] != last[2]:
                    tg2.append(o[0] - last[0]); last = o
            mel = model["tune"]["melody"][step]; bass = model["tune"]["bass"][step // 2]
            print("step %d frame %d: %d T, %d writes; v1 note %s half-periods %s ...; v2 note %s half-periods %s ..." % (
                step, f, t, len(outs), mel, tg1[:6], bass, tg2[:4]))
            print("   p1/c1/p2/c2 =", list(mc.peek(S["mt_p1"], 4)), "masks", mc.peek(S["mt_m1"] + 1)[0], mc.peek(S["mt_m2"] + 1)[0],
                  "values seen v1", sorted(set(o[2] for o in v1)), "v2", sorted(set(o[2] for o in v2)))
