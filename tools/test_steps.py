#!/usr/bin/env python3
"""test_steps.py - M2.9 (4 Nov 2026): unit test of kea48.asm `steps` (fixed 10 game steps per second from the 50 Hz counter).

Runs the REAL assembled routine (build/kea48.tap or, with KEA128=1, build/kea128.tap) on the Python Z80 core. The test plays
the part of the machine around it:
  * a "frame" = the render time, simulated by adding R ticks to the 50 Hz counter `ticks`, then a call to `steps`;
  * game_tick is trapped (breakpoint) and only counted, then a RET is emulated;
  * the HALT inside `steps` is trapped: one interrupt is simulated (ticks + 1) and execution continues after the HALT.
Scenarios (10 simulated seconds = 500 ticks each, after a 1 s warm-up):
  R = 1, 2, 3, 4 ticks/frame   (faster than a step: Next at 28 MHz)  -> exactly 10 steps/s, never more than 1 per frame
  R = 5, 6, 7, 8, 9 ticks/frame (48K ~5.5, 128K ~7.7)               -> exactly 10 steps/s (+-1 for the window edge)
  R = 13 ticks/frame (very slow scene)                               -> capped: 2 steps per frame = 7.7 steps/s, no burst
  stall of 150 ticks (3 s pause menu / tape load) then R = 5          -> the first frame after it runs exactly 2 steps
  ticks wrap 0xFFFF -> 0x0000 inside a run                            -> still 10 steps/s
Exit 0 and 'RESULT PASS' when every check holds.
"""
import os, sys, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80

ROOT = pathlib.Path(__file__).resolve().parent.parent
K128 = bool(os.environ.get("KEA128"))
SYMF, TAPF = ("build/kea128.sym", "build/kea128.tap") if K128 else ("build/kea48.sym", "build/kea48.tap")
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / SYMF).read_text(), re.M)}

def tap_blocks(path):
    data = pathlib.Path(path).read_bytes(); i = 0; out = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); out.append(data[i + 2:i + 2 + n]); i += 2 + n
    return out

def load():
    b = tap_blocks(ROOT / TAPF)
    for h, d in zip(b[::2], b[1::2]):
        if h[0] == 0 and h[1] == 3 and len(d) > 30000:
            return h[14] | (h[15] << 8), bytes(d[1:-1])
    raise SystemExit("no code block")

START, CODE = load()
STEPS, GT, TICKS, STEPT = SYM["steps"], SYM["game_tick"], SYM["ticks"], SYM["step_t"]
mem0 = bytearray(65536); mem0[START:START + len(CODE)] = CODE
# the HALT(s) inside steps (between steps and step_t)
HALTS = [a for a in range(STEPS, STEPT) if mem0[a] == 0x76]
TRAP = 0x5B00                                                    # printer buffer: harmless return address
GLIDE = "glide_in" in SYM                                        # M2.9b (128K/Next): steps RETURNS when no step is due (another frame
assert HALTS or GLIDE, "no HALT found in steps"                   # is drawn, camera glides) instead of HALTing for the next interrupt

class Sim:
    def __init__(self, t0=0):
        self.m = z80.Z80Machine(); self.m.set_memory_block(0, bytes(mem0))
        self.m.set_memory_block(TRAP, b"\x00")
        for a in [GT, TRAP] + HALTS: self.m.set_breakpoint(a)
        self.t = t0; self.set_ticks(t0); self.m.memory[STEPT] = t0 & 255
    def ticks(self): return self.t                               # absolute time; memory holds the low 16 bits (wraps)
    def set_ticks(self, v): self.t = v; self.m.memory[TICKS] = v & 255; self.m.memory[TICKS + 1] = (v >> 8) & 255
    def frame(self, render):
        """render ticks pass, then main calls steps; returns the number of game_tick calls.
        GLIDE build: a frame shorter than a step just returns 0 steps (main draws again); the test's clock is the same."""
        self.set_ticks(self.ticks() + render)
        m = self.m; m.sp = 0x7E00
        m.memory[0x7DFE] = TRAP & 255; m.memory[0x7DFF] = TRAP >> 8; m.sp = 0x7DFE
        m.pc = STEPS; n = 0; guard = 0
        while True:
            m.ticks_to_stop = 20000; m.run(); guard += 1
            assert guard < 5000, "runaway pc=%04x" % m.pc
            if m.pc == TRAP: return n
            if m.pc == GT:                                       # count, emulate RET
                n += 1; sp = m.sp; m.pc = m.memory[sp] | (m.memory[sp + 1] << 8); m.sp = sp + 2
            elif m.pc in HALTS:                                  # one 50 Hz interrupt: ticks + 1, continue after HALT
                self.set_ticks(self.ticks() + 1); m.pc += 1

fails = []
def check(name, ok, info):
    print("%-58s %s  %s" % (name, "ok  " if ok else "FAIL", info))
    if not ok: fails.append(name)

def run(render, seconds=10, t0=0):
    s = Sim(t0)
    for _ in range(60):                                          # warm-up 1+ s
        s.frame(render)
        if s.ticks() - t0 >= 50: break
    a = s.ticks(); steps = 0; per = []
    while s.ticks() - a < seconds * 50:
        k = s.frame(render); steps += k; per.append(k)
    el = (s.ticks() - a) / 50
    return steps / el, per, s

print("image %s: steps 0x%04X game_tick 0x%04X ticks 0x%04X step_t 0x%04X halts %s glide %s"
      % (TAPF, STEPS, GT, TICKS, STEPT, ["0x%04X" % h for h in HALTS], GLIDE))
for r in (1, 2, 3, 4):
    rate, per, _ = run(r)
    check("fast machine, render %d tick(s)/frame" % r, abs(rate - 10) <= 0.2 and max(per) == 1,
          "%.2f steps/s, max %d per frame" % (rate, max(per)))
for r in (5, 6, 7, 8, 9, 10):
    rate, per, _ = run(r)
    check("normal machine, render %d ticks/frame" % r, abs(rate - 10) <= 0.2 and max(per) <= 2,
          "%.2f steps/s, steps per frame %s" % (rate, sorted(set(per))))
rate, per, _ = run(13)
check("slow scene, render 13 ticks/frame (cap 2 per frame)", abs(rate - 2 * 50 / 13) <= 0.3 and max(per) == 2,
      "%.2f steps/s (expected %.2f), max %d" % (rate, 100 / 13, max(per)))
s = Sim(); [s.frame(5) for _ in range(20)]
s.set_ticks(s.ticks() + 150); k = s.frame(5); k2 = s.frame(5)
check("3 s stall (pause / tape) then normal", k == 2 and k2 <= 2, "first frame %d steps, second %d" % (k, k2))
rate, per, s = run(6, t0=0xFFFF - 300)
check("ticks counter wraps 0xFFFF->0 during the run", abs(rate - 10) <= 0.2, "%.2f steps/s, end ticks 0x%04X" % (rate, s.ticks() & 0xFFFF))
print("RESULT", "PASS" if not fails else "FAIL %s" % fails)
sys.exit(1 if fails else 0)
