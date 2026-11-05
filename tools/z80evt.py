#!/usr/bin/env python3
"""z80evt.py - learn the run() event semantics of the Python z80 core (event 8 seen = ?)."""
import z80
m = z80.Z80Machine()
# program: a=0; loop: dec a / jr nz loop (256 iterations) ; jp self
m.set_memory_block(0x6000, bytes([0x3E, 0x00, 0x3D, 0x20, 0xFD, 0xC3, 0x05, 0x60]))
m.pc = 0x6000; m.ticks_to_stop = 100000
for i in range(6):
    ev = m.run()
    print("iter", i, "events", ev, "pc %04x" % m.pc, "ticks_to_stop", m.ticks_to_stop, "frame_tick", m.frame_tick)
    if m.pc == 0x6005 and ev == 8:
        print("event 8 = instruction-level stop at jp self? reached end")
        break
