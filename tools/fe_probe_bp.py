#!/usr/bin/env python3
"""fe_probe_bp.py - breakpoint semantics of the Python Z80 core: does run() at a marked pc stop before executing it?
Does ticks_to_stop=1 execute exactly one instruction? step_over_breakpoint()?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
m = z80.Z80Machine()
# 0x6000: nop(4) nop(4) nop(4) halt ; jr $
m.set_memory_block(0x6000, bytes([0x00, 0x00, 0x00, 0x76, 0x18, 0xFE]))
m.pc = 0x6000; m.sp = 0x7000
m.set_breakpoint(0x6002)
m.ticks_to_stop = 1000; ev = m.run()
print("run1: ev", ev, "pc %04x" % m.pc, "used", 1000 - m.ticks_to_stop)
m.ticks_to_stop = 1000; ev = m.run()
print("run2 (still marked): ev", ev, "pc %04x" % m.pc, "used", 1000 - m.ticks_to_stop)
try:
    r = m.step_over_breakpoint(); print("step_over_breakpoint ->", r, "pc %04x" % m.pc)
except Exception as e:
    print("step_over_breakpoint error", repr(e))
m.ticks_to_stop = 1; ev = m.run()
print("run ticks_to_stop=1: ev", ev, "pc %04x" % m.pc, "halted", m.halted, "ticks_to_stop", m.ticks_to_stop)
m.ticks_to_stop = 1; ev = m.run()
print("run ticks_to_stop=1 again: ev", ev, "pc %04x" % m.pc, "halted", m.halted, "ticks_to_stop", m.ticks_to_stop)
m.ticks_to_stop = 100; ev = m.run()
print("run 100 while halted: ev", ev, "pc %04x" % m.pc, "halted", m.halted, "ticks_to_stop", m.ticks_to_stop)
