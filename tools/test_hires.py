#!/usr/bin/env python3
"""test_hires.py - lane S (6 Nov 2026) static-scene oracle for the 128K HIRES (2-px column) zombie blitter prototype
(tools/build128_hires.sh: build/kea128_hires.tap + build/bank1.bin + build/bank3.bin). Python Z80 core + the 7FFDh paging model
of tools/test_flip.py (banks 0/1/3/7). For each scene (zombie dead-centre at 1.0 / 1.5 / 2.5 cells, offset half a cell, wall between)
render runs twice: once with the hi-res pass stubbed out (walls only, pass 2 of the vis loop = the FLIP build's picture is
NOT used - the old draw_sprite stays reachable for non-zombies) and once for real; the BUF difference is compared with a Python
model of the blitter (same tables, same art, same depth rule) pixel for pixel. Checks: (a) changed pixels == model, (b) every
changed 2-px column has zbuf < hv on its ray (depth), (c) nothing outside BUF / the window changed (bank 0, screen HUD rows,
bank 3 code), (d) bank 0 paged + BANKM bank bits 0 after the pass, (e) 30 frames with INTs every 69,888 T: ticks == 30.
Also prints T-states: render with no things, with 1 zombie at 1.0/1.5/2.5 cells, 3 zombies at 1.5 (old draw_sprite via the
default build build/kea128.tap for the same scenes). Output also to build/night/S_test_hires.out; exit 0 = all checks pass."""
import sys, re, struct, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import z80, tapdump
from gen_hires import model_frames
OUT = open(ROOT / "build/night/S_test_hires.out", "w"); fails = []
def say(s): print(s); print(s, file=OUT, flush=True)
def check(ok, msg):
    say(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)
def syms(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / p).read_text(), re.M)}
def code_of(tap):
    bl = tapdump.blocks((ROOT / tap).read_bytes())
    return next((struct.unpack_from("<H", b, 14)[0], bytes(bl[i + 1][1:1 + struct.unpack_from("<H", b, 12)[0]])) for i, b in enumerate(bl) if b[0] == 0 and b[1] == 3)
BANKM = 23388; TRAP, SCR = 0x5EC0, 0x5ED0
PXRAY = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 7, 7, 7]

class Mach:
    def __init__(self, tap, sym, bank3=None):
        self.S = syms(sym); start, code = code_of(tap)
        self.m = m = z80.Z80Machine(); m.set_memory_block(start, code)
        b1 = (ROOT / "build/bank1.bin").read_bytes()
        self.banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1)), 7: bytes(16384)}
        if bank3 is not None:
            b3 = (ROOT / bank3).read_bytes(); self.banks[3] = bytes(0x3000) + b3 + bytes(16384 - 0x3000 - len(b3))
        self.cur = 0; self.outs = []
        m.set_output_callback(self.on_out); m.set_input_callback(lambda p: 0xFF)
    def on_out(self, port, val):
        self.outs.append((port, val))
        if port == 0x7FFD and (val & 7) != self.cur:
            self.banks[self.cur] = bytes(self.m.memory[0xC000:0x10000]); b = val & 7
            if b not in self.banks: self.banks[b] = bytes(16384)
            self.m.set_memory_block(0xC000, self.banks[b]); self.cur = b
    def bank(self, n): return bytes(self.m.memory[0xC000:0x10000]) if self.cur == n else self.banks[n]
    def call(self, label, a=None, limit=6_000_000):
        S, m = self.S, self.m
        stub = (bytes([0x3E, a]) if a is not None else b"") + bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8])
        m.set_memory_block(SCR, stub); m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8])); m.pc = SCR; m.sp = S["FSTACK"]
        m.set_breakpoint(TRAP); used = 0
        while used < limit and m.pc != TRAP:
            m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
        m.clear_breakpoint(TRAP); assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc); return used
    def set_player(self, px, py, ang):
        S = self.S
        self.m.set_memory_block(S["posx"], struct.pack("<HH", int(px * 256), int(py * 256))); self.m.set_memory_block(S["angle"], bytes([ang & 255]))
    def clear_things(self): self.m.set_memory_block(self.S["things"], bytes(16 * 8))
    def set_thing(self, i, typ, x, y, state=0):
        self.m.set_memory_block(self.S["things"] + 8 * i, bytes([typ]) + struct.pack("<HH", int(x * 256), int(y * 256)) + bytes([state, 30, 0]))
    def buf(self): return bytes(self.m.memory[self.S["BUF"]:self.S["BUF"] + 2304])
    def zbuf(self): return bytes(self.m.memory[self.S["zbuf"]:self.S["zbuf"] + 64])
    def vis(self): return bytes(self.m.memory[self.S["vis"]:self.S["vis"] + 6 * self.m.memory[self.S["nvis"]]])

# ---------------- Python model of the bank-3 blitter (S_design.md 3..5)
FRAMES = model_frames()
def enemy_h(hv): c = hv >> 2; a = hv - c; c >>= 2; return (a + c) & 255
def model(vis_entry, zb, frame):
    """-> set of (bytecol, row, bitmask) pixels the blitter sets white (code 3) or black (code 1): {(bc,row): (and,or)} per 2-px"""
    hv, c0, nc = vis_entry[0], vis_entry[1] - 256 if vis_entry[1] > 127 else vis_entry[1], vis_entry[2]
    hd = enemy_h(hv) & 254
    vstep = round(hd * 256 / 48); top = ((48 + (hv >> 1)) << 8) - (hd << 8)
    rowtab = []
    acc = top
    for v in range(49):
        r = acc >> 8 if acc >= 0 else -1
        rowtab.append(0 if acc < 0 else min(96, r)); acc += vstep
    n2 = max(1, round(hd / 3)) if hd else 0
    ustep = 8192 // n2 if n2 else 0
    cx = c0 + (nc >> 1); k0 = (3 * cx + 1 - n2) >> 1; kend = min(k0 + n2, 96)
    out = {}
    if kend <= 0 or k0 >= 96: return out
    uacc = (-k0) * ustep if k0 < 0 else 0
    for k in range(max(k0, 0), kend):
        ray = 8 * ((2 * k) // 24) + PXRAY[(2 * k) % 24]
        if zb[ray] <= hv:
            u = (uacc >> 8) & 31
            v0 = 0
            mask = (0xC0, 0x30, 0x0C, 0x03)[k & 3]
            for b in FRAMES[frame][u]:
                if b == 0: break
                code, vend = b & 3, b >> 2
                r0, r1 = rowtab[v0], rowtab[vend]; v0 = vend
                if code == 0 or r1 == r0: continue
                for r in range(r0, r1):
                    out[(k >> 2, r)] = (out.get((k >> 2, r), (0xFF, 0))[0] & ~mask & 0xFF if code == 1 else out.get((k >> 2, r), (0xFF, 0))[0],
                                        (out.get((k >> 2, r), (0xFF, 0))[1] | mask) if code == 3 else (out.get((k >> 2, r), (0xFF, 0))[1] & ~mask))
        uacc += ustep
    return out
def apply_model(ref, pix):
    b = bytearray(ref)
    for (bc, r), (andm, orm) in pix.items():
        b[bc * 96 + r] = (b[bc * 96 + r] & andm) | orm
    return bytes(b)

H = Mach("build/kea128_hires.tap", "build/kea128_hires.sym", "build/bank3.bin")
D = Mach("build/kea128.tap", "build/kea128.sym")
for M in (H, D):
    M.call("bank_init"); M.call("init_game", limit=8_000_000); M.m.set_memory_block(M.S["draw_weapon"], b"\xc9")   # pistol off: sprite cost alone
    M.m.set_memory_block(M.S["fl_frame"], b"\xc9")                                                              # no copy phase: BUF is the result
check("hr_pass" in H.S and "hr_pass" not in D.S, "HIRES build has hr_pass (lowcode.asm), default build has not")
hb3 = H.bank(3); check(hb3[0x3DFD:0x3E00] == bytes([0xC3, H.S["isr"] & 255, H.S["isr"] >> 8]) and hb3[0x3E00:0x3F01] == bytes([0xFD] * 257), "bank 3 carries the IM2 mirror (jp isr at FDFDh, 257 x FDh at FE00h)")
# frame id in bank 3 = index of the vis entry's 16x24 pointer in spr_table[4..7]
sprt = [struct.unpack_from("<H", bytes(H.m.memory[H.S["spr_table"]:H.S["spr_table"] + 36]), 2 * i)[0] for i in range(18)]
def scene(M, things, px=3.5, py=7.5, ang=0):
    M.set_player(px, py, ang); M.clear_things()
    for i, (typ, x, y) in enumerate(things): M.set_thing(i, typ, x, y)
tcost = {}
for name, things in (("none", []), ("z1.0", [(2, 4.5, 7.5)]), ("z1.5", [(2, 5.0, 7.5)]), ("z2.5", [(2, 6.0, 7.5)]),
                     ("z1.5off", [(2, 5.0, 8.0)]), ("z3x1.5", [(2, 5.0, 7.5), (2, 5.0, 6.9), (2, 5.0, 8.1)]),
                     ("zwall", [(2, 8.5, 7.5)])):
    # walls-only reference (same camera, no things) then the scene; the HIRES build's changed pixels vs the model.
    # Every scene is rendered twice and the SECOND run is measured / compared: the first render at a new camera position
    # rebuilds the FTX/FTY tables (~14k T) and settles the render variables (thv, tdx, cos7 ... live in bank 0).
    scene(H, []); H.call("render"); H.call("render"); ref = H.buf(); zb = H.zbuf()
    scene(H, things); H.call("render"); b0 = H.bank(0); scr_hud = bytes(H.m.memory[0x4D00:0x5B00]); b3 = H.bank(3)
    tH = H.call("render"); got = H.buf(); vis = H.vis()
    scene(D, things); D.call("render"); tD = D.call("render"); gotD = D.buf()
    tcost[name] = (tH, tD)
    exp = ref
    n = len(vis) // 6
    for i in range(n):                        # vis is sorted far -> near: apply the model in that order
        e = vis[6 * i:6 * i + 6]; ptr = e[3] | (e[4] << 8)
        fr = sprt.index(ptr) - 4 if ptr in sprt[4:8] else None
        if fr is not None: exp = apply_model(exp, model(e, zb, fr))
    diff = [i for i in range(2304) if got[i] != exp[i]]
    cols_changed = sorted({i // 96 for i in range(2304) if got[i] != ref[i]})
    ok_depth = True
    if name == "zwall":
        # wall at x=7 (3.5 cells ahead) hides a zombie at 5.0 cells: nothing may change
        ok_depth = got == ref
    check(not diff and ok_depth, "%-8s HIRES BUF == model (%d mismatching bytes), vis entries %d, byte columns changed %s; T render HIRES %d / default %d" % (
        name, len(diff), n, (cols_changed[:1] + ["..", cols_changed[-1]]) if len(cols_changed) > 2 else cols_changed, tH, tD))
    check(H.bank(0) == b0 and bytes(H.m.memory[0x4D00:0x5B00]) == scr_hud and H.bank(3)[:0x500] == b3[:0x500] and H.cur == 0 and (H.m.memory[BANKM] & 7) == 0,
          "%-8s bank 0 / HUD rows / bank-3 code untouched, bank 0 paged after the pass (BANKM %02Xh)" % (name, H.m.memory[BANKM]))
    if name in ("z1.0", "z1.5", "z2.5"):
        # column coverage: 2-px columns changed in HIRES vs 3-px ray columns changed in the default build
        def cols2(a, b):
            s = set()
            for bc in range(24):
                for r in range(96):
                    d = a[bc * 96 + r] ^ b[bc * 96 + r]
                    for q in range(4):
                        if d & (0xC0 >> (2 * q)): s.add(4 * bc + q)
            return s
        scene(D, []); D.call("render"); refD = D.buf()
        say("     %-8s coverage: HIRES %d 2-px columns changed, default %d 2-px columns (old 3-px blitter), hv=%d" % (name, len(cols2(got, ref)), len(cols2(gotD, refD)), vis[0] if vis else 0))
        (ROOT / ("build/night/S_buf_%s_hires.bin" % name)).write_bytes(got); (ROOT / ("build/night/S_buf_%s_old.bin" % name)).write_bytes(gotD)
        (ROOT / ("build/night/S_buf_%s_walls.bin" % name)).write_bytes(ref)
say("T-states (render, pistol off, no copy phase): " + ", ".join("%s HIRES %d / old %d (+%d)" % (k, v[0], v[1], v[0] - v[1]) for k, v in tcost.items()))
# (e) interrupts during the pass: 30 frames of render with a zombie at 1.0 cell, one INT per 69,888 T, IM2 via the bank-3 mirror
S = H.S; m = H.m
m.set_memory_block(S["TABLE"], bytes([0xFD] * 257)); m.set_memory_block(S["ISRVEC"], bytes([0xC3, S["isr"] & 255, S["isr"] >> 8]))
H.call("fl_init")
scene(H, [(2, 4.5, 7.5)]); m.set_memory_block(S["ticks"], b"\x00\x00"); m.set_get_int_vector_callback(lambda: 0xFF)
m.set_memory_block(SCR, bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0xCD, S["render"] & 255, S["render"] >> 8, 0x18, 0xFB]))
m.pc = SCR; m.sp = S["FSTACK"]; accepted = 0; in3 = 0
for f in range(30):
    m.ticks_to_stop = 69888
    while m.ticks_to_stop > 0:
        m.run()
        if m.halted: break
    if H.cur == 3: in3 += 1
    if m.on_handle_active_int(): accepted += 1
m.ticks_to_stop = 8000; m.run()
ticks = struct.unpack_from("<H", bytes(m.memory[S["ticks"]:S["ticks"] + 2]))[0]
check(accepted == 30 and ticks == 30, "30 INTs @69,888 T through render with a hi-res zombie: accepted %d, ticks=%d, %d of them landed while bank 3 was paged" % (accepted, ticks, in3))
say("== %s (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILED", len(fails))); sys.exit(1 if fails else 0)
