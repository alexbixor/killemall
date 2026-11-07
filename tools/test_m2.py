#!/usr/bin/env python3
"""test_m2.py - lane M2 (7 Nov 2026) static-scene oracle for the DEFAULT 128K build with the bank-3 blitter drawing enemy types
3..6 (tools/build128.sh: build/kea128.tap + build/bank1.bin + build/bank3.bin, pasmo --equ BANK3=1). Python Z80 core + the
7FFDh paging model of tools/test_hires.py (its Mach class, copied here with two fixes: the bank-3 image is placed at bank3_org
from build/bank3.sym instead of a hard-coded F000h, and load_level 1 is run before the scenes because since lane K1 the low code
block (hr_pass) reaches LOWCODE 5BC0h only through load_level). The pre-M2 default build (build/night/pre_M2/build/kea128.tap +
bank1.bin, lane F2 state = killemall128_m2.tap b23dd27ba1f26169) renders the same scenes for the "old path" comparisons.
 A  for EACH type 3..6: scenes at 1.5 cells dead-centre for frames walk A (state 0), attack (state 2) and dead (state 3, ink A0h),
    one behind a wall (nothing drawn) and one at 2.5 cells: BUF == the Python model of the blitter with that type's frame (0
    mismatching bytes); ds_ink == HRINK[type] / A0h; a flash scene (hp |= 40h) -> ds_ink 20h and the hp byte decremented by 40h;
    bank 0, HUD rows, bank-3 code + tables untouched; bank 0 paged and BANKM bank bits 0 after the pass.
    A zombie scene takes the OLD path: BUF == the pre-M2 default build's BUF for the same scene. Items / imps: BUF unchanged vs
    pre-M2 too. HRINK (bank 3) == the ETAB ink column of the engine image (FF70h + 16*type + 9). 30 frames with INTs every
    69,888 T through render with a shotgunner at 1.5 cells: all accepted, ticks == 30.
 F  T-states per render (pistol off, no copy phase): no things / 1 zombie (old path) / 1 shotgunner at 1.5 cells, new vs pre-M2.
Also dumps the engine-exact BUFs of the 1.5-cell scenes to build/night/M2_buf_<type>_<frame>.bin for M2_types_sheet.png.
Output: build/night/M2_test_m2.out; exit 0 = all checks pass."""
import sys, re, struct, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import z80, tapdump
from gen_hires import model_type_frames
OUT = open(ROOT / "build/night/M2_test_m2.out", "w"); fails = []
def say(s): print(s); print(s, file=OUT, flush=True)
def check(ok, msg):
    say(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)
def syms(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / p).read_text(), re.M)}
def code_of(tap):
    bl = tapdump.blocks((ROOT / tap).read_bytes())
    return next((struct.unpack_from("<H", b, 14)[0], bytes(bl[i + 1][1:1 + struct.unpack_from("<H", b, 12)[0]])) for i, b in enumerate(bl) if b[0] == 0 and b[1] == 3)
BANKM = 23388; TRAP, SCR = 0x5B00, 0x5B10          # dead 128K editor page below BANKM (as tools/test_k1.py)
PXRAY = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 7, 7, 7]
NT = 36

class Mach:
    def __init__(self, tap, sym, bank1, bank3=None, bank3_sym=None):
        self.S = syms(sym); start, code = code_of(tap)
        self.m = m = z80.Z80Machine(); m.set_memory_block(start, code)
        b1 = (ROOT / bank1).read_bytes()
        self.banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1)), 7: bytes(16384)}
        self.S3 = syms(bank3_sym) if bank3_sym else {}
        if bank3 is not None:
            org = self.S3["bank3_org"] - 0xC000; b3 = (ROOT / bank3).read_bytes()
            self.banks[3] = bytes(org) + b3 + bytes(16384 - org - len(b3))
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
    def clear_things(self): self.m.set_memory_block(self.S["things"], bytes(NT * 8))
    def set_thing(self, i, typ, x, y, state=0, hp=30):
        self.m.set_memory_block(self.S["things"] + 8 * i, bytes([typ]) + struct.pack("<HH", int(x * 256), int(y * 256)) + bytes([state, hp, 0]))
    def thing(self, i): return bytes(self.m.memory[self.S["things"] + 8 * i:self.S["things"] + 8 * i + 8])
    def buf(self): return bytes(self.m.memory[self.S["BUF"]:self.S["BUF"] + 2304])
    def zbuf(self): return bytes(self.m.memory[self.S["zbuf"]:self.S["zbuf"] + 64])
    def vis(self): return bytes(self.m.memory[self.S["vis"]:self.S["vis"] + 6 * self.m.memory[self.S["nvis"]]])
    def ds_ink(self): return self.m.memory[self.S["ds_ink"]]

# ---------------- Python model of the bank-3 blitter (S_design.md 3..5; tools/test_hires.py model(), frame -> run lists parameter)
TF = model_type_frames()
def enemy_h(hv): c = hv >> 2; a = hv - c; c >>= 2; return (a + c) & 255
def model(vis_entry, zb, lists):
    hv, c0, nc = vis_entry[0], vis_entry[1] - 256 if vis_entry[1] > 127 else vis_entry[1], vis_entry[2]
    hd = enemy_h(hv) & 254
    vstep = round(hd * 256 / 48); top = ((48 + (hv >> 1)) << 8) - (hd << 8)
    rowtab = []; acc = top
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
            u = (uacc >> 8) & 31; v0 = 0; mask = (0xC0, 0x30, 0x0C, 0x03)[k & 3]
            for b in lists[u]:
                if b == 0: break
                code, vend = b & 3, b >> 2
                r0, r1 = rowtab[v0], rowtab[vend]; v0 = vend
                if code == 0 or r1 == r0: continue
                for r in range(r0, r1):
                    cur = out.get((k >> 2, r), (0xFF, 0))
                    out[(k >> 2, r)] = (cur[0] & ~mask & 0xFF if code == 1 else cur[0], (cur[1] | mask) if code == 3 else (cur[1] & ~mask))
        uacc += ustep
    return out
def apply_model(ref, pix):
    b = bytearray(ref)
    for (bc, r), (andm, orm) in pix.items():
        b[bc * 96 + r] = (b[bc * 96 + r] & andm) | orm
    return bytes(b)

N = Mach("build/kea128.tap", "build/kea128.sym", "build/bank1.bin", "build/bank3.bin", "build/bank3.sym")          # the M2 default build
O = Mach("build/night/pre_M2/build/kea128.tap", "build/night/pre_M2/build/kea128.sym", "build/night/pre_M2/build/bank1.bin")  # pre-M2 (F2 state)
for M in (N, O):
    M.call("bank_init"); M.call("load_level", a=1); M.call("init_game", limit=8_000_000)
    M.m.set_memory_block(M.S["draw_weapon"], b"\xc9")   # pistol off: sprite cost alone
    M.m.set_memory_block(M.S["fl_frame"], b"\xc9")      # no copy phase: BUF is the result
lowimg = (ROOT / "build/lowcode128.bin").read_bytes()
check("hr_pass" in N.S and "hr_pass" not in O.S and bytes(N.m.memory[N.S["LOWCODE"]:N.S["LOWCODE"] + len(lowimg)]) == lowimg and N.S["LOWCODE"] + len(lowimg) <= 0x5C43,
      "default build has hr_pass at %04Xh (low code block %d B at %04Xh..%04Xh == lowcode128.bin after load_level, <= 5C43h); pre-M2 build has not" % (
          N.S.get("hr_pass", 0), len(lowimg), N.S["LOWCODE"], N.S["LOWCODE"] + len(lowimg) - 1))
S3 = N.S3; b3 = N.bank(3)
check(b3[0x3DFD:0x3E00] == bytes([0xC3, N.S["isr"] & 255, N.S["isr"] >> 8]) and b3[0x3E00:0x3F01] == bytes([0xFD] * 257) and S3["hr_entry"] == 0xF000,
      "bank 3 carries the IM2 mirror (jp isr at FDFDh, 257 x FDh at FE00h); hr_entry at F000h")
check(S3["art2_end"] <= 0xF000 and S3["hr_code_end"] <= 0xF300 and S3["hires_end"] <= 0xFDFD and S3["bank3_org"] + len((ROOT / "build/bank3.bin").read_bytes()) <= 0x10000,
      "bank 3 layout: org %04Xh, art2_end %04Xh (<= F000h, %d B free), code end %04Xh (<= F300h), hires_end %04Xh (<= FDFDh, %d B free), image %d B" % (
          S3["bank3_org"], S3["art2_end"], 0xF000 - S3["art2_end"], S3["hr_code_end"], S3["hires_end"], 0xFDFD - S3["hires_end"], len((ROOT / "build/bank3.bin").read_bytes())))
# HRINK == ETAB ink column of the engine image
start, code = code_of("build/kea128.tap")
etab_ink = [code[N.S["ETAB"] - start + 16 * t + 9] for t in range(7)]
hrink = list(b3[S3["HRINK"] - 0xC000:S3["HRINK"] - 0xC000 + 7])
check(hrink == etab_ink and N.S["ETAB"] == 0xFF70, "HRINK (bank 3) %s == ETAB +9 ink column (engine image FF70h+16*type+9) %s" % (
    ["%02X" % v for v in hrink], ["%02X" % v for v in etab_ink]))
# HRFRM2 rows point at the frames gen_hires emitted (walk A, walk B, attack, dead per type 2..6)
hrfrm2 = [struct.unpack_from("<H", b3, S3["HRFRM2"] - 0xC000 + 2 * i)[0] for i in range(20)]
exp_ptr = [S3["hrf_%d" % f] for f in range(4)] + [S3["hrf_%d_%d" % (t, f)] for t in (3, 4, 5, 6) for f in range(4)]
check(hrfrm2 == exp_ptr and all(S3["bank3_org"] <= p < 0xF000 for p in hrfrm2[4:]), "HRFRM2 (20 words at %04Xh) == hrf_* frame labels of gen/hires_art2.asm; types 3..6 frames all below F000h" % S3["HRFRM2"])
# frame id in bank 3 = index of the vis entry's 16x24 pointer in spr_table[4..7]
sprt = [struct.unpack_from("<H", bytes(N.m.memory[N.S["spr_table"]:N.S["spr_table"] + 36]), 2 * i)[0] for i in range(18)]
def scene(M, things, px=3.5, py=7.5, ang=0):
    M.set_player(px, py, ang); M.clear_things()
    for i, th in enumerate(things): M.set_thing(i, *th)
NAMES = {2: "zombie", 3: "shotgunner", 4: "floater", 5: "brute", 6: "boss"}
tcost = {}
def b3_static(b):
    """bank 3 with its two RAM areas (hr_hv..hr_code_end variables, ROWTAB2 49 B) zeroed: everything else must never change."""
    a = bytearray(b); v0, v1 = S3["hr_hv"] - 0xC000, S3["hr_code_end"] - 0xC000; r0 = S3["ROWTAB2"] - 0xC000
    a[v0:v1] = bytes(v1 - v0); a[r0:r0 + 49] = bytes(49); return bytes(a)
def run_scene(name, things, expect_new, exp_ink=None, flash_idx=None, dump=None):
    """render the scene on both builds (walls-only reference first, then twice: the second run is measured / compared)."""
    scene(N, []); N.call("render"); N.call("render"); ref = N.buf(); zb = N.zbuf()
    scene(N, things); N.call("render"); b0 = N.bank(0); scr_hud = bytes(N.m.memory[0x4D00:0x5B00]); b3c = N.bank(3)
    hp_before = None
    if flash_idx is not None:
        hp_before = N.thing(flash_idx)[6]
    tN = N.call("render"); got = N.buf(); vis = N.vis(); ink = N.ds_ink()
    scene(O, things); O.call("render"); tO = O.call("render"); gotO = O.buf()
    tcost[name] = (tN, tO)
    n = len(vis) // 6
    frames_used = []
    if expect_new:
        exp = ref
        for i in range(n):                    # vis is sorted far -> near: apply the model in that order
            e = vis[6 * i:6 * i + 6]; ptr = e[3] | (e[4] << 8); idx = e[5]
            fr = sprt.index(ptr) - 4 if ptr in sprt[4:8] else None
            typ = N.thing(idx)[0] & 31
            if fr is not None and typ in (3, 4, 5, 6): exp = apply_model(exp, model(e, zb, TF[typ][fr])); frames_used.append(("walkA", "walkB", "attack", "dead")[fr])
        diff = [i for i in range(2304) if got[i] != exp[i]]
        cols = sorted({i // 96 for i in range(2304) if got[i] != ref[i]})
        drew = got != ref
        ok_vis = (not drew) if name.endswith("wall") else drew
        check(not diff and ok_vis, "%-18s BUF == bank-3 model (%d mismatching bytes), vis %d, frame %s, hv %d, byte columns changed %s, %s; T render new %d / pre-M2 %d" % (
            name, len(diff), n, "+".join(frames_used), vis[0] if vis else 0, (cols[:1] + ["..", cols[-1]]) if len(cols) > 2 else cols, "drawn" if drew else "nothing drawn (wall)", tN, tO))
        if exp_ink is not None:
            check(ink == exp_ink, "%-18s ds_ink after the pass %02Xh == expected %02Xh" % (name, ink, exp_ink))
        if flash_idx is not None:
            hp_after = N.thing(flash_idx)[6]
            check(ink == 0x20 and hp_after == hp_before - 0x40, "%-18s flash: ds_ink %02Xh (red), hp byte %02Xh -> %02Xh (one flash frame used per drawn frame)" % (name, ink, hp_before, hp_after))
        check(N.bank(0) == b0 and bytes(N.m.memory[0x4D00:0x5B00]) == scr_hud and b3_static(N.bank(3)) == b3_static(b3c) and N.cur == 0 and (N.m.memory[BANKM] & 7) == 0,
              "%-18s bank 0 / HUD rows / bank 3 (art, code, tables, IM2 mirror) untouched, bank 0 paged after (BANKM %02Xh)" % (name, N.m.memory[BANKM]))
    else:
        check(got == gotO, "%-18s OLD path: BUF == pre-M2 default build's BUF (%d mismatching bytes), vis %d, drawn %s; T render new %d / pre-M2 %d" % (
            name, sum(1 for i in range(2304) if got[i] != gotO[i]), n, got != ref, tN, tO))
        check(N.cur == 0 and (N.m.memory[BANKM] & 7) == 0 and b3_static(N.bank(3)) == b3_static(b3c), "%-18s bank 0 paged after (BANKM %02Xh), bank 3 untouched" % (name, N.m.memory[BANKM]))
    if dump:
        (ROOT / ("build/night/M2_buf_%s.bin" % dump)).write_bytes(got); (ROOT / "build/night/M2_buf_walls.bin").write_bytes(ref)
    return got, vis
# ---- A: types 3..6 (the camera at (3.5, 7.5) looking +x: 1.5 cells = x 5.0, 2.5 cells = x 6.0; wall at x = 7 hides x = 8.5)
for M in (N, O): M.m.set_memory_block(M.S["ticks"], b"\x10\x00")      # ticks bit 4 set: chasing enemies show walk B (sprites_d.asm va_walk)
run_scene("none", [], False)
for t in (3, 4, 5, 6):
    nm = NAMES[t]
    run_scene(nm + " walkA 1.5", [(t, 5.0, 7.5, 0)], True, exp_ink=etab_ink[t], dump="%d_walkA" % t)
    run_scene(nm + " attack 1.5", [(t, 5.0, 7.5, 2)], True, exp_ink=etab_ink[t], dump="%d_attack" % t)
    run_scene(nm + " dead 1.5", [(t, 5.0, 7.5, 3)], True, exp_ink=0xA0, dump="%d_dead" % t)
    run_scene(nm + " 2.5", [(t, 6.0, 7.5, 0)], True, exp_ink=etab_ink[t])
    run_scene(nm + " wall", [(t, 8.5, 7.5, 0)], True)
    run_scene(nm + " flash 1.5", [(t, 5.0, 7.5, 1, 30 | 0xC0)], True, flash_idx=0)   # 3 flash frames pending: warm-up render uses one, the measured one another
    run_scene(nm + " walkB 1.5", [(t, 5.0, 7.5, 1)], True, exp_ink=etab_ink[t], dump="%d_walkB" % t)    # chase + ticks bit 4 -> walk B
# ---- old path: zombie, imp, items (BUF identical to the pre-M2 build)
run_scene("zombie 1.5", [(2, 5.0, 7.5, 0)], False)
run_scene("zombie dead", [(2, 5.0, 7.5, 3)], False)
run_scene("imp 1.5", [(1, 5.0, 7.5, 0)], False)
run_scene("health 1.5", [(16, 5.0, 7.5, 0)], False)
run_scene("barrel 1.5", [(21, 5.0, 7.5, 0)], False)
# mixed vis list: a zombie at 2.5 cells (old path, drawn first = far) and a shotgunner at 1.5 cells (bank 3, drawn last = near):
# expected BUF = the pre-M2 build's BUF of the zombie alone + the shotgunner model on top
scene(O, [(2, 6.0, 7.5, 0)]); O.call("render"); O.call("render"); zonly = O.buf()
scene(N, []); N.call("render"); N.call("render"); zb = N.zbuf()
scene(N, [(2, 6.0, 7.5, 0), (3, 5.0, 7.5, 0)]); N.call("render"); tN = N.call("render"); got = N.buf(); vis = N.vis()
exp = zonly; order = []
for i in range(len(vis) // 6):
    e = vis[6 * i:6 * i + 6]; ptr = e[3] | (e[4] << 8); typ = N.thing(e[5])[0] & 31; order.append(typ)
    if typ == 3: exp = apply_model(exp, model(e, zb, TF[3][sprt.index(ptr) - 4]))
check(got == exp and order == [2, 3], "mixed vis list (zombie 2.5 old path, shotgunner 1.5 bank 3; order far->near %s): BUF == pre-M2 zombie-only BUF + shotgunner model (%d mismatching bytes), %d T" % (
    order, sum(1 for i in range(2304) if got[i] != exp[i]), tN))
tcost["mixed"] = (tN, 0)
# ---- F: T-states
say("T-states (render, pistol off, no copy phase): " + ", ".join("%s new %d / pre-M2 %d (%+d)" % (k, v[0], v[1], v[0] - v[1]) for k, v in tcost.items() if k in ("none", "zombie 1.5", "shotgunner walkA 1.5", "brute walkA 1.5", "boss walkA 1.5", "floater walkA 1.5", "mixed")))
# ---- (e) interrupts during the pass: 30 frames of render with a shotgunner at 1.5 cells, one INT per 69,888 T, IM2 via the bank-3 mirror
S = N.S; m = N.m
m.set_memory_block(S["TABLE"], bytes([0xFD] * 257)); m.set_memory_block(S["ISRVEC"], bytes([0xC3, S["isr"] & 255, S["isr"] >> 8]))
N.call("fl_init")
scene(N, [(3, 5.0, 7.5, 0)]); m.set_memory_block(S["ticks"], b"\x00\x00"); m.set_get_int_vector_callback(lambda: 0xFF)
m.set_memory_block(SCR, bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0xCD, S["render"] & 255, S["render"] >> 8, 0x18, 0xFB]))
m.pc = SCR; m.sp = S["FSTACK"]; accepted = 0; in3 = 0
for f in range(30):
    m.ticks_to_stop = 69888
    while m.ticks_to_stop > 0:
        m.run()
        if m.halted: break
    if N.cur == 3: in3 += 1
    for k in range(8):                      # the ULA holds INT for 32 T: re-offer within that window (tools/test_k1.py frames())
        if m.on_handle_active_int(): accepted += 1; break
        m.ticks_to_stop = 4; m.run()
m.ticks_to_stop = 8000; m.run()
ticks = struct.unpack_from("<H", bytes(m.memory[S["ticks"]:S["ticks"] + 2]))[0]
check(accepted == 30 and ticks == 30, "30 INTs @69,888 T through render with a bank-3 shotgunner at 1.5 cells: accepted %d, ticks=%d, %d of them landed while bank 3 was paged" % (accepted, ticks, in3))
say("== %s (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILED", len(fails))); sys.exit(1 if fails else 0)
