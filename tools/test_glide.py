#!/usr/bin/env python3
"""test_glide.py - M2.9b (4 Nov 2026): unit test of the camera glide in the 128K image (build/kea128.tap, pasmo --equ GLIDE=1).
Runs the REAL assembled routines on the Python Z80 core:
  glide_mark  at a known start state (opx/opy/oang/ofl), then the true state is moved as one game step would move it,
  glide_in    with ticks - step_t = 0..4 -> the camera (posx/posy/angle/fl_ph) must sit at start + (end - start) * k/5,
  glide_out   -> the true values are restored exactly.
Cases: forward move +38/256 on x, diagonal (+27, +27), negative move (-38 on y), angle +6 and -6 with wrap (angle 2 -> 252),
floor phase +38 with wrap (250 -> 32), and an ISR tick arriving between steps and glide_in (elapsed = 5 -> clamped to 4).
Tolerance: the Z80 uses 8-bit fractions (k*51/256 etc.), so |camera - exact| <= 1/256 cell and <= 1 angle unit.
Also checks that the 48K image has NO glide code (symbol absent) and that `steps` in the 128K image returns (0xC9) where the
48K halts (0x76). Exit 0 and 'RESULT PASS' when every check holds."""
import sys, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
ROOT = pathlib.Path(__file__).resolve().parent.parent

def sym(f): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / f).read_text(), re.M)}
def tap_blocks(path):
    data = pathlib.Path(path).read_bytes(); i = 0; out = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); out.append(data[i + 2:i + 2 + n]); i += 2 + n
    return out
def load(tapf):
    b = tap_blocks(ROOT / tapf)
    for h, d in zip(b[::2], b[1::2]):
        if h[0] == 0 and h[1] == 3 and len(d) > 30000: return h[14] | (h[15] << 8), bytes(d[1:-1])
    raise SystemExit("no code block in " + tapf)

S = sym("build/kea128.sym"); S48 = sym("build/kea48.sym")
START, CODE = load("build/kea128.tap")
mem0 = bytearray(65536); mem0[START:START + len(CODE)] = CODE
TRAP = 0x5B00
fails = []
def check(name, ok, info=""):
    print("%-64s %s  %s" % (name, "ok  " if ok else "FAIL", info))
    if not ok: fails.append(name)

check("48K image has no glide code", "glide_in" not in S48 and "glide_mark" not in S48, "symbols absent")
# steps: 48K has HALT (0x76) after `jp nc,st_two`; 128K has RET (0xC9)
S48START, C48 = load("build/kea48.tap"); m48 = bytearray(65536); m48[S48START:S48START + len(C48)] = C48
def after_jpnc(mem, steps, step_t, st_two):
    for a in range(steps, step_t):
        if mem[a] == 0xD2 and mem[a + 1] | (mem[a + 2] << 8) == st_two: return mem[a + 3]   # jp nc,st_two = D2 lo hi, then the next opcode
    return None
check("48K steps halts when no step is due", after_jpnc(m48, S48["steps"], S48["step_t"], S48["st_two"]) == 0x76, "opcode %s" % hex(after_jpnc(m48, S48["steps"], S48["step_t"], S48["st_two"]) or 0))
check("128K steps returns when no step is due (draws another frame)", after_jpnc(mem0, S["steps"], S["step_t"], S["st_two"]) == 0xC9, "opcode %s" % hex(after_jpnc(mem0, S["steps"], S["step_t"], S["st_two"]) or 0))

class M:
    def __init__(self):
        self.m = z80.Z80Machine(); self.m.set_memory_block(0, bytes(mem0)); self.m.set_memory_block(TRAP, b"\x00"); self.m.set_breakpoint(TRAP)
    def call(self, addr):
        m = self.m; m.sp = 0x7DFE; m.memory[0x7DFE] = TRAP & 255; m.memory[0x7DFF] = TRAP >> 8; m.pc = addr
        for _ in range(200):
            m.ticks_to_stop = 20000; m.run()
            if m.pc == TRAP: return
        raise SystemExit("runaway pc=%04x" % m.pc)
    def w16(self, a, v): self.m.memory[a] = v & 255; self.m.memory[a + 1] = (v >> 8) & 255
    def r16(self, a): return self.m.memory[a] | (self.m.memory[a + 1] << 8)
    def w8(self, a, v): self.m.memory[a] = v & 255
    def r8(self, a): return self.m.memory[a]

def s16(v): return v - 65536 if v > 32767 else v
def case(name, start, end, elapsed_list=(0, 1, 2, 3, 4), isr_extra=0):
    """start/end = (posx, posy, angle, fl_ph) in raw units; the step is start -> end."""
    for k in elapsed_list:
        mm = M()
        mm.w16(S["posx"], start[0]); mm.w16(S["posy"], start[1]); mm.w8(S["angle"], start[2]); mm.w8(S["fl_ph"], start[3])
        mm.call(S["glide_mark"])
        mm.w16(S["posx"], end[0]); mm.w16(S["posy"], end[1]); mm.w8(S["angle"], end[2]); mm.w8(S["fl_ph"], end[3])
        mm.w16(S["ticks"], 1000 + k + isr_extra); mm.w8(S["step_t"], 1000 & 255)
        mm.call(S["glide_in"])
        kk = min(k + isr_extra, 4); f = kk / 5.0
        got = (mm.r16(S["posx"]), mm.r16(S["posy"]), mm.r8(S["angle"]), mm.r8(S["fl_ph"]))
        exp = [start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f]
        da = ((end[2] - start[2] + 128) & 255) - 128; dfl = ((end[3] - start[3] + 128) & 255) - 128
        expa = (start[2] + da * f) % 256; expf = (start[3] + dfl * f) % 256
        okx = abs(got[0] - exp[0]) <= 1 and abs(got[1] - exp[1]) <= 1
        oka = min(abs(got[2] - expa), 256 - abs(got[2] - expa)) <= 1 and min(abs(got[3] - expf), 256 - abs(got[3] - expf)) <= 1
        mm.call(S["glide_out"])
        back = (mm.r16(S["posx"]), mm.r16(S["posy"]), mm.r8(S["angle"]), mm.r8(S["fl_ph"]))
        okb = back == end
        check("%s, elapsed %d/5%s" % (name, k, " (+1 ISR tick)" if isr_extra else ""), okx and oka and okb,
              "camera pos (%d,%d) exp (%.1f,%.1f) ang %d exp %.1f fl %d exp %.1f; restored %s" % (got[0], got[1], exp[0], exp[1], got[2], expa, got[3], expf, "yes" if okb else "NO %s" % (back,)))

P = lambda c, f: c * 256 + f
case("forward +38 on x", (P(3, 128), P(7, 128), 0, 10), (P(3, 128 + 38), P(7, 128), 0, 48))
case("diagonal +27 x, +27 y", (P(3, 128), P(7, 128), 32, 0), (P(3, 155), P(7, 155), 32, 38))
case("backward -38 on y (crossing a cell edge)", (P(5, 10), P(9, 20), 64, 100), (P(5, 10), P(8, 256 + 20 - 38), 64, 62))
case("turn right +6", (P(3, 128), P(7, 128), 100, 0), (P(3, 128), P(7, 128), 106, 0))
case("turn left -6 with wrap 2 -> 252", (P(3, 128), P(7, 128), 2, 0), (P(3, 128), P(7, 128), 252, 0))
case("floor phase wrap 250 -> 32", (P(3, 128), P(7, 128), 0, 250), (P(3, 128), P(7, 128), 0, 32))
case("ISR tick between steps and glide_in (elapsed 4+1 clamps to 4)", (P(3, 128), P(7, 128), 0, 0), (P(3, 166), P(7, 128), 0, 38), elapsed_list=(4,), isr_extra=1)
case("standing still (no change -> camera = true)", (P(3, 128), P(7, 128), 0, 0), (P(3, 128), P(7, 128), 0, 0))
print("RESULT", "PASS" if not fails else "FAIL %s" % fails)
sys.exit(1 if fails else 0)
