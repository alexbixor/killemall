#!/usr/bin/env python3
"""test_game_replay.py (lane G, 5 Nov 2026) - deterministic replay: the CURRENT 48K build (build/kea48.tap) and the REFERENCE
pre-G tape (build/night/pre_G/build/killemall48_m25.tap, the shipped m25 build) are both run on the Python Z80 core for
600 game steps on level 1 with the SAME fixed key script; posx/posy/angle/health/ammo/kills/shield + the whole 128-byte
things table are compared at steps 100, 300 and 600 (and the full state at every step as a stricter check). Same bytes = pass.
How a step is run: init_game (level 1 as assembled into the image), then per step: in_read is replaced by `ld a,bits / ret`
(the key script), `render` (builds the vis list the hitscan needs and advances nothing else), `game_tick` (one 0.1 s step:
movement, doors, enemies, pickups), ticks += 5 (the ISR would add 5 per step at 10 steps/s; va_walk reads bit 4 of ticks).
snd_fx is stubbed to `ret` (the beeper is blocking code that polls nothing we have). The script walks into enemies, turns,
strafes and fires so chase/attack/hitscan/damage/death paths all run (the imp at (3,2) and zombie at (7,10) of level 1).
usage: test_game_replay.py [ref.tap] [cur.tap]   exit 0 = identical; prints the compared values and RESULT.
"""
import sys, re, pathlib, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/night/pre_G/build/killemall48_m25.tap")
CUR = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "build/kea48.tap")
REFSYM = ROOT / "build/night/pre_G/build/kea48_m25.sym"
CURSYM = ROOT / "build/kea48.sym"
TRAP, SCR = 0x5EF0, 0x5EC0            # DRAM spare (state.asm): harness stub + trap, as every other test uses
STEPS, CHECK = 600, (100, 300, 600)

def symbols(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", path.read_text(), re.M)}

def code_block(tap):
    """(start, bytes) of the LAST CODE block of a tape (killemall48_m25.tap: the engine image is the only CODE block)."""
    data = tap.read_bytes(); i = 0; blocks = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); blocks.append(data[i + 2:i + 2 + n]); i += 2 + n
    res = None
    for h, d in zip(blocks, blocks[1:]):
        if h[0] == 0 and len(h) == 19 and h[1] == 3:
            length = h[12] | (h[13] << 8); start = h[14] | (h[15] << 8)
            res = (start, bytes(d[1:1 + length]))
    assert res, "no CODE block in %s" % tap
    return res

# key script per step: bits b0 fwd b1 back b2 left b3 right b4 fire b5 use b6 strafe L b7 strafe R (in_read contract)
def key_bits(step):
    if step < 15: return 0x01                 # walk forward (level 1 start faces east, x 3 y 7 -> corridor)
    if step < 22: return 0x04                 # turn left
    if step < 60: return 0x01 | (0x10 if step % 12 == 0 else 0)   # walk + a shot every 1.2 s
    if step < 70: return 0x08                 # turn right
    if step < 130: return 0x01 | 0x20 if step % 7 == 0 else 0x01   # walk, use doors
    if step < 160: return 0x40                # strafe left
    if step < 260: return (0x02 if step % 8 < 3 else 0x10)         # stand: back 3 steps (open the 0.19-cell gap), fire 5 steps
                                                                   # (12-step cooldown): the chasing imp/zombie arrive adjacent -> attack
                                                                   # timer -> damage; the gap lets the hitscan see them -> hits/kills
    if step < 300: return 0x04 | 0x01         # curve
    if step < 400: return 0x01 | (0x10 if step % 9 == 0 else 0)
    if step < 450: return 0x80                # strafe right
    if step < 520: return 0x08 | 0x01
    if step < 555: return 0x01 | 0x20 if step % 5 == 0 else 0x01
    return 0x00                               # stand still: the zombie that followed arrives, attacks (timer 25) -> damage, snd 4

class Run:
    def __init__(self, tap, symf):
        self.S = symbols(symf)
        start, code = code_block(tap)
        self.m = z80.Z80Machine(); self.m.set_memory_block(start, code)
        self.m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8]))
        self.m.set_memory_block(self.S["snd_fx"], bytes([0xC9]))      # no beeper
        self.call("init_game")
        self.m.set_memory_block(self.S["fire_cool"], bytes([0]))
    def call(self, label, limit=5_000_000):
        S = self.S
        self.m.set_memory_block(SCR, bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8]))
        self.m.pc = SCR; self.m.sp = 65008; used = 0
        self.m.set_breakpoint(TRAP)
        while used < limit and self.m.pc != TRAP:
            self.m.ticks_to_stop = 100_000; self.m.run(); used += 100_000 - self.m.ticks_to_stop
        self.m.clear_breakpoint(TRAP)
        assert self.m.pc == TRAP, "%s did not return (pc=%04x)" % (label, self.m.pc)
        return used
    def step(self, n):
        S, m = self.S, self.m
        m.set_memory_block(S["in_read"], bytes([0x3E, key_bits(n), 0xC9]))
        self.call("render")
        self.call("game_tick")
        t = m.memory[S["ticks"]] + 5                                  # 10 steps/s at 50 Hz: +5 ticks per step
        m.set_memory_block(S["ticks"], bytes([t & 255, (m.memory[S["ticks"] + 1] + (t >> 8)) & 255]))
    def state(self):
        S, m = self.S, self.m
        rd = lambda k, n=1: bytes(m.memory[S[k]:S[k] + n])
        return (rd("posx", 2), rd("posy", 2), rd("angle"), rd("health"), rd("ammo"), rd("kills"), rd("shield"), rd("keys"),
                rd("things", 128), rd("fire_cool"), rd("door_cool"))
    def pretty(self):
        S, m = self.S, self.m
        w = lambda k: m.memory[S[k]] | (m.memory[S[k] + 1] << 8)
        return "posx %.3f posy %.3f ang %d health %d ammo %d kills %d shield %d things %s" % (
            w("posx") / 256, w("posy") / 256, m.memory[S["angle"]], m.memory[S["health"]], m.memory[S["ammo"]],
            m.memory[S["kills"]], m.memory[S["shield"]], hashlib.sha256(bytes(m.memory[S["things"]:S["things"] + 128])).hexdigest()[:12])

def main():
    ref, cur = Run(REF, REFSYM), Run(CUR, CURSYM)
    print("ref %s (%d B code)  cur %s" % (REF.relative_to(ROOT), len(code_block(REF)[1]), CUR.relative_to(ROOT)))
    fails, first = 0, None
    for n in range(1, STEPS + 1):
        ref.step(n); cur.step(n)
        if ref.state() != cur.state() and first is None:
            first = n
        if n in CHECK:
            same = ref.state() == cur.state()
            print("step %3d: ref %s" % (n, ref.pretty()))
            print("          cur %s  -> %s" % (cur.pretty(), "SAME" if same else "DIFFERENT"))
            if not same: fails += 1
    if first is not None:
        print("first differing step: %d" % first); fails += 1
    else:
        print("every one of the %d steps identical (all compared bytes)" % STEPS)
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
