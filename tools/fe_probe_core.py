#!/usr/bin/env python3
"""fe_probe_core.py - probe the Python Z80 core: does set_input_callback see IN ports (16-bit?), tick accounting."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
m = z80.Z80Machine()
# ld a,0xFE ; in a,(0xFE) ; ld (0x9000),a ; ld bc,0x001F ; in a,(c) ; ld (0x9001),a ; jp $
prog = bytes([0x3E, 0xFE, 0xDB, 0xFE, 0x32, 0x00, 0x90, 0x01, 0x1F, 0x00, 0xED, 0x78, 0x32, 0x01, 0x90, 0xC3, 0x0F, 0x60])
m.set_memory_block(0x6000, prog)
seen = []
def inp(port):
    seen.append(port)
    return 0x55 if (port % 256) == 0xFE else 0xAA
m.set_input_callback(inp)
m.pc = 0x6000; m.sp = 0x7000
m.set_breakpoint(0x600F)
m.ticks_to_stop = 1000
ev = m.run()
print("ev", ev, "pc %04x" % m.pc, "ticks_to_stop", m.ticks_to_stop)
print("ports seen", [hex(p) for p in seen])
print("mem", hex(m.memory[0x9000]), hex(m.memory[0x9001]))
# expected: ld a,n 7 + in a,(n) 11 + ld (nn),a 13 + ld bc,nn 10 + in a,(c) 12 + ld (nn),a 13 = 66
print("used ticks", 1000 - m.ticks_to_stop, "(expected 66 if breakpoint stops before executing jp)")
