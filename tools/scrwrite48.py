#!/usr/bin/env python3
"""scrwrite48.py - proves the back-buffer contract: runs one render() on the Python Z80 core with a memory-write hook and
reports every write into pixel memory 16384..22527, attributing it to the code address that performed it.  All such writes
must come from COPYBUF (the final burst); attribute writes (22528..23295) are listed separately.  usage: scrwrite48.py [px py ang]"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM, run_until

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
    labels = sorted((a, n) for n, a in SYM.items() if 32768 <= a < 65536)
    def owner(pc):
        name = "?"
        for a, n in labels:
            if a <= pc: name = n
            else: break
        return name
    pix, attr, other = {}, {}, {}
    def hook(addr, value):
        pc = m.pc
        if 0x4000 <= addr < 0x5800: pix[owner(pc)] = pix.get(owner(pc), 0) + 1
        elif 0x5800 <= addr < 0x5B00: attr[owner(pc)] = attr.get(owner(pc), 0) + 1
        elif addr < 0x8000 and not (0x6000 <= addr < 0x6E00) and not (0x7E00 <= addr < 0x8000): other[(owner(pc), addr >> 8)] = other.get((owner(pc), addr >> 8), 0) + 1
    m.set_write_callback(hook)
    m.mark_addrs(0x4000, 0x1B00, m.WRITE_MARK)             # 16384..23295: screen pixels + attributes
    # run() stops with _NO_EVENTS-style returns on marks; loop until the trap
    m.set_breakpoint(TRAP); used = 0
    while m.pc != TRAP:
        m.ticks_to_stop = 100_000
        m.run(); used += 100_000 - m.ticks_to_stop
        if used > 50_000_000: raise SystemExit("runaway pc=%04x" % m.pc)
    t = used
    print("render+copy T-states", t)
    print("pixel-memory writes by routine:", pix)
    print("attribute writes by routine:", attr)
    print("other low-RAM writes (routine, page):", other)
    ok = set(pix) <= {"COPYBUF", "cb_col"} and sum(pix.values()) == 1536
    print("CONTRACT", "OK: all %d pixel writes come from COPYBUF" % sum(pix.values()) if ok else "VIOLATED")

if __name__ == "__main__":
    main()
