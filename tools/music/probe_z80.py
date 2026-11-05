#!/usr/bin/env python3
"""probe_z80.py - inspect the Python z80 core for port output hooks (T3 sound lane)."""
import z80, inspect, sys
print("module", z80.__file__ if hasattr(z80, "__file__") else "?")
print("module dir:", [n for n in dir(z80) if not n.startswith("__")])
m = z80.Z80Machine()
names = [n for n in dir(m) if not n.startswith("__")]
print("machine dir:", names)
for n in names:
    try:
        a = getattr(type(m), n, None)
        doc = (getattr(a, "__doc__", None) or "").strip().replace("\n", " ")[:160]
        print("  %-24s %s" % (n, doc))
    except Exception as e:
        print("  %-24s <err %s>" % (n, e))
# check for subclassing hooks: run a program doing OUT (254),A and see if any method gets called
class M(z80.Z80Machine):
    def on_output(self, *a):
        print("on_output called", a)
    def output(self, *a):
        print("output called", a)
    def on_port_output(self, *a):
        print("on_port_output called", a)
    def out(self, *a):
        print("out called", a)
    def write_port(self, *a):
        print("write_port called", a)
    def on_write_port(self, *a):
        print("on_write_port called", a)
    def on_input(self, *a):
        print("on_input called", a); return 0xFF
    def input(self, *a):
        print("input called", a); return 0xFF
    def read_port(self, *a):
        print("read_port called", a); return 0xFF
    def on_read_port(self, *a):
        print("on_read_port called", a); return 0xFF
mm = M()
# ld a,0x10 ; out (0xFE),a ; in a,(0xFE) ; ld bc,0xFFFD ; out (c),a ; jp $
prog = bytes([0x3E, 0x10, 0xD3, 0xFE, 0xDB, 0xFE, 0x01, 0xFD, 0xFF, 0xED, 0x79, 0xC3, 0x0B, 0x60])
mm.set_memory_block(0x6000, prog)
mm.pc = 0x6000
mm.ticks_to_stop = 200
ev = mm.run()
print("events", ev, "pc", hex(mm.pc), "a", mm.a, "ticks_to_stop", mm.ticks_to_stop)
