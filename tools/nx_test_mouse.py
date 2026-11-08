#!/usr/bin/env python3
"""nx_test_mouse.py (lane N5, 8 Nov 2026) - oracles of the edition B mouse look + vertical look (src/next/mouse_next.asm).

  ref   oracle A (-> build/night/N5_ref.out): the assembled mouse_look_b (build/next/main_b_n5.bin, MOUSE_B=1) is run on the
        Python Z80 core (kosarev z80, as tools/m_mouse_test.py) with the ports served by a callback: all 256 X counter values
        x 4 starting fractions x 6 (ang, last) states (wraps 7Fh->80h, FFh->00h, ang 1023->0, 0->1023) x 4 button states,
        plus 256 Y values x 3 horizons (clamps 16/80) = exhaustive, compared with the Python model below: 0 mismatches.
        Also: opt_mouse_b = 0 -> no byte changes, no port read, T-states OFF and ON (oracle E part 1), read_keys latch
        consumption, look_keys_b (I toggle + debounce, W/S/E), set_horizon_b clamp for all 256 inputs.
  live  oracles C, E (fps), F (-> N5_live.out, N5_timing.out, N5_mouse.mp4): ZEsarUX TBBlue --vo xwindows under Xvfb with
        --enablekempstonmouse running build/next/killemall_b_n5.nex (the real main_loop), the pointer driven by xdotool:
        right -> ang up, left -> ang down, up/down -> horizon_row, left click -> ammo - 1 and weapon frame 1, right click
        in front of the door -> door cell opened, I key toggles opt_mouse_b with debounce, OFF -> nothing moves;
        fps ON vs OFF over 3 s each. Frames grabbed over ZRCP -> PNG -> ffmpeg mp4.
usage: .venv/bin/python tools/nx_test_mouse.py ref|live"""
import os, re, sys, time, pathlib, socket, subprocess
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
NIGHT = ROOT / "build/night"
import nx_build

MSHIFT_B, VSHIFT_B, DBNC_B = 8, 7, 10
VL_MIN, VL_MAX, VL_DEF = 16, 80, 48
KEY_FIRE, KEY_USE = 16, 32


def s8(v):
    v &= 255
    return v - 256 if v >= 128 else v


def clamp_h(a):
    """set_horizon_b: A is an int8-wrapped byte; 128..255 (negative) -> VL_MIN"""
    a &= 255
    if a >= 128 or a < VL_MIN:
        return VL_MIN
    if a > VL_MAX:
        return VL_MAX
    return a


def mouse_look_ref(ang, frac, last, ylast, hrow, vfrac, btn, x, y, b):
    """the Python model of mouse_look_b (opt ON) -> (ang, frac, last, ylast, hrow, vfrac, btn, moved)"""
    dx = s8(x - last)
    acc = dx << MSHIFT_B                       # s16 = whole units : 1/256 units
    lo = (frac + (acc & 255))
    carry = lo >> 8
    frac = lo & 255
    units = ((acc >> 8) + carry) & 255         # adc a,0 on the high byte (int8 arithmetic)
    moved = 0
    if units:
        ang = (ang + s8(units)) & 1023
        moved = 1
    dy = s8(y - ylast)
    accy = dy << VSHIFT_B
    lo = vfrac + (accy & 255)
    carry = lo >> 8
    vfrac = lo & 255
    hrow = clamp_h(hrow + ((accy >> 8) & 255) + carry)
    if not (b & 1):
        btn |= KEY_USE
    if not (b & 2):
        btn |= KEY_FIRE
    return (ang, frac, x, y, hrow, vfrac, btn, moved)


# ---------------------------------------------------------------- oracle A: the Z80 core
def oracle_ref():
    import z80
    out = []
    def log(s):
        print(s, flush=True); out.append(s)
    S = nx_build.read_syms(ROOT / "build/next/main_b_n5.sym")
    code = (ROOT / "build/next/main_b_n5.bin").read_bytes()
    for k in ("mouse_look_b", "look_keys_b", "set_horizon_b", "read_keys", "opt_mouse_b", "mouse_last", "mouse_frac", "mouse_btn",
              "horizon_row", "mouse_ylast", "vl_frac", "mouse_dbnc", "ang", "g_moved", "g_keys", "ticks", "g_step_t"):
        assert k in S, "symbol %s missing" % k
    log("nx_test_mouse ref %s: main_b_n5.bin %d bytes at 8000h; mouse_look_b %04X look_keys_b %04X set_horizon_b %04X read_keys %04X; MSHIFT_B %d VSHIFT_B %d" % (
        time.strftime("%H:%M:%SZ", time.gmtime()), len(code), S["mouse_look_b"], S["look_keys_b"], S["set_horizon_b"], S["read_keys"], S["MSHIFT_B"], S["VSHIFT_B"]))
    TRAP, SCR = 0x5EF8, 0x5EE8
    m = z80.Z80Machine(); m.set_memory_block(0x8000, code)
    m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8]))
    port = {"x": 0, "y": 0, "btn": 0xFF, "rows": {}}; reads = []
    def on_in(p):
        reads.append(p)
        if p == 0xFBDF: return port["x"]
        if p == 0xFFDF: return port["y"]
        if p == 0xFADF: return port["btn"]
        if (p & 255) == 0xFE: return port["rows"].get(p >> 8, 0xFF)
        return 0xFF
    m.set_input_callback(on_in)
    def call(label, limit=100000):
        m.set_memory_block(SCR, bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8]))
        m.pc = SCR; m.sp = 0x5F00; used = 0
        m.set_breakpoint(TRAP)
        while used < limit and m.pc != TRAP:
            m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
        m.clear_breakpoint(TRAP)
        assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc)
        return used - 17 - 10
    def wr(label, v): m.set_memory_block(S[label], bytes([v & 255]))
    def wr16(label, v): m.set_memory_block(S[label], bytes([v & 255, (v >> 8) & 255]))
    def rd(label): return m.memory[S[label]]
    def rd16(label): return m.memory[S[label]] | (m.memory[S[label] + 1] << 8)
    def setstate(ang, frac, last, ylast, hrow, vfrac, btn, opt=1):
        wr16("ang", ang); wr("mouse_frac", frac); wr("mouse_last", last); wr("mouse_ylast", ylast)
        wr("horizon_row", hrow); wr("vl_frac", vfrac); wr("mouse_btn", btn); wr("opt_mouse_b", opt); wr("g_moved", 0)
        m.set_memory_block(S["horizon_row"] - 1, b"\0")      # vl_pad
    def getstate():
        return (rd16("ang"), rd("mouse_frac"), rd("mouse_last"), rd("mouse_ylast"), rd("horizon_row"), rd("vl_frac"), rd("mouse_btn"), rd("g_moved"))
    # A1: X exhaustive
    STATES = [(0, 0), (0, 0x7F), (0, 0x80), (10, 0xFF), (1023, 0), (1020, 0x10)]
    FRACS = [0, 0x40, 0xC0, 0xFF]
    BTNS = [0xFF, 0xFD, 0xFE, 0xFC]
    mism = calls = 0; tmin, tmax = 10 ** 9, 0; first = []
    for ang, last in STATES:
        for frac in FRACS:
            for x in range(256):
                for b in BTNS:
                    setstate(ang, frac, last, 0x20, 48, 0, 0)
                    port["x"], port["y"], port["btn"] = x, 0x20, b
                    t = call("mouse_look_b"); calls += 1; tmin, tmax = min(tmin, t), max(tmax, t)
                    got = getstate()
                    exp = mouse_look_ref(ang, frac, last, 0x20, 48, 0, 0, x, 0x20, b)
                    if got != exp:
                        mism += 1
                        if len(first) < 8: first.append(((ang, frac, last), x, b, got, exp))
    log("A1 X mapping: %d calls (6 (ang,last) states x 4 fractions x 256 X x 4 buttons), %d mismatches; ON path %d..%d T" % (calls, mism, tmin, tmax))
    for f in first: log("   MISMATCH state=%s x=%02X btn=%02X got=%s exp=%s" % f)
    # A2: Y exhaustive at three horizons incl. the clamps, with fractions
    mism2 = calls2 = 0; first2 = []
    for hrow in (48, 16, 80, 17, 79):
        for vfrac in (0, 0x80, 0xFF):
            for ylast in (0, 0x80):
                for y in range(256):
                    setstate(100, 0, 0x33, ylast, hrow, vfrac, 0)
                    port["x"], port["y"], port["btn"] = 0x33, y, 0xFF
                    call("mouse_look_b"); calls2 += 1
                    got = getstate(); exp = mouse_look_ref(100, 0, 0x33, ylast, hrow, vfrac, 0, 0x33, y, 0xFF)
                    if got != exp:
                        mism2 += 1
                        if len(first2) < 8: first2.append(((hrow, vfrac, ylast), y, got, exp))
    log("A2 Y mapping: %d calls (5 horizons x 3 fractions x 2 ylast x 256 Y), %d mismatches (clamp %d..%d)" % (calls2, mism2, VL_MIN, VL_MAX))
    for f in first2: log("   MISMATCH state=%s y=%02X got=%s exp=%s" % f)
    # spot values in words
    setstate(0, 0, 0, 0, 48, 0, 0); port["x"], port["y"], port["btn"] = 1, 0, 0xFF; call("mouse_look_b"); log("   X 0->1 from ang 0: ang %d frac %d moved %d (1 count = 1 unit)" % (getstate()[0], getstate()[1], getstate()[7]))
    setstate(0, 0, 0x7F, 0, 48, 0, 0); port["x"] = 0x80; call("mouse_look_b"); log("   X 7F->80: ang %d (+1)" % getstate()[0])
    setstate(0, 0, 0xFF, 0, 48, 0, 0); port["x"] = 0x00; call("mouse_look_b"); log("   X FF->00 from ang 0: ang %d (+1)" % getstate()[0])
    setstate(0, 0, 0, 0, 48, 0, 0); port["x"] = 0xFF; call("mouse_look_b"); log("   X 0->FF (-1) from ang 0: ang %d (wrap to 1023)" % getstate()[0])
    setstate(1023, 0, 0, 0, 48, 0, 0); port["x"] = 1; call("mouse_look_b"); log("   X 0->1 from ang 1023: ang %d (wrap to 0)" % getstate()[0])
    setstate(0, 0, 0, 0, 48, 0, 0); port["x"] = 0x80; call("mouse_look_b"); log("   X 0->80 (-128): ang %d" % getstate()[0])
    setstate(0, 0, 0, 0, 48, 0, 0); port["x"] = 0; port["y"] = 1; call("mouse_look_b"); log("   Y 0->1 from horizon 48 frac 0: horizon %d vl_frac %d (half a row)" % (getstate()[4], getstate()[5]))
    port["y"] = 2; call("mouse_look_b"); log("   Y 1->2: horizon %d vl_frac %d (one row per 2 counts)" % (getstate()[4], getstate()[5]))
    setstate(0, 0, 0, 0, 48, 0, 0); port["y"] = 0x80; call("mouse_look_b"); log("   Y 0->80 (-128 = look down hard): horizon %d (clamped %d)" % (getstate()[4], VL_MIN))
    setstate(0, 0, 0, 0, 48, 0, 0); port["y"] = 0x7F; call("mouse_look_b"); log("   Y 0->7F (+127): horizon %d (clamped %d)" % (getstate()[4], VL_MAX))
    setstate(0, 0, 0, 0, 48, 0, 0); port["y"] = 0; port["btn"] = 0xFD; call("mouse_look_b"); log("   left button (b1 low): latch %02X (KEY_FIRE 10h)" % getstate()[6])
    port["btn"] = 0xFE; call("mouse_look_b"); log("   right button (b0 low) added: latch %02X (KEY_FIRE|KEY_USE 30h)" % getstate()[6])
    setstate(0, 0, 0, 0, 48, 0, 0); port["btn"] = 0xF0; call("mouse_look_b"); log("   wheel bits only (F0h): latch %02X (ignored)" % getstate()[6])
    # A3: OFF path
    mism0 = 0; t0 = 0
    for ang, last in STATES:
        for x in (0, 1, 0x80, 0xFF):
            setstate(ang, 0x55, last, 0x11, 48, 0x22, 0, opt=0); port["x"], port["y"], port["btn"] = x, 0x99, 0xFC; del reads[:]
            before = getstate(); t0 = call("mouse_look_b")
            if getstate() != before or reads: mism0 += 1
    log("A3 opt_mouse_b=0: 24 calls, %d state changes, %d port reads, %d T" % (mism0, len(reads), t0))
    # A4: read_keys latch consumption: no key pressed, latch 30h; (ticks - g_step_t) < STEP_B -> OR but keep; >= STEP_B -> OR and clear
    res4 = []
    for latch, ticks_lo, step_t in ((0x30, 7, 5), (0x30, 10, 5), (0x10, 4, 0), (0x20, 5, 0), (0, 9, 0)):
        wr("mouse_btn", latch); wr("ticks", ticks_lo); wr("g_step_t", step_t); port["rows"] = {}
        call("read_keys"); res4.append((latch, ticks_lo - step_t, rd("g_keys"), rd("mouse_btn")))
    exp4 = [(0x30, 2, 0x30, 0x30), (0x30, 5, 0x30, 0), (0x10, 4, 0x10, 0x10), (0x20, 5, 0x20, 0), (0, 9, 0, 0)]
    ok4 = res4 == exp4
    log("A4 read_keys latch: (latch, ticks since step, g_keys, latch after) %s -> %s" % (["%02X %d -> %02X %02X" % r for r in res4], "ok" if ok4 else "WRONG expected %s" % exp4))
    # A5: look_keys_b: I toggle with debounce, re-base; W/S/E
    ok5 = True; notes = []
    wr("opt_mouse_b", 0); wr("mouse_dbnc", 0); wr("horizon_row", 48); port["x"], port["y"] = 0x77, 0x66; wr("mouse_last", 0); wr("mouse_ylast", 0)
    port["rows"] = {0xDF: 0xFF ^ 4}; call("look_keys_b")                     # I down
    notes.append("I press: opt %d dbnc %d last %02X ylast %02X" % (rd("opt_mouse_b"), rd("mouse_dbnc"), rd("mouse_last"), rd("mouse_ylast")))
    ok5 &= rd("opt_mouse_b") == 1 and rd("mouse_dbnc") == DBNC_B and rd("mouse_last") == 0x77 and rd("mouse_ylast") == 0x66
    for _ in range(20): call("look_keys_b")                                   # held 20 frames: no second toggle
    ok5 &= rd("opt_mouse_b") == 1 and rd("mouse_dbnc") == DBNC_B
    notes.append("held 20 frames: opt %d dbnc %d" % (rd("opt_mouse_b"), rd("mouse_dbnc")))
    port["rows"] = {}
    for _ in range(5): call("look_keys_b")                                    # released 5 frames
    port["rows"] = {0xDF: 0xFF ^ 4}; call("look_keys_b")                     # pressed again too early
    ok5 &= rd("opt_mouse_b") == 1
    notes.append("released 5, pressed: opt %d dbnc %d (too early: no toggle)" % (rd("opt_mouse_b"), rd("mouse_dbnc")))
    port["rows"] = {}
    for _ in range(DBNC_B): call("look_keys_b")
    port["rows"] = {0xDF: 0xFF ^ 4}; call("look_keys_b")
    ok5 &= rd("opt_mouse_b") == 0
    notes.append("released %d, pressed: opt %d (toggled OFF)" % (DBNC_B, rd("opt_mouse_b")))
    port["rows"] = {0xFB: 0xFF ^ 2}; wr("horizon_row", 48)
    for _ in range(40): call("look_keys_b")
    ok5 &= rd("horizon_row") == VL_MAX; notes.append("W held 40 frames from 48: horizon %d (clamp %d)" % (rd("horizon_row"), VL_MAX))
    port["rows"] = {0xFD: 0xFF ^ 2}
    for _ in range(100): call("look_keys_b")
    ok5 &= rd("horizon_row") == VL_MIN; notes.append("S held 100 frames: horizon %d (clamp %d)" % (rd("horizon_row"), VL_MIN))
    port["rows"] = {0xFB: 0xFF ^ 4}; call("look_keys_b")
    ok5 &= rd("horizon_row") == VL_DEF; notes.append("E: horizon %d (re-centred)" % rd("horizon_row"))
    port["rows"] = {}; t_lk = call("look_keys_b")
    notes.append("look_keys_b idle %d T" % t_lk)
    log("A5 look_keys_b: %s -> %s" % ("; ".join(notes), "ok" if ok5 else "WRONG"))
    # A6: set_horizon_b all 256 inputs
    bad6 = 0
    for a in range(256):
        m.set_memory_block(SCR, bytes([0x3E, a, 0xCD, S["set_horizon_b"] & 255, S["set_horizon_b"] >> 8, 0xC3, TRAP & 255, TRAP >> 8]))
        m.pc = SCR; m.sp = 0x5F00; m.set_breakpoint(TRAP); m.ticks_to_stop = 20000; m.run(); m.clear_breakpoint(TRAP)
        if rd("horizon_row") != clamp_h(a): bad6 += 1
    log("A6 set_horizon_b: 256 inputs, %d wrong (int8 -128..-1 -> 16, 0..15 -> 16, 16..80 kept, 81..127 -> 80)" % bad6)
    # sizes
    size_ml = S["look_keys_b"] - S["mouse_look_b"]; size_lk = S["set_horizon_b"] - S["look_keys_b"]; size_sh = S["mouse_next_end"] - S["set_horizon_b"]
    log("SIZE mouse_next.asm: mouse_look_b %d B + look_keys_b %d B + set_horizon_b %d B = %d B; main_b.asm hooks: code_end %04Xh vs N4 9D75h (+%d B: start init, 2 calls, read_keys latch)" % (
        size_ml, size_lk, size_sh, S["mouse_next_end"] - S["mouse_look_b"], S["code_end"], S["code_end"] - 0x9D75))
    total = mism + mism2 + mism0 + (0 if ok4 else 1) + (0 if ok5 else 1) + bad6
    log("RESULT %s" % ("PASS 0 mismatches" if total == 0 else "FAIL %d" % total))
    (NIGHT / "N5_ref.out").write_text("\n".join(out) + "\n")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "ref"
    if what == "ref":
        sys.exit(oracle_ref())
    import nx_test_mouse_live
    sys.exit(nx_test_mouse_live.main(sys.argv[2:]))
