#!/usr/bin/env python3
"""t1_isr_test.py - run the real `start` entry for N frames in the Python core with the 50 Hz interrupt asserted every
69888 T (same method as tools/isrstress48.py) and check `ticks` keeps counting while enemies chase/attack."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM

def main():
    start, code = load_code()
    m = z80.Z80Machine()
    m.set_memory_block(start, code)
    m.set_memory_block(SYM["snd_fx"], bytes([0xC9]))          # beeper would take ms of blocking: stubbed here
    m.pc = SYM["start"]; m.sp = 65008
    m.set_get_int_vector_callback(lambda: 0xFF)
    labels = sorted((a, n) for n, a in SYM.items() if 27904 <= a < 65536)
    def owner(pc):
        name = "?"
        for a, n in labels:
            if a <= pc: name = n
            else: break
        return name
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    ints = 0; missed = {}
    for win in range(n):
        m.ticks_to_stop = 69888
        while m.ticks_to_stop > 0:
            m.run()
            if m.halted: break
        if m.on_handle_active_int(): ints += 1
        else: missed[owner(m.pc)] = missed.get(owner(m.pc), 0) + 1
        if win % 25 == 24:
            t = m.memory[SYM["ticks"]] | m.memory[SYM["ticks"] + 1] << 8
            hp = m.memory[SYM["health"]]; st = m.memory[SYM["things"] + 5]; fr = m.memory[SYM["frames"]] | m.memory[SYM["frames"] + 1] << 8
            print("frame %3d: ints %3d ticks %3d frames %3d health %3d imp0 state %d pc in %s" % (win + 1, ints, t, fr, hp, st, owner(m.pc)))
    print("interrupts not accepted (iff1 clear) by routine:", missed)
    print("RESULT", "PASS" if ints >= n - 5 else "FAIL")

if __name__ == "__main__":
    main()
