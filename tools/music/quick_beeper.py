#!/usr/bin/env python3
"""quick_beeper.py - T3: first-light measurement of beeper.asm on the Z80 core (durations, toggles, menu tick cost)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from z80harness import Machine, ROOT, CALL_JP_T

mc = Machine(ROOT / "build/snd_test48.tap", ROOT / "build/snd_test48.sym")
model = json.loads((ROOT / "build/beeper_model.json").read_text())
mc.poke(mc.addr("opt_sfx"), [1]); mc.poke(mc.addr("opt_music"), [1])
for i in range(1, 11):
    n0 = len(mc.outs)
    t = mc.call("snd_fx", a=i) - CALL_JP_T
    outs = mc.outs[n0:]
    p254 = [o for o in outs if (o[1] & 0xFF) == 0xFE]
    bad = [o for o in p254 if o[2] & ~0x10]
    tog = sum(1 for a, b in zip(p254, p254[1:]) if (a[2] ^ b[2]) & 16)
    exp = model["sfx"][str(i)]
    dur = (p254[-1][0] - p254[0][0]) if len(p254) > 1 else 0
    print("sfx %2d: T=%6d (%.1f ms) model %d..%d  outs=%d toggles=%d nonzero-border=%d iff1=%s span=%d" % (
        i, t, t / 3500, exp["t_min"], exp["t_max"], len(p254), tog, len(bad), mc.iff1(), dur))
# menu tick
t = mc.call("snd_music", a=1) - CALL_JP_T
print("snd_music T", t, "playing", mc.peek(mc.addr("snd_playing"))[0])
costs = []
n0 = len(mc.outs)
for f in range(60):
    costs.append(mc.call("snd_menu_tick") - CALL_JP_T)
outs = [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]
print("menu_tick T min/max/avg %d/%d/%.0f outs=%d" % (min(costs), max(costs), sum(costs) / len(costs), len(outs)))
# estimate frequency from toggles within first few calls
ts = [o[0] for o in outs[:40]]
print("first toggle gaps:", [b - a for a, b in zip(ts, ts[1:])][:20])
print("mt state pos/cnt/p1/p2:", list(mc.peek(mc.addr("mt_pos"), 6)))
# half-cycle overhead measurement for pure tone: sfx 6 (period 15, no noise)
p6 = [o for o in mc.outs if (o[1] & 0xFF) == 0xFE]
