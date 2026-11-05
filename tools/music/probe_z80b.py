#!/usr/bin/env python3
"""probe_z80b.py - learn set_output_callback / set_input_callback signatures and timing (T3)."""
import z80, inspect
m = z80.Z80Machine()
print("set_output_callback doc:", (m.set_output_callback.__doc__ or "").strip())
print("set_input_callback doc:", (m.set_input_callback.__doc__ or "").strip())
print("run doc:", (m.run.__doc__ or "").strip())
log = []
def outcb(*a, **k):
    log.append(("out", a, k, m.ticks_to_stop, m.frame_tick))
def incb(*a, **k):
    log.append(("in", a, k, m.ticks_to_stop, m.frame_tick))
    return 0xBF
m.set_output_callback(outcb)
m.set_input_callback(incb)
# ld a,0x10 ; out (0xFE),a ; nop x4 ; in a,(0xFE) ; ld bc,0xFFFD ; out (c),a ; jp $
prog = bytes([0x3E, 0x10, 0xD3, 0xFE, 0x00, 0x00, 0x00, 0x00, 0xDB, 0xFE, 0x01, 0xFD, 0xFF, 0xED, 0x79, 0xC3, 0x0F, 0x60])
m.set_memory_block(0x6000, prog)
m.pc = 0x6000
m.ticks_to_stop = 1000
ev = m.run()
print("events", ev, "pc", hex(m.pc), "a", m.a, "ticks_to_stop", m.ticks_to_stop, "frame_tick", m.frame_tick)
for e in log:
    print(e)
# second run: does frame_tick accumulate? run a 2nd time
m.pc = 0x6000
m.ticks_to_stop = 1000
ev = m.run()
print("2nd events", ev, "ticks_to_stop", m.ticks_to_stop, "frame_tick", m.frame_tick)
for e in log[3:]:
    print(e)
# check: iff1 / int_disabled attributes after DI/EI
m2 = z80.Z80Machine()
m2.set_memory_block(0x6000, bytes([0xF3, 0xFB, 0xC3, 0x02, 0x60]))  # di ; ei ; jp $
m2.pc = 0x6000; m2.ticks_to_stop = 100
m2.run()
print("iff1 after di/ei:", m2.iff1, "iff2", m2.iff2, "int_disabled", m2.int_disabled)
m2.set_memory_block(0x6000, bytes([0xFB, 0xF3, 0xC3, 0x02, 0x60]))  # ei ; di ; jp $
m2.pc = 0x6000; m2.ticks_to_stop = 100
m2.run()
print("iff1 after ei/di:", m2.iff1, "iff2", m2.iff2, "int_disabled", m2.int_disabled)
