#!/usr/bin/env python3
"""m_mouse_test.py (lane M, 5 Nov 2026) - oracle A: the Z80 mouse_look of the 128K build (build/kea128.tap, pasmo --equ MOUSE=1)
against tools/m_mouse_ref.py, exhaustively: all 256 X counter values x 14 previous states (incl. the wraps 7Fh->80h, FFh->00h,
fraction carry/borrow) x 4 button states = 14,336 calls on the Python Z80 core (kosarev z80, the core of test_game_replay.py);
plus: opt_mouse = 0 leaves every byte alone and reads no port, in_read consumes the click latch only when opt_mouse <> 0,
T-states of both paths. Ports are served by an input callback (0FBDFh = X, 0FADFh = buttons, 0FFDFh = Y junk, 0xFE/31 = idle).
usage: .venv/bin/python tools/m_mouse_test.py > build/night/M_map.out ; exit 0 = 0 mismatches."""
import sys, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from m_mouse_ref import mouse_look_ref, MSHIFT
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAP = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/kea128.tap")
SYMF = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "build/kea128.sym")
TRAP, SCR = 0x5EF0, 0x5EC0            # DRAM spare (state.asm), as every other Z80-core harness

def symbols(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", path.read_text(), re.M)}

def code_block(tap):
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

S = symbols(SYMF)
for k in ("mouse_look", "mouse_last", "mouse_frac", "mouse_btn", "opt_mouse", "angle", "in_read", "opt_joy"):
    assert k in S, "symbol %s missing from %s (built without MOUSE=1?)" % (k, SYMF)
HAS_GLIDE = "oang" in S
start, code = code_block(TAP)
m = z80.Z80Machine(); m.set_memory_block(start, code)
m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8]))
port = {"x": 0, "btn": 0xFF}; reads = []
def on_in(p):
    reads.append(p)
    if p == 0xFBDF: return port["x"]
    if p == 0xFADF: return port["btn"]
    if p == 0xFFDF: return 0x5A                      # Y counter: must be ignored
    return 0xFF                                      # keyboard rows idle (no key), port 31 = no Kempston joystick
m.set_input_callback(on_in)

def call(label, limit=100000):
    m.set_memory_block(SCR, bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8]))
    m.pc = SCR; m.sp = 65008; used = 0
    m.set_breakpoint(TRAP)
    while used < limit and m.pc != TRAP:
        m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
    m.clear_breakpoint(TRAP)
    assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc)
    return used - 17 - 10                            # minus the stub's call + jp

def wr(label, v): m.set_memory_block(S[label], bytes([v & 0xFF]))
def rd(label): return m.memory[S[label]]
def setstate(angle, frac, last, btn, oang, opt=1):
    wr("angle", angle); wr("mouse_frac", frac); wr("mouse_last", last); wr("mouse_btn", btn); wr("opt_mouse", opt)
    if HAS_GLIDE: wr("oang", oang)
def getstate():
    return (rd("angle"), rd("mouse_frac"), rd("mouse_last"), rd("mouse_btn"), rd("oang") if HAS_GLIDE else 0)

print("tape %s  sym %s  MSHIFT %d  GLIDE %s" % (TAP.relative_to(ROOT), SYMF.relative_to(ROOT), MSHIFT, HAS_GLIDE))
print("mouse_look %04X mouse_last %04X mouse_frac %04X mouse_btn %04X opt_mouse %04X angle %04X" % tuple(S[k] for k in ("mouse_look", "mouse_last", "mouse_frac", "mouse_btn", "opt_mouse", "angle")))
# previous states: (angle, frac, last, btn, oang) - wraps and carries on purpose
PREV = [(0, 0, 0, 0, 0), (0, 0, 0x7F, 0, 0), (0, 0, 0x80, 0, 0), (10, 0, 0xFF, 0, 10), (10, 0xC0, 0, 0, 10), (10, 0x40, 0, 0, 7),
        (255, 0xFF, 0x7F, 0, 250), (128, 0x80, 0x10, 0x10, 128), (64, 0x3F, 0xF0, 0x20, 60), (200, 0xC1, 0x55, 0x30, 199),
        (1, 0x00, 0x01, 0, 1), (255, 0x00, 0xFE, 0, 0), (37, 0x7F, 0xAA, 0, 40), (0, 0xFF, 0xFF, 0, 0)]
BTNS = [0xFF, 0xFD, 0xFE, 0xFC]                      # none, left (b1 low), right (b0 low), both (Next wheel bits high)
mism, calls, tmin, tmax = 0, 0, 10 ** 9, 0
first = []
for prev in PREV:
    for x in range(256):
        for b in BTNS:
            setstate(*prev); port["x"], port["btn"] = x, b
            t = call("mouse_look"); calls += 1; tmin, tmax = min(tmin, t), max(tmax, t)
            got = getstate()
            exp = mouse_look_ref(prev[0], prev[1], prev[2], prev[3], x, b, prev[4])
            if not HAS_GLIDE: exp = exp[:4] + (0,)
            if got != exp:
                mism += 1
                if len(first) < 10: first.append((prev, x, b, got, exp))
print("A1 mapping: %d calls (14 states x 256 X x 4 buttons), %d mismatches; mouse_look ON path %d..%d T" % (calls, mism, tmin, tmax))
for f in first: print("   MISMATCH prev=%s x=%02X btn=%02X got=%s exp=%s" % f)
# spot values in plain words (from the same runs)
setstate(0, 0, 0, 0, 0); port["x"], port["btn"] = 4, 0xFF; call("mouse_look"); print("   X 0->4 from angle 0: angle %d frac %d (4 counts = 1 unit)" % getstate()[:2])
setstate(0, 0, 0x7F, 0, 0); port["x"] = 0x80; call("mouse_look"); print("   X 7F->80: angle %d frac %d (one count right = +64/256)" % getstate()[:2])
setstate(10, 0, 0xFF, 0, 10); port["x"] = 0x00; call("mouse_look"); print("   X FF->00 from angle 10: angle %d frac %d" % getstate()[:2])
setstate(10, 0xC0, 0, 0, 10); port["x"] = 1; call("mouse_look"); print("   X 0->1 with frac C0: angle %d frac %d (fraction carry)" % getstate()[:2])
setstate(10, 0x00, 0, 0, 10); port["x"] = 0xFF; call("mouse_look"); print("   X 0->FF (-1) from angle 10 frac 0: angle %d frac %d (borrow)" % getstate()[:2])
setstate(0, 0, 0, 0, 0); port["x"] = 0x80; call("mouse_look"); print("   X 0->80 (-128, the extreme): angle %d frac %d" % getstate()[:2])
# A2: opt_mouse = 0 -> nothing changes, no port read
mism0 = 0
for prev in PREV[:6]:
    for x in (0, 1, 0x80, 0xFF):
        setstate(*prev, opt=0); port["x"], port["btn"] = x, 0xFC; del reads[:]
        t0 = call("mouse_look")
        if getstate() != prev or reads: mism0 += 1
print("A2 opt_mouse=0: 24 calls, %d state changes, port reads %d, %d T" % (mism0, len(reads), t0))
# A3: in_read consumes the latch only when opt_mouse <> 0 (keyboard idle, opt_joy 0)
wr("opt_joy", 0); res = []
for opt, latch in ((1, 0x30), (1, 0x10), (1, 0x20), (0, 0x30), (1, 0)):
    wr("opt_mouse", opt); wr("mouse_btn", latch)
    m.set_memory_block(SCR, bytes([0xCD, S["in_read"] & 255, S["in_read"] >> 8, 0x32, 0xE0, 0x5E, 0xC3, TRAP & 255, TRAP >> 8]))
    m.pc = SCR; m.sp = 65008; m.set_breakpoint(TRAP); m.ticks_to_stop = 20000; m.run(); m.clear_breakpoint(TRAP)
    assert m.pc == TRAP
    res.append((opt, latch, m.memory[0x5EE0], rd("mouse_btn")))
ok3 = res == [(1, 0x30, 0x30, 0), (1, 0x10, 0x10, 0), (1, 0x20, 0x20, 0), (0, 0x30, 0, 0x30), (1, 0, 0, 0)]
print("A3 in_read latch: (opt, latch, A, latch after) %s -> %s" % (["%d %02X -> A %02X latch %02X" % r for r in res], "ok" if ok3 else "WRONG"))
total = mism + mism0 + (0 if ok3 else 1)
print("RESULT", "PASS 0 mismatches" if total == 0 else "FAIL %d" % total)
sys.exit(1 if total else 0)
