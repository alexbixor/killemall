#!/usr/bin/env python3
"""test48.py - cycle-level harness for the 48K engine using the Python Z80 core.

Loads the assembled binary (build/kea48.tap, code block at 32768) into a bare Z80, sets player state, calls `render`
once with a RET trap, then compares the produced screen bytes with the Python reference (tools/refcast.py geometry)
and prints T-states for the frame.  No emulator, no ROM: IM2/ints are off, `render` touches only RAM.
usage: test48.py [posx posy angle]  (cell units float, angle 0..255)
"""
import sys, os, pathlib, re, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80

ROOT = pathlib.Path(__file__).resolve().parent.parent
K128 = bool(os.environ.get("KEA128"))                      # 1 Nov: KEA128=1 -> run the SAME harness on the 128K image (kea128.tap + bank1.bin paged by 7FFD)
SYMF, TAPF = ("build/kea128.sym", "build/kea128.tap") if K128 else ("build/kea48.sym", "build/kea48.tap")
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / SYMF).read_text(), re.M)}

def tap_blocks(path):
    data = pathlib.Path(path).read_bytes(); i = 0; blocks = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); blocks.append(data[i + 2:i + 2 + n]); i += 2 + n
    return blocks

def load_code():
    blocks = tap_blocks(ROOT / TAPF)
    # headers: flag 0, type 3 = code; data block follows with flag 255
    for h, d in zip(blocks[::2], blocks[1::2]):
        if h[0] == 0 and h[1] == 3:
            start = h[14] | (h[15] << 8)
            return start, bytes(d[1:-1])
    raise SystemExit("no code block")

def scr_ascii(mem, y0=8, y1=104, step=4):
    for y in range(y0, y1, step):
        base = 0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        row = ""
        for bx in range(4, 28):
            b = mem[base + bx]
            row += "".join("#" if (b >> (7 - bit)) & 1 else "." for bit in range(0, 8, 2))
        print("%3d %s" % (y, row))

def run_until(m, trap, limit=60_000_000):
    """run() returns every ~100k ticks (event 8 = frame end); loop until PC sits on the trap."""
    used = 0
    m.set_breakpoint(trap)
    while used < limit:
        m.ticks_to_stop = 100_000
        ev = m.run()
        used += 100_000 - m.ticks_to_stop
        if m.pc == trap:
            m.clear_breakpoint(trap)
            return used
    raise SystemExit("trap not reached, pc=%04x" % m.pc)

def main():
    px, py, ang = (float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (3.5, 7.5, 0)
    start, code = load_code()
    m = z80.Z80Machine()
    m.set_memory_block(start, code)
    if K128:                                                   # simulated 128K paging at 49152 (same model as tools/test_128.py)
        b1 = (ROOT / "build/bank1.bin").read_bytes()
        banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1))}; cur = [0]
        def on_out(port, val):
            if port == 0x7FFD and (val & 7) != cur[0]:
                banks[cur[0]] = bytes(m.memory[0xC000:0x10000]); m.set_memory_block(0xC000, banks[val & 7]); cur[0] = val & 7
        m.set_output_callback(on_out); m.set_input_callback(lambda p: 0xFF)
    # init_game then render; trap: push a return address that holds a HALT-free spin (jp $) we detect by PC
    TRAP = 0x5EF0                                               # harness lives in the DRAM spare 0x5EC0..0x5EFF (M2.5C: page 0x6A is FTX)
    m.set_memory_block(TRAP, bytes([0xC3, 0xF0, 0x5E]))        # jp TRAP
    m.set_memory_block(0x5EC0, bytes([0xCD]) + SYM["init_game"].to_bytes(2, "little") + bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x5E]))
    m.pc = 0x5EC0; m.sp = 65008
    t_init = run_until(m, TRAP)
    print("init+render T", t_init)
    t_init = 50_000_000 - m.ticks_to_stop
    # now set the player and render again, measuring T-states
    ix, fx = int(px), int((px - int(px)) * 256); iy, fy = int(py), int((py - int(py)) * 256)
    m.set_memory_block(SYM["posx"], bytes([fx, ix])); m.set_memory_block(SYM["posy"], bytes([fy, iy]))
    m.set_memory_block(SYM["angle"], bytes([ang & 255]))
    if os.environ.get("NOTHINGS") and "fl_k" in SYM:
        m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))                       # M2.3: floor lines off (chk48 scans the checker)
        m.set_memory_block(SYM["cl_de"] + 1, bytes([0xAA, 0x55]))             # M2.5E: both floor fill words = the 0x55AA checker
        m.set_memory_block(SYM["cl_bc"] + 1, bytes([0xAA, 0x55]))             #        (the game's dot lattice is mostly 0x00 = a dark texel)
    if os.environ.get("NOTHINGS") and "things" in SYM:                       # T1: walls-only geometry check (sprites change the scan)
        m.set_memory_block(SYM["things"], bytes(128))
        m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))                  # and no weapon graphic over the floor
        m.set_memory_block(SYM["TEXPG"], bytes([0x5F]) * 16)                   # M2.5C: solid walls (SOLIDPG) -> exact checker scan in chk48
        m.set_memory_block(SYM["rd_shade"] + 1, bytes([0]))                    # M2.5C: no dark-side 0xAA dither (== checker on even rows)
    m.set_memory_block(0x5EC0, bytes([0xCD]) + SYM["render"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x5E]))
    m.pc = 0x5EC0; m.sp = 65008
    t = run_until(m, TRAP)
    print("render T-states %d  -> %.1f fps at 3.5 MHz (%.1f%% of a 69888-T frame)" % (t, 3_500_000 / t, 100.0 * t / 69888))
    mem = m.memory
    scr_ascii(mem)
    attrs = [mem[0x5800 + 32 * r + 4: 0x5800 + 32 * r + 28].hex() for r in range(1, 13)]
    print("attr row1", attrs[0]); print("attr row6", attrs[5])
    # per-column wall heights by scanning the screen (first non-black row in each 2px column)
    pathlib.Path(ROOT / "build/test48_scr.bin").write_bytes(bytes(mem[0x4000:0x5B00]))

if __name__ == "__main__":
    main()
