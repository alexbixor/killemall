#!/usr/bin/env python3
"""fe_probe_int.py - probe the Python Z80 core: does on_handle_active_int() wake a HALTed CPU (IM1 / IM2)?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
m = z80.Z80Machine()
# at 0x6000: im 1 ; ei ; halt ; inc a ; jp $-? -> loop: halt / inc a / jr loop
prog = bytes([0xED, 0x56, 0xFB, 0x76, 0x3C, 0x18, 0xFC])
m.set_memory_block(0x6000, prog)
m.set_memory_block(0x0038, bytes([0xFB, 0xED, 0x4D]))  # ei ; reti
m.pc = 0x6000; m.sp = 0x7000; m.a = 0
m.ticks_to_stop = 2000
ev = m.run()
print("after run: ev", ev, "pc %04x" % m.pc, "halted", m.halted, "a", m.a, "ticks_to_stop", m.ticks_to_stop, "iff1", m.iff1)
try:
    r = m.on_handle_active_int()
    print("on_handle_active_int ->", r, "pc %04x" % m.pc, "halted", m.halted)
except Exception as e:
    print("on_handle_active_int error:", repr(e))
m.ticks_to_stop = 200
ev = m.run()
print("after 2nd run: ev", ev, "pc %04x" % m.pc, "halted", m.halted, "a", m.a, "ticks_to_stop", m.ticks_to_stop)
# IM2 test
m2 = z80.Z80Machine()
prog2 = bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0x76, 0x3C, 0x18, 0xFC])  # ld a,0xFE; ld i,a; im 2; ei; halt; inc a; jr
m2.set_memory_block(0x6000, prog2)
m2.set_memory_block(0xFE00, bytes([0x00, 0x70] * 129))  # vector table -> 0x7000
m2.set_memory_block(0x7000, bytes([0xFB, 0xED, 0x4D]))
m2.set_get_int_vector_callback(lambda: 0xFF)
m2.pc = 0x6000; m2.sp = 0x7F00; m2.a = 5
m2.ticks_to_stop = 2000; ev = m2.run()
print("IM2 after run: ev", ev, "pc %04x" % m2.pc, "halted", m2.halted, "a", m2.a)
r = m2.on_handle_active_int(); print("IM2 int ->", r, "pc %04x" % m2.pc, "halted", m2.halted)
m2.ticks_to_stop = 200; ev = m2.run()
print("IM2 after 2nd run: ev", ev, "pc %04x" % m2.pc, "halted", m2.halted, "a", m2.a)
