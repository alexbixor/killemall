#!/usr/bin/env python3
"""prof48.py - phase profiler for the 48K renderer on the Python Z80 core.

Puts breakpoints on phase labels, runs one render() from the level start position, and reports the T-states spent
between consecutive labels (attributed to the phase that *starts* at each label).  Usage: prof48.py [px py angle]
"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM, run_until

PHASES = ["ray", "ry_st", "rx_st", "dda_call", "rh_set", "rd_band", "attr_jp", "band_jp", "hit_x", "hit_y", "hit_far", "calc_u", "col_loop", "CLRBUF", "COPYBUF", "build_ftab"]

def main():
    px, py, ang = (float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (3.5, 7.5, 0)
    start, code = load_code()
    m = z80.Z80Machine(); m.set_memory_block(start, code)
    TRAP = 0x7F00
    m.set_memory_block(TRAP, bytes([0xC3, 0x00, 0x7F]))
    m.set_memory_block(0x7E00, bytes([0xCD]) + SYM["init_game"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x7F]))
    m.pc = 0x7E00; m.sp = 0x7E00; run_until(m, TRAP)
    ix, fx = int(px), int((px - int(px)) * 256); iy, fy = int(py), int((py - int(py)) * 256)
    m.set_memory_block(SYM["posx"], bytes([fx, ix])); m.set_memory_block(SYM["posy"], bytes([fy, iy]))
    m.set_memory_block(SYM["angle"], bytes([ang & 255]))
    m.set_memory_block(0x7E00, bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x7F]))
    m.pc = 0x7E00; m.sp = 0x7E00
    addr2lab = {SYM[l]: l for l in PHASES if l in SYM}
    for a in addr2lab: m.set_breakpoint(a)
    m.set_breakpoint(TRAP)
    spent, hits = {}, {}
    cur = "render-setup"; total = 0
    while True:
        m.ticks_to_stop = 2_000_000
        ev = m.run()
        used = 2_000_000 - m.ticks_to_stop; total += used
        spent[cur] = spent.get(cur, 0) + used
        if m.pc == TRAP: break
        if ev & m._BREAKPOINT_HIT:
            cur = addr2lab.get(m.pc, "?%04x" % m.pc); hits[cur] = hits.get(cur, 0) + 1
            m.step_over_breakpoint()
            # step_over executes one instruction; count its ticks into the new phase
        if total > 60_000_000: print("runaway"); break
    print("total T %d (%.1f fps)" % (total, 3_500_000 / total))
    for k, v in sorted(spent.items(), key=lambda kv: -kv[1]):
        print("%-14s %8d T  %5.1f%%  hits %d" % (k, v, 100.0 * v / total, hits.get(k, 0)))

if __name__ == "__main__":
    main()
