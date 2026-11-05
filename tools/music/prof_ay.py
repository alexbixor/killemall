#!/usr/bin/env python3
"""prof_ay.py - T3: per-frame snd_isr cost profile (which frame type is the peak?)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from z80harness import Machine, ROOT, CALL_JP_T
mc = Machine(ROOT / "build/snd_test128.tap", ROOT / "build/snd_test128.sym")
S = mc.sym
mc.poke(S["opt_sfx"], [1]); mc.poke(S["opt_music"], [1])
for track in (1, 2):
    mc.call("snd_music", a=track)
    rows = []
    for f in range(400):
        c = mc.call("snd_isr") - CALL_JP_T
        rows.append((c, mc.peek(S["mus_tick"])[0], mc.peek(S["mus_phase"])[0], mc.peek(S["mus_rowleft"])[0]))
    worst = sorted(range(len(rows)), key=lambda i: -rows[i][0])[:8]
    print("track", track, "worst frames (cost, tick, phase, rowleft):", [(i,) + rows[i] for i in worst])
    print("  first 14:", rows[:14])
    # classify by phase/tick
    from collections import defaultdict
    cls = defaultdict(list)
    for c, tick, phase, rl in rows[3:]:
        cls[(phase)].append(c)
    for k in sorted(cls):
        print("  phase-after %d: n=%d max=%d avg=%.0f" % (k, len(cls[k]), max(cls[k]), sum(cls[k]) / len(cls[k])))
# idle cost (music stopped, no sfx)
mc.call("snd_music", a=0); mc.call("snd_isr")
print("idle snd_isr:", mc.call("snd_isr") - CALL_JP_T)
