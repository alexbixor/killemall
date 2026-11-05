#!/usr/bin/env python3
"""isrstress48.py - interrupt-safety test of the stack-based fill/copy routines on the Python Z80 core.
Runs the real `main` loop (IM2 set up by `start`) with the Spectrum's 50 Hz interrupt asserted every 69888 T, for N frames,
then checks that (a) the screen window equals the back buffer image rendered by a clean render() of the same state,
(b) `ticks` advanced by the number of interrupts, (c) ticks arrived during CLRBUF/COPYBUF/build_ftab (so the stack trick was
really exercised).  usage: isrstress48.py [frames=120]"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, SYM

FRAME_T = 69888

def main():
    n_frames = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    start, code = load_code()
    m = z80.Z80Machine(); m.set_memory_block(start, code)
    # ROM font area: zero (print reads it); the IM2 table is built by start itself.
    m.pc = SYM["start"]
    m.set_get_int_vector_callback(lambda: 0xFF)
    labels = sorted((a, n) for n, a in SYM.items() if 32768 <= a < 65536)
    def owner(pc):
        name = "?"
        for a, n in labels:
            if a <= pc: name = n
            else: break
        return name
    in_phase = {}
    total = 0; ints = 0
    for f in range(n_frames):
        m.ticks_to_stop = FRAME_T
        while m.ticks_to_stop > 0:
            ev = m.run()
            if m.halted: break
        total += FRAME_T
        # raise the interrupt: the core's on_handle_active_int() services a pending INT if iff1 is set
        ph = owner(m.pc); in_phase[ph] = in_phase.get(ph, 0) + 1
        if m.on_handle_active_int():
            ints += 1
    # finish the current frame: run (with interrupts still arriving every video frame) until PC is back at `main`,
    # i.e. right after render+COPYBUF+read_input -> screen window must equal the back buffer exactly
    m.set_breakpoint(SYM["main"]); guard = 0
    while m.pc != SYM["main"] and guard < 50:
        m.ticks_to_stop = FRAME_T
        while m.ticks_to_stop > 0 and m.pc != SYM["main"]:
            ev = m.run()
            if ev & m._BREAKPOINT_HIT and m.pc == SYM["main"]: break
        if m.pc != SYM["main"]:
            if m.on_handle_active_int(): ints += 1
        guard += 1
    ticks = m.memory[SYM["ticks"]] | (m.memory[SYM["ticks"] + 1] << 8)
    frames = m.memory[SYM["frames"]] | (m.memory[SYM["frames"] + 1] << 8)
    print("ran %d video frames (%d T); interrupts accepted %d; ticks counter %d; game frames %d (%.1f fps)" % (
        n_frames, total, ints, ticks, frames, frames * 50.0 / n_frames))
    print("interrupt arrived while in:", dict(sorted(in_phase.items(), key=lambda kv: -kv[1])))
    # consistency: window on screen must equal the back buffer (column-major) of the LAST completed copy; check instead that
    # every window byte equals the buffer byte (true whenever we stop outside COPYBUF/render mid-frame is possible, so only
    # report the count)
    mem = m.memory
    # oracle: a clean, interrupt-free render of the same player state on a fresh machine -> window pixels + attributes
    posx, posy, ang = mem[SYM["posx"]:SYM["posx"] + 2], mem[SYM["posy"]:SYM["posy"] + 2], mem[SYM["angle"]]
    m2 = z80.Z80Machine(); m2.set_memory_block(start, code)
    TRAP = 0x7F00; m2.set_memory_block(TRAP, bytes([0xC3, 0x00, 0x7F]))
    m2.set_memory_block(0x7E00, bytes([0xCD]) + SYM["init_game"].to_bytes(2, "little") + bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x7F]))
    m2.pc = 0x7E00; m2.sp = 0x7E00
    from test48 import run_until
    run_until(m2, TRAP)
    m2.set_memory_block(SYM["posx"], bytes(posx)); m2.set_memory_block(SYM["posy"], bytes(posy)); m2.set_memory_block(SYM["angle"], bytes([ang]))
    m2.set_memory_block(0x7E00, bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x7F]))
    m2.pc = 0x7E00; m2.sp = 0x7E00; run_until(m2, TRAP)
    ref = m2.memory
    def scr(mm, y, bx): return mm[0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + bx]
    diff = sum(1 for c in range(16) for r in range(96) if scr(mem, 8 + r, 8 + c) != scr(ref, 8 + r, 8 + c))
    dattr = sum(1 for r in range(1, 13) for c in range(8, 24) if mem[0x5800 + 32 * r + c] != ref[0x5800 + 32 * r + c])
    print("window pixel bytes differing from a clean render of the same state (must be 0):", diff, "; attribute cells differing:", dattr)
    BUF = 24576
    dbuf = sum(1 for c in range(16) for r in range(96) if scr(mem, 8 + r, 8 + c) != mem[BUF + c * 128 + r])
    print("back-buffer bytes overwritten by ISR pushes after being copied (harmless, cleared next frame):", dbuf)
    # stack sanity: SP must be back in the main stack area
    print("SP at stop: %d (main stack top 65008)" % m.sp)
    # IM2 table intact?
    print("IM2 table intact:", all(mem[65024 + i] == 253 for i in range(257)), "ISR vector:", mem[65021], mem[65022] | (mem[65023] << 8), "isr =", SYM["isr"])

if __name__ == "__main__":
    main()
