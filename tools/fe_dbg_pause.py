#!/usr/bin/env python3
"""fe_dbg_pause.py - debug the fe_pause RESUME path."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_frontend as tf
SYM = tf.SYM
m3 = tf.Machine(); mm3 = m3.m
stub3 = 0x7E00; trap3 = 0x7F00
mm3.set_memory_block(65024, bytes([253]) * 257); mm3.set_memory_block(65021, bytes([0xC3]) + SYM["isr"].to_bytes(2, "little"))
mm3.set_memory_block(stub3, bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xCD]) + SYM["fe_pause"].to_bytes(2, "little") + bytes([0x32, 0x00, 0x7F, 0x76, 0x18, 0xFD]))
mm3.set_memory_block(trap3, bytes([0xAA]))
mm3.pc = stub3; mm3.sp = 0x7E00
m3.to_halt(); m3.frames(2)
m3.tap("Q")
print("after Q: fe_cur", m3.byte("fe_cur"))
m3.press_blocking("SPACE"); m3.run_ticks(100_000)
print("after SPACE (quit): trap", hex(mm3.memory[trap3]), "pc %04x" % mm3.pc, "halted", mm3.halted, "sp %04x" % mm3.sp)
mm3.set_memory_block(trap3, bytes([0xAA])); mm3.pc = stub3; mm3.sp = 0x7E00; mm3.halted = 0
print("reset: pc %04x halted" % mm3.pc, mm3.halted, "iff1", mm3.iff1)
t = m3.to_halt()
print("to_halt T", t, "pc %04x" % mm3.pc, "fe_cur", m3.byte("fe_cur"), "fe_mode", m3.byte("fe_mode"), "fe_prev %02x" % m3.byte("fe_prev"), "trap", hex(mm3.memory[trap3]))
for r in range(16, 24):
    print("row %2d %-32s attr %02X" % (r, m3.text_row(r), m3.attr_row(r)[0]))
m3.press("ENTER")
for i in range(3):
    if mm3.halted:
        mm3.on_handle_active_int()
    m3.run_ticks(70_000)
    print("frame", i, "pc %04x" % mm3.pc, "halted", mm3.halted, "trap", hex(mm3.memory[trap3]), "fe_cur", m3.byte("fe_cur"), "fe_prev %02x" % m3.byte("fe_prev"))
m3.release("ENTER"); m3.run_ticks(300_000)
print("after release: pc %04x" % mm3.pc, "halted", mm3.halted, "trap", hex(mm3.memory[trap3]), "sp %04x" % mm3.sp)
