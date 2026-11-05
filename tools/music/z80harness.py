#!/usr/bin/env python3
"""z80harness.py - T3 sound lane: shared helpers to run assembled sound code on the Python Z80 core (z80 1.2.0).

Core facts (probed with tools/music/probe_z80*.py):
  * z80.Z80Machine.set_output_callback(fn): fn(port16, value) is called on every OUT; inside the callback
    m.ticks_to_stop / m.frame_tick give the cycle-exact time (frame_tick accumulates across run() calls).
  * set_input_callback(fn): fn(port16) -> byte for every IN.
  * run() stops at ticks_to_stop (event 4) or at a breakpoint (event 1/2); set_breakpoint(addr).
  * No OUT hook needed in the Z80 code: the callback IS the port-254 / AY register-stream logger.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import z80

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRAP = 0x7F00          # RET trap: a `jp $` whose PC we watch
SCRATCH = 0x7E00       # tiny call stubs live here

def read_sym(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(path).read_text(), re.M)}

def tap_blocks(path):
    data = pathlib.Path(path).read_bytes(); i = 0; blocks = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); blocks.append(data[i + 2:i + 2 + n]); i += 2 + n
    return blocks

def load_code(tap):
    """Return (start, bytes) of the first CODE block of a pasmo --tapbas tape."""
    blocks = tap_blocks(tap)
    for h, d in zip(blocks[::2], blocks[1::2]):
        if h[0] == 0 and h[1] == 3:
            start = h[14] | (h[15] << 8)
            return start, bytes(d[1:-1])
    raise SystemExit("no code block in %s" % tap)

class Machine:
    """Z80 + OUT/IN logging. self.outs = list of (t, port, value) with t = absolute T-state (frame_tick based)."""
    def __init__(self, tap, sym):
        self.sym = read_sym(sym)
        start, code = load_code(tap)
        self.m = z80.Z80Machine()
        self.m.set_memory_block(start, code)
        self.code_start, self.code_len = start, len(code)
        self.m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8]))
        self.outs = []
        self.ins = {}
        self.m.set_output_callback(self._out)
        self.m.set_input_callback(self._in)
        self.t = 0                      # absolute T-states executed so far
        self._t_base = 0

    def _now(self):
        # inside run(): elapsed in this run = budget - ticks_to_stop
        return self._t_base + (self._budget - self.m.ticks_to_stop)

    def _out(self, port, value):
        self.outs.append((self._now(), port, value))

    def _in(self, port):
        return self.ins.get(port & 0xFF, self.ins.get(port, 0xFF))

    def peek(self, addr, n=1):
        return bytes(self.m.memory[addr:addr + n])

    def poke(self, addr, data):
        self.m.set_memory_block(addr, bytes(data))

    def addr(self, name):
        return self.sym[name]

    def call(self, label, a=None, limit=2_000_000, bc=None, de=None, hl=None):
        """CALL label with A set; run until the RET trap. Returns T-states used. Raises if limit exceeded."""
        target = self.sym[label] if isinstance(label, str) else label
        stub = bytearray()
        if a is not None:
            stub += bytes([0x3E, a & 255])                   # ld a,n
        stub += bytes([0xCD, target & 255, target >> 8])     # call target
        stub += bytes([0xC3, TRAP & 255, TRAP >> 8])         # jp TRAP
        self.m.set_memory_block(SCRATCH, bytes(stub))
        self.m.pc = SCRATCH; self.m.sp = 0xFE00
        if bc is not None: self.m.bc = bc
        if de is not None: self.m.de = de
        if hl is not None: self.m.hl = hl
        used = 0
        self.m.set_breakpoint(TRAP)
        try:
            while used < limit:
                self._budget = 200_000
                self._t_base = self.t
                self.m.ticks_to_stop = self._budget
                self.m.run()
                step = self._budget - self.m.ticks_to_stop
                used += step; self.t += step
                if self.m.pc == TRAP:
                    return used - (7 if a is not None else 0) - 0   # subtract the ld a,n (7 T); call/jp counted in
        finally:
            self.m.clear_breakpoint(TRAP)
        raise SystemExit("call %s did not return within %d T (pc=%04x)" % (label, limit, self.m.pc))

    def iff1(self):
        return self.m.iff1

CALL_JP_T = 17 + 10   # T-states of the stub's `call` + `jp TRAP` included in Machine.call() results
