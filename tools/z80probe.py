#!/usr/bin/env python3
"""z80probe.py — check the Python Z80 core API we will use to unit-test the ray loop (register/memory/ticks access)."""
import z80, inspect
m = z80.Z80Machine()
print("run doc:", (m.run.__doc__ or "").strip()[:200])
print("set_memory_block doc:", (m.set_memory_block.__doc__ or "").strip()[:200])
code = bytes([0x21, 0x34, 0x12,      # ld hl,1234h
              0x22, 0x00, 0x80,      # ld (8000h),hl
              0x3E, 0x05,            # ld a,5
              0x3D,                  # dec a
              0x20, 0xFD,            # jr nz,-3
              0xC3, 0x0B, 0x60])     # jp self  (spin)
m.set_memory_block(0x6000, code)
m.pc = 0x6000
m.ticks_to_stop = 500
ev = m.run()
print("events", ev, "pc", hex(m.pc), "hl", hex(m.hl), "a", m.a, "mem", m.memory[0x8000:0x8002].hex(), "ticks_to_stop", m.ticks_to_stop)
