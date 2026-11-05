#!/usr/bin/env python3
"""t1_isr_find.py - find the first instruction that leaves IFF1 clear outside the ISR / beeper (single-step with breakpoints).
Runs the real start; once ticks stop (int refused at a frame boundary) we bisect inside that frame by stepping small
tick windows and watching iff1 via m.on_handle_active_int() dry run is destructive -> use the state attribute instead."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM

start, code = load_code()
m = z80.Z80Machine()
m.set_memory_block(start, code)
m.set_memory_block(SYM["snd_fx"], bytes([0xC9]))
m.pc = SYM["start"]; m.sp = 65008
m.set_get_int_vector_callback(lambda: 0xFF)
labels = sorted((a, n) for n, a in SYM.items() if 27904 <= a < 65536)
def owner(pc):
    name = "?"
    for a, n in labels:
        if a <= pc: name = n
        else: break
    return name
iff = lambda: m.iff1
# run frames until an interrupt is refused
for f in range(40):
    m.ticks_to_stop = 69888
    while m.ticks_to_stop > 0: m.run()
    if not m.on_handle_active_int():
        print("int refused at frame", f, "pc %04x in %s iff1=%s" % (m.pc, owner(m.pc), iff())); break
else:
    print("no refusal in 40 frames"); sys.exit(0)
# step backwards is impossible: re-run from scratch to that frame, then step in 200-T windows and print the first iff1 drop
m2 = z80.Z80Machine(); m2.set_memory_block(start, code); m2.set_memory_block(SYM["snd_fx"], bytes([0xC9]))
m2.pc = SYM["start"]; m2.sp = 65008; m2.set_get_int_vector_callback(lambda: 0xFF)
iff2 = lambda: m2.iff1
for g in range(f):
    m2.ticks_to_stop = 69888
    while m2.ticks_to_stop > 0: m2.run()
    m2.on_handle_active_int()
# now inside frame f: step in small windows
prev_pc = m2.pc; was = iff2(); steps = 0
while steps < 69888:
    m2.ticks_to_stop = 4
    m2.run(); steps += 4
    now = iff2()
    if was and not now:
        print("IFF1 cleared between pc %04x (%s) and %04x (%s) after %d T into frame %d" % (prev_pc, owner(prev_pc), m2.pc, owner(m2.pc), steps, f))
        print("bytes at prev pc:", bytes(m2.memory[prev_pc:prev_pc + 6]).hex(), "sp %04x" % m2.sp)
        break
    was = now; prev_pc = m2.pc
else:
    print("no drop seen within the frame; iff1 now", iff2(), "pc %04x" % m2.pc)
