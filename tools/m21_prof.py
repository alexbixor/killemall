#!/usr/bin/env python3
"""m21_prof.py - where the M2.1 attribute path spends its T-states (Python Z80 core, breakpoints like prof48.py).
Scene = m21_shots 'near' (barrel + imp at 1.5 cells, hv 64 each) and the start view with the level things.
Phases: dc_mark (per ink run), dc_attr (paint marked cells), ATTRCOPY, rest of draw_things, rays+bands, COPYBUF."""
import sys, pathlib
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
from test48 import SYM, run_until
import test_game_sprites as tgs
from test_game_doors import fake_input

def find_call_after(m, target):
    """addresses just after every 'call z,target' / 'call target' (CC/CD lo hi) in the code block"""
    lo, hi = target & 255, target >> 8
    out = []
    for a in range(0x8000, 0xFD60):
        if m.memory[a] in (0xCC, 0xCD) and m.memory[a + 1] == lo and m.memory[a + 2] == hi:
            out.append(a + 3)
    return out

def profile(m, labels):
    TRAP = 0x6AF0
    m.set_memory_block(0x6A00, bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x6A]))
    m.pc = 0x6A00; m.sp = 65008
    addr2lab = {}
    for lab, addrs in labels.items():
        for a in addrs: addr2lab[a] = lab
    for a in addr2lab: m.set_breakpoint(a)
    m.set_breakpoint(TRAP)
    cur, total, acc, hits = "render", 0, {}, {}
    while True:
        m.ticks_to_stop = 2_000_000
        m.run()
        used = 2_000_000 - m.ticks_to_stop; total += used
        acc[cur] = acc.get(cur, 0) + used
        if m.pc == TRAP: break
        if m.pc in addr2lab:
            cur = addr2lab[m.pc]; hits[cur] = hits.get(cur, 0) + 1
            m.step_over_breakpoint()
    for a in list(addr2lab) + [TRAP]: m.clear_breakpoint(a)
    return total, acc, hits

m = tgs.machine(); tgs.call(m, "init_game", "render"); fake_input(m, 0)
after_mark = find_call_after(m, SYM["dc_mark"])
labels = {"dc_mark": [SYM["dc_mark"]], "blit(after mark)": after_mark, "dc_attr": [SYM["dc_attr"]], "ATTRCOPY": [SYM["ATTRCOPY"]],
          "COPYBUF": [SYM["COPYBUF"]], "draw_things": [SYM["draw_things"]], "rays(col_loop)": [SYM["col_loop"]]}
print("call sites after dc_mark:", ["%04X" % a for a in after_mark])
def map_set(x, y, code): m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))
tgs.set_player(m, 3.5, 7.5, 0)
scenes = {"start, level things": None, "near 1.5 (barrel+imp)": 1.5, "mid 3.0": 3.0}
for name, d in scenes.items():
    if d is not None:
        wx = int(3.5 + d + 1.0)
        for x in range(7, 12): map_set(x, 7, 1 if x == wx else 0)
        tgs.clear_things(m); tgs.set_thing(m, 0, 21, 3.5 + d, 7.05); tgs.set_thing(m, 1, 1, 3.5 + d, 7.95)
    total, acc, hits = profile(m, labels)
    print("%s: total %d T = %.1f fps" % (name, total, 3500000 / total))
    for k, v in sorted(acc.items(), key=lambda kv: -kv[1]):
        print("   %-18s %7d T  %5.1f%%  hits %d" % (k, v, 100.0 * v / total, hits.get(k, 0)))
