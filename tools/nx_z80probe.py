#!/usr/bin/env python3
"""nx_z80probe.py - probe the kosarev z80 python package: can it run code blocks, breakpoints, Z80N opcodes, speed."""
import z80, time
m = z80.Z80Machine()
# ld hl,1234h ; ld de,0010h ; add hl,de ; ld (9000h),hl ; nop ; (ED 34 = Z80N add hl,nn)
code = bytes.fromhex("2134121110001922009000ED340500")
m.set_memory_block(0x8000, code)
m.pc = 0x8000
m.set_breakpoint(0x800A)
r = m.run()
print("run ->", r, "pc=%04X hl=%04X" % (m.pc, m.hl), "mem9000=", bytes(m.memory[0x9000:0x9002]).hex())
print(type(m.memory), len(m.memory))
m.pc = 0x800B; m.hl = 0x0100
m.set_breakpoint(0x800F)
try:
    r = m.run(); print("after ED34 (Z80N add hl,nn): pc=%04X hl=%04X r=%s" % (m.pc, m.hl, r))
except Exception as e: print("ED34 ->", repr(e))
m2 = z80.Z80Machine(); m2.set_memory_block(0x8000, bytes.fromhex("0B78B1C2008000")); m2.pc = 0x8000; m2.bc = 0; m2.set_breakpoint(0x8006)
t = time.time(); m2.run(); print("65536 iterations x 4 instr in %.2fs" % (time.time() - t), "pc=%04X" % m2.pc)
print([a for a in dir(m) if 'tick' in a or 'state' in a])
