#!/usr/bin/env python3
"""test_frontend.py - cycle-level tests of the T2 lane (src/common/input.asm + frontend.asm) on the Python Z80 core.

Loads build/fe_test.tap (tools/fe_build.sh) at 32768 plus the real 48K ROM (tools/zesarux/48.rom, for the font) into a
bare Z80.  The keyboard and the Kempston port are emulated through the core's port hook (`set_input_callback`: the
callback receives the full 16-bit port; even ports answer the ULA keyboard rows selected by the high byte, port 31 the
joystick byte).  Interrupts: the menu loop does `ei; halt`; the harness detects the HALT, calls on_handle_active_int()
(IM2, vector table from the test main) and continues, one call = one 50 Hz frame.
Asserts: navigation moves the bright bar (edge-triggered), toggles flip the option bytes and the text, joystick
navigation/fire with opt_joy, redefine stores the scripted [port,mask] pairs (and BREAK aborts without saving),
rows 0..15 of the screen are never touched, in_read bits for the default keys / Kempston / BREAK, snd_fx 6 per move
and toggle, snd_menu_tick per frame; measures in_read (<= 600 T asserted), in_wait_key debounce, one menu frame.
Exit code 0 = all passed.  usage: .venv/bin/python tools/test_frontend.py
"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/fe_test.sym").read_text(), re.M)}
ROM = (ROOT / "tools/zesarux/48.rom").read_bytes()
ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]  # \x03 CAPS \x02 ENTER \x01 SPACE \x04 SYM
KEY = {ch: (r, b) for r, row in enumerate(ROWS) for b, ch in enumerate(row)}
KEY.update({"CAPS": (0, 0), "ENTER": (6, 0), "SPACE": (7, 0), "SYM": (7, 1)})
PORTHI = [0xFE, 0xFD, 0xFB, 0xF7, 0xEF, 0xDF, 0xBF, 0x7F]
FE_ANORM, FE_AHI, FE_AFLASH = 0x07, 0x4F, 0xCE
failures = []

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)

def tap_blocks(path):
    data = pathlib.Path(path).read_bytes(); i = 0; blocks = []
    while i + 2 <= len(data):
        n = data[i] | (data[i + 1] << 8); blocks.append(data[i + 2:i + 2 + n]); i += 2 + n
    return blocks

def load_code():
    blocks = tap_blocks(ROOT / "build/fe_test.tap")
    for h, d in zip(blocks[::2], blocks[1::2]):
        if h[0] == 0 and h[1] == 3:
            return h[14] | (h[15] << 8), bytes(d[1:-1])
    raise SystemExit("no code block")

class Machine:
    def __init__(self):
        self.m = z80.Z80Machine()
        self.m.set_memory_block(0, ROM)
        start, code = load_code()
        self.m.set_memory_block(start, code)
        self.rows = [0xFF] * 8          # keyboard rows, active low
        self.joy = 0x00                  # Kempston byte (0xFF = no interface)
        self.m.set_input_callback(self.inp)
        self.m.set_get_int_vector_callback(lambda: 0xFF)
        self.m.pc = start; self.m.sp = 65008
        self.halt_addr = SYM["fe_loop"] + 1   # the HALT after EI
    def inp(self, port):
        if (port & 0xFF) == 0x1F:
            return self.joy
        if (port & 1) == 0:
            v = 0xFF; hi = port >> 8
            for r in range(8):
                if not (hi >> r) & 1:
                    v &= self.rows[r]
            return v
        return 0xFF
    def press(self, *names):
        for n in names:
            r, b = KEY[n]; self.rows[r] &= ~(1 << b) & 0xFF
    def release(self, *names):
        for n in names:
            r, b = KEY[n]; self.rows[r] |= 1 << b
    def release_all(self):
        self.rows = [0xFF] * 8; self.joy = 0 if self.joy != 0xFF else 0xFF
    def run_until(self, addr, limit=50_000_000):
        """run to a breakpoint (handles HALT by delivering the IM2 interrupt); returns T-states used (int delivery not counted)."""
        used = 0; m = self.m
        m.set_breakpoint(addr)
        while used < limit:
            m.ticks_to_stop = 200_000
            m.run()
            used += 200_000 - m.ticks_to_stop
            if m.pc == addr and not m.halted:
                m.clear_breakpoint(addr); return used
            if m.halted:
                m.on_handle_active_int()
        raise SystemExit("breakpoint %04x not reached, pc=%04x" % (addr, m.pc))
    def to_halt(self):
        """run until the menu loop's HALT is reached (one frame of work done); returns T-states of the run."""
        t = self.run_until(self.halt_addr)
        self.m.step_over_breakpoint()                 # executes the HALT -> halted, pc after it
        return t
    def frame(self):
        """deliver the 50 Hz interrupt to the halted CPU and run the next frame up to its HALT; returns T-states (ISR + work + ei)."""
        assert self.m.halted, "frame(): CPU is not halted (pc=%04x)" % self.m.pc
        self.m.on_handle_active_int()
        return self.to_halt()
    def frames(self, n):
        for _ in range(n):
            self.frame()
    def tap(self, *names, hold=2, gap=2):
        self.press(*names); self.frames(hold); self.release(*names); self.frames(gap)
    def run_ticks(self, n):
        """advance time without breakpoints (blocking code such as in_wait_key / fe_exit): wakes a halted CPU first,
        then delivers the interrupt whenever a HALT is reached."""
        m = self.m; left = n
        while left > 0:
            if m.halted:
                m.on_handle_active_int()
            chunk = min(left, 70_000); m.ticks_to_stop = chunk; m.run(); left -= chunk - m.ticks_to_stop
    def press_blocking(self, *names):
        """press keys that make the menu leave its frame loop (START / REDEFINE): run, release, run."""
        self.press(*names); self.run_ticks(150_000); self.release(*names); self.run_ticks(300_000)
    def byte(self, name):
        return self.m.memory[SYM[name]]
    def attr_row(self, r):
        return list(self.m.memory[0x5800 + 32 * r: 0x5800 + 32 * r + 32])
    def text_row(self, r):
        """decode a character row (16..23) from the pixel bytes with the ROM font."""
        mem = self.m.memory; out = ""
        for c in range(32):
            base = 0x4000 + ((r & 0x18) << 8) + ((r & 7) << 5) + c
            g = bytes(mem[base + 256 * k] for k in range(8))
            out += GLYPH.get(g, "?" if any(g) else " ")
        return out
    def top_hash(self):
        mem = self.m.memory
        return hash(bytes(mem[0x4000:0x5000]) + bytes(mem[0x5800:0x5A00]))

GLYPH = {bytes(ROM[15616 + 8 * i: 15616 + 8 * i + 8]): chr(32 + i) for i in range(96)}

def bar_row(mc):
    """index of the attribute row (16..23) carrying the bright bar, -1 if none."""
    rows = [r for r in range(16, 24) if mc.attr_row(r)[0] == FE_AHI]
    return rows[0] if len(rows) == 1 else -1

def main():
    mc = Machine(); m = mc.m
    # ---------------------------------------------------------------- boot: title, menu drawn, first HALT
    t_boot = mc.to_halt()
    top0 = mc.top_hash()
    print("boot (cls + title + fe_draw_all) T", t_boot)
    for r in range(16, 24):
        print("row %2d %-32s attr %02X..%02X" % (r, mc.text_row(r), mc.attr_row(r)[0], mc.attr_row(r)[31]))
    check(bar_row(mc) == 16 and mc.attr_row(16)[2:12] == [FE_AFLASH] * 10 and mc.attr_row(16)[12] == FE_AHI, "initial bar on row 16 (START GAME), label flashing")
    check(all(mc.attr_row(r) == [FE_ANORM] * 32 for r in range(17, 23)), "rows 17..22 plain attributes")
    check(mc.text_row(16).strip() == "START GAME" and mc.text_row(17).strip() == "MUSIC: ON" and mc.text_row(21).strip() == "REDEFINE KEYS", "labels drawn with the ROM font")
    check(mc.text_row(23).strip() == "Q/A/CURSORS MOVE  SPACE SELECTS", "key hint on row 23")
    # ---------------------------------------------------------------- frame cost (idle, no keys)
    m.on_handle_active_int()
    t_isr = mc.run_until(SYM["fe_frame"])
    t_work = mc.to_halt()
    print("menu frame T: ISR %d + work (snd_menu_tick stub + fe_keys/in_read + dispatch + ei) %d = %d" % (t_isr, t_work, t_isr + t_work))
    ticks0 = mc.byte("stub_tick_count"); mc.frames(10)
    check(mc.byte("stub_tick_count") == ticks0 + 10, "snd_menu_tick called once per frame (10 frames)")
    # ---------------------------------------------------------------- navigation
    fx0 = mc.byte("stub_fx_count")
    mc.tap("6")                                   # cursor down
    check(bar_row(mc) == 17 and mc.byte("fe_cur") == 1 and mc.attr_row(16) == [FE_ANORM] * 32, "6 (cursor down) moves the bar to row 17")
    check(mc.attr_row(17)[9:11] == [FE_AFLASH] * 2 and mc.attr_row(17)[11] == FE_AHI, "value cell 'ON' flashes on the current option row")
    mc.press("A"); mc.frames(10); mc.release("A"); mc.frames(2)
    check(bar_row(mc) == 18 and mc.byte("fe_cur") == 2, "A held 10 frames moves exactly one row (edge-triggered)")
    mc.tap("7"); mc.tap("Q")
    check(bar_row(mc) == 16 and mc.byte("fe_cur") == 0, "7 and Q move up")
    mc.tap("Q")
    check(bar_row(mc) == 21 and mc.byte("fe_cur") == 5, "up from the top wraps to REDEFINE KEYS (row 21)")
    mc.tap("6")
    check(bar_row(mc) == 16 and mc.byte("fe_cur") == 0, "down from the bottom wraps to START GAME")
    check(mc.byte("stub_fx_count") == fx0 + 6 and mc.byte("stub_fx_last") == 6, "snd_fx 6 on each of the 6 moves")
    # ---------------------------------------------------------------- toggles
    mc.tap("6"); fx0 = mc.byte("stub_fx_count")
    mc.tap("SPACE")
    check(mc.byte("opt_music") == 0 and mc.text_row(17).strip() == "MUSIC: OFF", "SPACE toggles MUSIC -> OFF (text + opt_music)")
    check(mc.attr_row(17)[9:12] == [FE_AFLASH] * 3 and mc.attr_row(17)[12] == FE_AHI, "flashing cells follow the new value width")
    mc.tap("ENTER")
    check(mc.byte("opt_music") == 1 and mc.text_row(17).strip() == "MUSIC: ON", "ENTER toggles MUSIC back ON")
    check(mc.byte("stub_fx_count") == fx0 + 2, "snd_fx 6 on each toggle")
    mc.tap("6"); mc.tap("SPACE")
    check(mc.byte("opt_sfx") == 0 and mc.text_row(18).strip() == "SOUND FX: OFF", "SOUND FX -> OFF")
    mc.tap("6"); mc.tap("SPACE")
    check(mc.byte("opt_detail") == 0 and mc.text_row(19).strip() == "DETAIL: LOW", "DETAIL -> LOW")
    mc.tap("6"); mc.tap("SPACE")
    check(mc.byte("opt_joy") == 1 and mc.text_row(20).strip() == "CONTROLS: KEMPSTON", "CONTROLS -> KEMPSTON")
    # ---------------------------------------------------------------- joystick navigation (opt_joy = 1)
    mc.joy = 0x08; mc.frames(2); mc.joy = 0x00; mc.frames(2)          # up
    check(bar_row(mc) == 19 and mc.byte("fe_cur") == 3, "joystick up moves the bar up")
    mc.joy = 0x04; mc.frames(2); mc.joy = 0x00; mc.frames(2)          # down
    mc.joy = 0x04; mc.frames(2); mc.joy = 0x00; mc.frames(2)
    check(bar_row(mc) == 21 and mc.byte("fe_cur") == 5, "joystick down x2 -> REDEFINE KEYS")
    mc.joy = 0x08; mc.frames(2); mc.joy = 0x00; mc.frames(2)
    mc.joy = 0x10; mc.frames(2); mc.joy = 0x00; mc.frames(2)          # fire on CONTROLS
    check(mc.byte("opt_joy") == 0 and mc.text_row(20).strip() == "CONTROLS: KEYBOARD", "joystick fire toggles CONTROLS back to KEYBOARD")
    mc.joy = 0x04; mc.frames(2); mc.joy = 0x00; mc.frames(2)
    check(mc.byte("fe_cur") == 4, "joystick ignored once opt_joy = 0")
    # BREAK is swallowed in the menu
    mc.tap("CAPS", "SPACE")
    check(mc.byte("fe_cur") == 4 and mc.byte("opt_joy") == 0, "CAPS+SPACE in the menu does nothing")
    # ---------------------------------------------------------------- redefine: abort with BREAK
    keys0 = bytes(m.memory[SYM["in_keys"]:SYM["in_keys"] + 16])
    check(keys0 == bytes([0xFB, 1, 0xFD, 1, 0xDF, 2, 0xDF, 1, 0x7F, 1, 0x7F, 4, 0xFE, 2, 0xFE, 4]), "default in_keys Q A O P SPACE M Z X (M2.3)")
    mc.tap("6"); mc.press_blocking("SPACE")                                # enters fe_redef (blocking from here)
    print("redefine screen:"); [print("row %2d %s" % (r, mc.text_row(r))) for r in range(16, 24)]
    check(mc.text_row(16).strip().startswith("FORWARD") and "Q" in mc.text_row(16)[11:14] and mc.text_row(21).strip() == "PRESS THE KEY FOR EACH ACTION", "redefine screen lists actions with current keys")
    check(mc.attr_row(16)[0] == FE_AHI and mc.attr_row(16)[11] == FE_AFLASH and mc.attr_row(16)[14] == FE_AHI, "first action highlighted, its key cells flashing")
    mc.press("W"); mc.run_ticks(300_000); mc.release("W"); mc.run_ticks(300_000)
    check(mc.text_row(16)[11] == "W" and bytes(m.memory[SYM["fe_tmpk"]:SYM["fe_tmpk"] + 2]) == bytes([0xFB, 0x02]), "W accepted for FORWARD (shown, stored in fe_tmpk)")
    mc.press("CAPS", "SPACE"); mc.run_ticks(300_000); mc.release("CAPS", "SPACE"); mc.run_ticks(300_000)
    mc.to_halt()
    check(bytes(m.memory[SYM["in_keys"]:SYM["in_keys"] + 16]) == keys0 and mc.text_row(16).strip() == "START GAME", "BREAK aborts redefine: in_keys unchanged, menu redrawn")
    # ---------------------------------------------------------------- redefine: full scripted sequence
    mc.frames(2); mc.press_blocking("SPACE")
    seq = ["W", "S", "A", "D", "ENTER", "SPACE", "N", "M"]
    for k in seq:
        mc.press(k); mc.run_ticks(300_000); mc.release(k); mc.run_ticks(300_000)
    mc.to_halt()
    want = bytes([0xFB, 2, 0xFD, 2, 0xFD, 1, 0xFD, 4, 0xBF, 1, 0x7F, 1, 0x7F, 8, 0x7F, 4])
    got = bytes(m.memory[SYM["in_keys"]:SYM["in_keys"] + 16])
    print("in_keys after redefine:", got.hex())
    check(got == want, "redefine W S A D ENTER SPACE N M stored the right [port,mask] pairs")
    check(mc.text_row(16).strip() == "START GAME" and bar_row(mc) == 21 and mc.byte("fe_cur") == 5, "menu redrawn after redefine, cursor still on REDEFINE KEYS")
    # redefined keys drive the menu too: S (back) = down (wraps 5 -> 0)
    mc.tap("S")
    check(mc.byte("fe_cur") == 0, "redefined back key (S) moves down in the menu (wrap to START GAME)")
    # ---------------------------------------------------------------- START returns 0, options + keys printed as hex
    while mc.byte("fe_cur") != 0:
        mc.tap("Q")
    mc.press_blocking("SPACE"); mc.run_ticks(400_000)
    print("after START:"); [print("row %2d %s" % (r, mc.text_row(r))) for r in range(16, 21)]
    opt = bytes(m.memory[SYM["opt_music"]:SYM["opt_music"] + 4]).hex().upper()
    check(mc.text_row(16).strip() == "OPT " + opt and opt == "01000000", "START: option bytes printed as hex (%s)" % opt)
    check(mc.text_row(17).strip() == "KEYS" and mc.text_row(18) == got.hex().upper(), "START: in_keys printed as hex on row 18")
    check(mc.top_hash() == top0, "rows 0..15 (pixels + attributes) never touched")
    # ---------------------------------------------------------------- worst-case menu frame: a cursor move (redraws 2 rows)
    mc.press_blocking("K")                                                 # ANY KEY -> fe_run again (menu redrawn)
    mc.to_halt(); mc.frames(2)
    mc.press("6"); m.on_handle_active_int(); t_move = mc.to_halt(); mc.release("6"); mc.frames(2)
    check(mc.byte("fe_cur") == 1, "frame with a cursor move handled")
    print("menu frame T with a cursor move (2 rows redrawn, ISR included): %d" % t_move)
    # ---------------------------------------------------------------- fe_pause: RESUME / QUIT TO MENU (direct call)
    m3 = Machine(); mm3 = m3.m
    stub3 = 0x7E00; trap3 = 0x7F00
    # IM2 like the real start code (vector table 0xFE00.. = 0xFD -> jp isr at 0xFDFD), then: call fe_pause; ld (7F00),a; halt; jr $
    mm3.set_memory_block(65024, bytes([253]) * 257); mm3.set_memory_block(65021, bytes([0xC3]) + SYM["isr"].to_bytes(2, "little"))
    mm3.set_memory_block(stub3, bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xCD]) + SYM["fe_pause"].to_bytes(2, "little") + bytes([0x32, 0x00, 0x7F, 0x76, 0x18, 0xFD]))
    mm3.set_memory_block(trap3, bytes([0xAA]))
    mm3.pc = stub3; mm3.sp = 0x7E00
    m3.to_halt(); m3.frames(2)                                             # keys held at entry are swallowed: idle frames first
    for r in range(16, 24):
        print("pause row %2d %-32s attr %02X" % (r, m3.text_row(r), m3.attr_row(r)[0]))
    check(m3.text_row(16).strip() == "RESUME" and m3.text_row(22).strip() == "QUIT TO MENU" and bar_row(m3) == 16, "fe_pause: RESUME on top, QUIT TO MENU on row 22, 7 items")
    # a key held while entering the menu (the BREAK that opened it) must not fire: enter with SPACE down, release, idle
    m3.press("SPACE"); mm3.pc = stub3; mm3.sp = 0x7E00; mm3.halted = 0; m3.to_halt(); m3.frames(3); m3.release("SPACE"); m3.frames(2)
    check(mm3.halted and mm3.pc == m3.halt_addr + 1 and mm3.memory[trap3] == 0xAA, "fe_pause: SPACE held while entering (BREAK) is swallowed, menu still up")
    m3.tap("Q")
    check(m3.byte("fe_cur") == 6 and bar_row(m3) == 22, "fe_pause: up from RESUME wraps to QUIT TO MENU")
    m3.press_blocking("SPACE"); m3.run_ticks(100_000)
    check(mm3.memory[trap3] == 1 and stub3 <= mm3.pc < stub3 + 16, "fe_pause returns A = 1 for QUIT TO MENU (pc back in the caller)")
    mm3.set_memory_block(trap3, bytes([0xAA])); mm3.pc = stub3; mm3.sp = 0x7E00; mm3.halted = 0
    m3.to_halt(); m3.frames(2); m3.press_blocking("ENTER"); m3.run_ticks(100_000)    # idle frame first: keys down at entry are swallowed
    check(mm3.memory[trap3] == 0 and stub3 <= mm3.pc < stub3 + 16, "fe_pause returns A = 0 for RESUME (pc back in the caller)")
    # ---------------------------------------------------------------- in_read unit tests (direct calls)
    m2 = Machine(); mm = m2.m
    stub = 0x7E00; trap = 0x7F00
    mm.set_memory_block(stub, bytes([0xCD]) + SYM["in_read"].to_bytes(2, "little") + bytes([0xC3]) + trap.to_bytes(2, "little"))
    mm.set_memory_block(trap, bytes([0xC3]) + trap.to_bytes(2, "little"))
    def in_read(keys=(), joy=0x00, opt_joy=0):
        m2.rows = [0xFF] * 8; m2.press(*keys); m2.joy = joy
        mm.set_memory_block(SYM["opt_joy"], bytes([opt_joy]))
        mm.pc = stub; mm.sp = 0x7E00; mm.hl = 0x1234; mm.bc = 0x5678
        m2.run_until(SYM["in_read"])
        t = m2.run_until(stub + 3)                    # from the first in_read instruction to the return address (RET included)
        m2.run_until(trap)
        return mm.a, t, mm.memory[SYM["in_break"]], (mm.hl, mm.bc)
    cases = [((), 0x00), (("Q",), 0x01), (("A",), 0x02), (("O",), 0x04), (("P",), 0x08), (("SPACE",), 0x10), (("M",), 0x20),
             (("Z",), 0x40), (("X",), 0x80), (("Q", "P", "SPACE"), 0x19), (("CAPS", "SPACE"), 0x10)]
    tmax = 0
    for keys, want_a in cases:
        a, t, brk, regs = in_read(keys); tmax = max(tmax, t)
        check(a == want_a and brk == (1 if keys == ("CAPS", "SPACE") else 0) and regs == (0x1234, 0x5678),
              "in_read keys %-18s -> %02X in_break %d (%d T)" % (",".join(keys) or "-", a, brk, t))
    a, t_joy, brk, _ = in_read((), 0x0A, 1); check(a == 0x05, "in_read Kempston 0x0A (left+up) opt_joy=1 -> %02X (%d T)" % (a, t_joy))
    a, t, _, _ = in_read(("A",), 0x11, 1); check(a == 0x1A, "in_read Kempston 0x11 (right+fire) + key A -> %02X" % a)
    a, t, _, _ = in_read((), 0x1F, 1); check(a == 0x1F, "in_read Kempston all five -> %02X" % a)
    a, t_nojoy, _, _ = in_read((), 0xFF, 1); check(a == 0x00, "in_read Kempston 0xFF (no interface) ignored -> %02X (%d T)" % (a, t_nojoy))
    a, t, _, _ = in_read((), 0x0A, 0); check(a == 0x00, "in_read Kempston ignored when opt_joy=0")
    tmax = max(tmax, t_joy, t_nojoy)
    print("in_read T-states: keyboard %d, Kempston %d, Kempston absent %d, max %d" % (cases and in_read(("Q",))[1], t_joy, t_nojoy, tmax))
    check(tmax <= 600, "in_read max %d T <= 600" % tmax)
    # in_wait_key: debounce + name; a 10,000 T blip (< 78,000 T debounce) is ignored
    mm.set_memory_block(stub, bytes([0xCD]) + SYM["in_wait_key"].to_bytes(2, "little") + bytes([0xC3]) + trap.to_bytes(2, "little"))
    m2.rows = [0xFF] * 8; mm.pc = stub; mm.sp = 0x7E00; m2.run_ticks(20_000)      # past the all-keys-up wait
    m2.press("K"); m2.run_ticks(10_000); m2.release("K"); m2.run_ticks(100_000)
    check(mm.pc != trap, "in_wait_key: 10,000 T blip on K rejected (still waiting)")
    m2.press("K"); m2.run_ticks(200_000); m2.release("K"); m2.run_until(trap)
    check(mm.a == ord("K") and mm.b == 0xBF and mm.c == 0x04 and not (mm.f & 1), "in_wait_key: K held -> B=%02X C=%02X name %r, NC" % (mm.b, mm.c, chr(mm.a)))
    mm.pc = stub; m2.run_ticks(20_000); m2.press("SPACE"); m2.run_ticks(200_000); m2.release("SPACE"); m2.run_until(trap)
    check(mm.a == 1 and mm.b == 0x7F and mm.c == 0x01, "in_wait_key: SPACE -> name code 1, B=7F C=01")
    mm.pc = stub; m2.run_ticks(20_000); m2.press("CAPS", "SPACE"); m2.run_ticks(200_000); m2.release("CAPS", "SPACE"); m2.run_until(trap)
    check(mm.f & 1, "in_wait_key: CAPS+SPACE -> carry (abort)")
    mm.pc = stub; m2.run_ticks(20_000); m2.press("CAPS"); m2.run_ticks(200_000); m2.release("CAPS"); m2.run_until(trap)
    check(mm.a == 3 and mm.b == 0xFE and mm.c == 0x01 and not (mm.f & 1), "in_wait_key: CAPS alone -> name code 3, B=FE C=01")
    print("summary: %d failures" % len(failures))
    for f in failures:
        print("  FAILED:", f)
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
