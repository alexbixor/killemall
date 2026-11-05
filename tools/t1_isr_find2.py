#!/usr/bin/env python3
"""t1_isr_find2.py - at the frame where the int is refused, print iff1/iff2/int_disabled/halted and the instruction;
then also test: does on_handle_active_int succeed if we step a few T first?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM
start, code = load_code()
labels = sorted((a, n) for n, a in SYM.items() if 27904 <= a < 65536)
def owner(pc):
    name = "?"
    for a, n in labels:
        if a <= pc: name = n
        else: break
    return name
m = z80.Z80Machine(); m.set_memory_block(start, code); m.set_memory_block(SYM["snd_fx"], bytes([0xC9]))
m.pc = SYM["start"]; m.sp = 65008; m.set_get_int_vector_callback(lambda: 0xFF)
for f in range(60):
    m.ticks_to_stop = 69888
    while m.ticks_to_stop > 0: m.run()
    ok = m.on_handle_active_int()
    print("frame %2d pc %04x %-12s iff1 %d iff2 %d int_disabled %d halted %d im %s -> int %s" % (
        f, m.pc, owner(m.pc), m.iff1, m.iff2, m.int_disabled, m.halted, getattr(m, "int_mode", "?"), ok))
    if f == 6:
        # int accepted at frame 6: run the ISR (ei at its end), then step until iff1 drops -> the culprit instruction
        prev = m.pc; was = m.iff1; t = 0
        while t < 69888 * 2:
            m.ticks_to_stop = 4; m.run(); t += 4
            now = m.iff1
            if was and not now:
                print("   IFF1 cleared: prev pc %04x (%s) -> pc %04x (%s), %d T after the frame-6 int; bytes at prev %s sp %04x" % (
                    prev, owner(prev), m.pc, owner(m.pc), t, bytes(m.memory[prev:prev + 4]).hex(), m.sp))
                print("   stack:", bytes(m.memory[m.sp:m.sp + 12]).hex())
                break
            was = now; prev = m.pc
        else:
            print("   no drop in 2 frames; iff1", m.iff1)
        break
