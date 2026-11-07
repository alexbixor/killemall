#!/usr/bin/env python3
"""test_k1.py - lane K1 (6 Nov 2026) oracle for the 128K LEVELS8 build: 8 levels, 36 things, real enemy rows (hp in units
of 10), the DRAM re-layout (vis 5B60h, low code block 5BC0h, things 5DA0h..5EBFh, door_log/fe_tmpk 5EC0h..5EFFh).
Python Z80 core (z80 1.2.0) + the 7FFDh paging model of tools/test_flip.py, on the REAL image (build/kea128.tap +
build/bank1.bin, built here by tools/build128.sh unless --nobuild). Exit 0 = all checks pass. Output: build/night/K1_test_k1.out.
 S  static: .sym layout (moved symbols, NTHINGS 36, NLEVELS 8, LEVEL_BLK 1141, low_end <= 8000h), bank-1 table (lev0..7 ==
    .sym, count 8, stride 1141, +32 = jp b1_load), the 8 images + low code block inside bank 1, ETAB rows, 48K identity sha.
 L  per level 1..8: load_level -> level_data == the bank-1 image (1141 B, id byte), 7FFD writes 11h/10h, low code block in
    place (== build/lowcode128.bin); init_game/things_init -> count == header n_things and every record's type/x/y/hp/state.
 R  per level: the start view through the real render with 30 INTs @ 69,888 T: all accepted, ticks == 30, PC never outside
    code; BUF of the view with things vs the same view with the things table cleared: differences = sprite columns only.
 V  level 8: densest pose found around the start / thing cluster: vis entries <= VISMAX, door_log/fe_tmpk untouched by renders.
 C  canary: 5B60h..5CFFh patterned (vis / low code restored), 300 frames of render+steps on level 8 (the main loop body),
    all INTs accepted; changed bytes = vis + low code variables + ONE contiguous stack range from 5D00h down; deepest
    stack write reported; SOLIDPG (5F00h..) still FFh; door_log/fe_tmpk only written by the game (door_n == 0 -> unchanged).
 H  hp: enemy_hit on a shotgunner/floater/brute/boss takes 1 unit per hit (3/6/12/40 hits to kill, kills + 1).
Harness stubs live in the dead 128K editor page 5B00h..5B5Bh (below BANKM 5B5Ch): nothing of the game touches it."""
import sys, re, struct, pathlib, subprocess, hashlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import z80, tapdump
OUT = open(ROOT / "build/night/K1_test_k1.out", "w"); fails = []
def say(s): print(s); print(s, file=OUT, flush=True)
def check(ok, msg):
    say(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)
def sym(path): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(path).read_text(), re.M)}
if "--nobuild" not in sys.argv:
    r = subprocess.run(["bash", str(ROOT / "tools/build128.sh")], capture_output=True, text=True)
    check(r.returncode == 0, "tools/build128.sh exit %d" % r.returncode)
    if r.returncode: say(r.stdout + r.stderr); sys.exit(1)
S = sym(ROOT / "build/kea128.sym"); S1 = sym(ROOT / "build/bank1.sym")
b1 = (ROOT / "build/bank1.bin").read_bytes(); lowimg = (ROOT / "build/lowcode128.bin").read_bytes()
# lane M2 (7 Nov 2026): the default build pages RAM bank 3 (hr_pass in the low code block) for every sprite of the vis list: the
# bank-3 image (build/bank3.bin at bank3_org from build/bank3.sym; blitter + types 3..6 art + IM2 mirror) is part of the machine model
S3 = sym(ROOT / "build/bank3.sym"); b3 = (ROOT / "build/bank3.bin").read_bytes(); b3org = S3["bank3_org"] - 0xC000
imgs = [(ROOT / ("build/lev128_%d.bin" % i)).read_bytes() for i in range(8)]
NT, VISMAX, BLK = S["NTHINGS"], S["VISMAX"], S["LEVEL_BLK"]
# ---- S static layout
check(NT == 36 and S["NLEVELS"] == 8 and BLK == 1141 and S["things"] == 0x5DA0 and S["vis"] == 0x5B60 and S["LOWCODE"] == 0x5BC0
      and S["door_log"] == 0x5EC0 and S["fe_tmpk"] == 0x5EF0 and S["DRAM_END"] == 0x5EC0 and S["FSTACK"] == 0x5D00,
      "S layout: NTHINGS %d NLEVELS %d LEVEL_BLK %d things %04X vis %04X LOWCODE %04X door_log %04X fe_tmpk %04X DRAM_END %04X FSTACK %04X" % (
          NT, S["NLEVELS"], BLK, S["things"], S["vis"], S["LOWCODE"], S["door_log"], S["fe_tmpk"], S["DRAM_END"], S["FSTACK"]))
check(S["things"] + NT * 8 == 0x5EC0 and S["vis"] + VISMAX * 6 == 0x5BC0 and S["low_end"] <= 0x8000 and S["level_data"] + BLK <= S["low_end"]
      and S["dc_white"] == 0x5BC0 and S["LOWCODE"] + len(lowimg) <= 0x5C43,
      "S fits: things end %04X, vis end %04X, level_data %04X + %d = %04X <= low_end %04X <= 8000h; low code %04X..%04X (%d B) below the stack's 5C43h" % (
          S["things"] + NT * 8, S["vis"] + VISMAX * 6, S["level_data"], BLK, S["level_data"] + BLK, S["low_end"], S["LOWCODE"], S["LOWCODE"] + len(lowimg) - 1, len(lowimg)))
tbl = list(struct.unpack_from("<8H", b1, 9))
check(b1[0] == b1[3] == b1[6] == b1[32] == 0xC3 and tbl == [S1["lev%d" % i] for i in range(8)] and b1[27] == 8 and struct.unpack_from("<H", b1, 28)[0] == BLK
      and struct.unpack_from("<H", b1, 33)[0] == S1["b1_load"] and struct.unpack_from("<H", b1, 30)[0] == S1["bank1_end"] and len(b1) <= 16384,
      "S bank-1 table: lev0..7 == .sym %s, count %d, stride %d, +32 jp b1_load %04X, bank1_end %04X, %d B <= 16K, levtab C009h..C018h in one page" % (
          [hex(x) for x in tbl], b1[27], struct.unpack_from("<H", b1, 28)[0], S1["b1_load"], S1["bank1_end"], len(b1)))
check(all(len(i) == BLK and i[0] == n + 1 and i[1] == 75 for n, i in enumerate(imgs)) and all(b1[S1["lev%d" % i] - 0xC000:S1["lev%d" % i] - 0xC000 + BLK] == imgs[i] for i in range(8))
      and b1[S1["lowcode_img"] - 0xC000:S1["lowcode_img"] - 0xC000 + len(lowimg)] == lowimg,
      "S bank 1 holds the 8 images (ids 1..8, %d B each, n_things %s) + the low code block (%d B)" % (BLK, [i[8] for i in imgs], len(lowimg)))
bl = tapdump.blocks((ROOT / "build/kea128.tap").read_bytes())
start, code = next((struct.unpack_from("<H", b, 14)[0], bytes(bl[i + 1][1:1 + struct.unpack_from("<H", b, 12)[0]])) for i, b in enumerate(bl) if b[0] == 0 and b[1] == 3)
etab = code[S["ETAB"] - start:S["ETAB"] - start + 7 * 16]
rows = {t: etab[t * 16:t * 16 + 16] for t in range(7)}
exp_rows = {1: (3, 15, 10, 0, 0, 25, 10, 4, 0, 0x30), 2: (3, 15, 15, 0, 0, 25, 10, 4, 4, 0x40), 3: (3, 13, 0, 20, 6, 20, 10, 2, 4, 0x30),
            4: (6, 10, 0, 15, 8, 30, 10, 3, 4, 0x60), 5: (12, 18, 25, 0, 0, 20, 10, 4, 4, 0x50), 6: (40, 13, 35, 20, 8, 15, 10, 0x0E, 4, 0x10)}
check(all(tuple(rows[t][:10]) == exp_rows[t] for t in exp_rows) and all(rows[t][8] <= 14 for t in range(1, 7)),
      "S ETAB rows 1..6 (hp units of 10) = %s; every sprite column <= 14 (spr_table has 18 entries)" % {t: list(rows[t][:10]) for t in range(1, 7)})
sha48 = hashlib.sha256((ROOT / "build/kea48.tap").read_bytes()).hexdigest()[:16]
check(sha48 == "efc8dd21c080fb55", "S 48K identity: build/kea48.tap sha256 %s (expected efc8dd21c080fb55, unchanged)" % sha48)
# ---- machine
m = z80.Z80Machine(); m.set_memory_block(start, code)
BANKM = 23388
banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1)), 3: bytes(b3org) + b3 + bytes(16384 - b3org - len(b3)), 7: bytes(16384)}
cur = [0]; outs = []
def on_out(port, val):
    outs.append((port, val))
    if port == 0x7FFD and (val & 7) != cur[0]:
        banks[cur[0]] = bytes(m.memory[0xC000:0x10000]); b = val & 7
        if b not in banks: banks[b] = bytes(16384)
        m.set_memory_block(0xC000, banks[b]); cur[0] = b
m.set_output_callback(on_out); m.set_input_callback(lambda p: 0xFF)
TRAP, SCR = 0x5B00, 0x5B10                   # dead 128K editor page below BANKM (5B5Ch): no game code touches 5B00h..5B5Bh
def call(label, a=None, limit=2_000_000, pre=b""):
    stub = pre + (bytes([0x3E, a]) if a is not None else b"") + bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8])
    m.set_memory_block(SCR, stub); m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8])); m.pc = SCR; m.sp = S["FSTACK"]
    m.set_breakpoint(TRAP); used = 0
    while used < limit and m.pc != TRAP:
        m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
    m.clear_breakpoint(TRAP); assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc); return used
def pg(): return [v for p, v in outs if p == 0x7FFD]
def rd(a, n): return bytes(m.memory[a:a + n])
def in_code(pc): return 0x6C00 <= pc < 0x10000 or S["LOWCODE"] <= pc < S["LOWCODE"] + len(lowimg) or TRAP <= pc < SCR + 16   # C000h..: bank 0 / 1 / 3 code alike
def frames(n, stub):
    """run `stub` (a loop, placed at SCR) for n frames of 69,888 T with one INT per frame. A refused INT (the stop fell on a
    prefix / EI instruction, where the core refuses) is re-offered within the 32 T the ULA holds the line. Returns
    (accepted, pc-outside-code count). The last ISR gets 8,000 T to finish (ticks must then equal n)."""
    m.set_memory_block(SCR, stub); m.pc = SCR; m.sp = S["FSTACK"]; acc = 0; outside = 0
    m.set_memory_block(S["ticks"], b"\x00\x00"); m.set_memory_block(S["step_t"], b"\x00"); m.set_get_int_vector_callback(lambda: 0xFF)
    for f in range(n):
        m.ticks_to_stop = 69888
        while m.ticks_to_stop > 0:
            m.run()
            if not in_code(m.pc): outside += 1
            if m.halted: break
        for k in range(8):
            if m.on_handle_active_int(): acc += 1; break
            m.ticks_to_stop = 4; m.run()
    m.ticks_to_stop = 8000; m.run()
    # lane M2: the last frame may stop inside a paged phase (bank 3 in hr_pass, bank 7 in fl_frame): let it end (bank 0 back,
    # BANKM bank bits 0) before the caller judges the paging state or re-enters code at C000h.. (tools/test_flip.py does the same)
    for k in range(40):
        if cur[0] == 0 and (m.memory[BANKM] & 7) == 0: break
        m.ticks_to_stop = 5000; m.run()
    return acc, outside
RENDER_LOOP = bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0xCD, S["render"] & 255, S["render"] >> 8, 0x18, 0xFB])                # im 2 / ei / loop: call render / jr loop
MAIN_LOOP = bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0xCD, S["render"] & 255, S["render"] >> 8, 0xCD, S["steps"] & 255, S["steps"] >> 8, 0x18, 0xF8])   # + call steps
m.set_memory_block(BANKM, b"\x07"); call("bank_init")
m.set_memory_block(S["TABLE"], bytes([0xFD] * 257)); m.set_memory_block(S["ISRVEC"], bytes([0xC3, S["isr"] & 255, S["isr"] >> 8])); call("fl_init")
check(pg()[-1] == 0x10 and m.memory[BANKM] == 0x10, "bank_init + fl_init: bank 0 paged, BANKM 10h, IM2 table mirrored")
def level_things(img):
    n = img[8]; return [tuple(img[1033 + 3 * i:1036 + 3 * i]) for i in range(n)]
# ---- L + R per level
for lid in range(1, 9):
    img = imgs[lid - 1]
    m.set_memory_block(S["LOWCODE"], bytes(len(lowimg))); m.set_memory_block(BANKM, b"\x10"); del outs[:]
    t = call("load_level", lid)
    ok_img = rd(S["level_data"], BLK) == img and rd(S["LOWCODE"], len(lowimg)) == lowimg
    check(ok_img and pg() == [0x11, 0x10] and m.memory[BANKM] == 0x10 and m.sp == S["FSTACK"],
          "L%d load_level: level_data == bank-1 image (id %d, %d B) %s, low code block at %04X == lowcode128.bin, 7FFD %s, %d T" % (lid, img[0], BLK, ok_img, S["LOWCODE"], [hex(v) for v in pg()], t))
    call("init_game", limit=5_000_000)        # win_tint + CHJ + SOLIDPG + header -> posx/posy/angle/mapptr, then things_init
    th = level_things(img); n = len(th)
    got = [tuple(rd(S["things"] + 8 * i, 8)) for i in range(NT)]
    exp = [(ty, 128, x, 128, y, 0, 3 if ty >= 16 else rows[ty][0], 0) for (ty, x, y) in th] + [(0,) * 8] * (NT - n)
    bad = [(i, got[i], exp[i]) for i in range(NT) if got[i] != exp[i]]
    check(not bad and n == img[8], "L%d things_init: %d things (header %d), type/x/y/hp(units)/state/timer all as mapc + ETAB say%s" % (lid, n, img[8], "" if not bad else "; first bad %s" % bad[:2]))
    acc, outside = frames(30, RENDER_LOOP)
    ticks = struct.unpack_from("<H", rd(S["ticks"], 2))[0]
    check(acc == 30 and ticks == 30 and outside == 0 and (m.memory[BANKM] & 7) == 0,
          "R%d 30 INTs @69,888 T through render (start view): accepted %d, ticks %d, PC outside code %d, bank %d paged after" % (lid, acc, ticks, outside, m.memory[BANKM] & 7))
    save = rd(S["fl_frame"], 1); m.set_memory_block(S["fl_frame"], b"\xc9")      # render without the copy phase (BUF stays pristine)
    m.set_memory_block(S["fl_req"], b"\x00")   # lane M2: drop a flip left pending by the frames above - call() injects no interrupts and hr_pass's fl_wait would spin on it
    call("render", limit=6_000_000); call("render", limit=6_000_000); buf_t = rd(S["BUF"], 2304); nvis_t = m.memory[S["nvis"]]
    things_save = rd(S["things"], NT * 8); m.set_memory_block(S["things"], bytes(NT * 8))
    call("render", limit=6_000_000); buf_e = rd(S["BUF"], 2304); nvis_e = m.memory[S["nvis"]]
    m.set_memory_block(S["things"], things_save); m.set_memory_block(S["fl_frame"], save)
    diff_cols = sorted({i // 96 for i in range(2304) if buf_t[i] != buf_e[i]})
    check(nvis_e == 0 and nvis_t <= VISMAX and (not diff_cols or nvis_t > 0),
          "R%d start view: %d vis entries with the things, %d with the table cleared; BUF differs in byte columns %s (sprite pixels only%s)" % (
              lid, nvis_t, nvis_e, diff_cols, "" if diff_cols or not nvis_t else "; all occluded by walls"))
    say("     L%d: start (%d,%d) angle %d, n_things %d (enemies %s), %d wall cells" % (lid, img[5], img[6], img[7], img[8], sorted({ty for ty, _, _ in th if ty < 16}), sum(1 for c in img[9:1033] if 1 <= c <= 7)))
# ---- V level 8: vis cap at the densest pose around the start and the thing cluster
img = imgs[7]; th8 = level_things(img); best = (0, None)
cx = sorted(th8, key=lambda t: t[1])[len(th8) // 2][1]; cy = sorted(th8, key=lambda t: t[2])[len(th8) // 2][2]
cands = [(img[5], img[6], a) for a in range(0, 256, 32)] + [(cx, cy, a) for a in range(0, 256, 32)]
save = rd(S["fl_frame"], 1); m.set_memory_block(S["fl_frame"], b"\xc9")
for (x, y, a) in cands:
    if 1 <= img[9 + y * 32 + x] <= 12: continue
    call("init_game", limit=5_000_000)
    m.set_memory_block(S["posx"], struct.pack("<HH", (x << 8) | 128, (y << 8) | 128)); m.set_memory_block(S["angle"], bytes([a]))
    dl = rd(0x5EC0, 64)
    call("render", limit=6_000_000); call("render", limit=6_000_000)
    nv = m.memory[S["nvis"]]
    if nv > best[0]: best = (nv, (x, y, a, rd(0x5EC0, 64) == dl))
m.set_memory_block(S["fl_frame"], save)
check(best[1] is not None and best[0] <= VISMAX and best[1][3], "V level 8: densest of %d poses %s sees %d vis entries (<= VISMAX %d); 5EC0h..5EFFh (door_log/fe_tmpk) untouched: %s" % (
    len(cands), best[1][:3] if best[1] else None, best[0], VISMAX, best[1][3] if best[1] else None))
# ---- C canary: 300 frames of the main loop body (render + steps) on level 8 from its start pose
call("load_level", 8); call("init_game", limit=5_000_000)
REG0, REG1 = 0x5B60, 0x5D00
PAT = bytes((((i * 37 + 11) & 255) or 1) for i in range(REG1 - REG0))
m.set_memory_block(REG0, PAT); m.set_memory_block(S["vis"], bytes(VISMAX * 6)); m.set_memory_block(S["LOWCODE"], lowimg)
things_before = rd(S["things"], NT * 8); dl_before = rd(0x5EC0, 64)
acc, outside = frames(300, MAIN_LOOP)
ticks = struct.unpack_from("<H", rd(S["ticks"], 2))[0]
after = rd(REG0, REG1 - REG0)
changed = [REG0 + i for i in range(len(after)) if after[i] != PAT[i]]
vis_rng = range(S["vis"], S["vis"] + VISMAX * 6); low_rng = range(S["LOWCODE"], S["LOWCODE"] + len(lowimg))
stack_ch = [a for a in changed if a >= S["LOWCODE"] + len(lowimg)]
deepest = min(stack_ch) if stack_ch else 0x5D00
unexplained = [a for a in changed if a not in vis_rng and a not in low_rng and not (deepest <= a < 0x5D00)]
check(acc == 300 and ticks == 300 and outside == 0, "C 300 INTs @69,888 T through render+steps on level 8 (frames %d): accepted %d, ticks %d, PC outside code %d" % (
    struct.unpack_from("<H", rd(S["frames"], 2))[0], acc, ticks, outside))
check(not unexplained and deepest >= 0x5C43 + 64, "C canary 5B60h..5CFFh after 300 frames: deepest stack write %04Xh (%d B of the 189 B 5C43h..5CFFh used, %d B margin to the low code block), %d bytes changed = vis %d + low code vars %d + stack %d; unexplained %d %s" % (
    deepest, 0x5D00 - deepest, deepest - (S["LOWCODE"] + len(lowimg)), len(changed), sum(1 for a in changed if a in vis_rng), sum(1 for a in changed if a in low_rng), len(stack_ch), len(unexplained), [hex(a) for a in unexplained[:8]]))
check(rd(0x5F00, 256) == b"\xff" * 256 and rd(0x5EC0, 64) == dl_before and m.memory[S["door_n"]] == 0,
      "C SOLIDPG 5F00h..5FFFh still 256 x FFh; door_log/fe_tmpk 5EC0h..5EFFh unchanged (door_n %d: no door opened by the standing player)" % m.memory[S["door_n"]])
live = sum(1 for i in range(NT) if m.memory[S["things"] + 8 * i]); moved = sum(1 for i in range(NT) if rd(S["things"] + 8 * i + 1, 4) != things_before[8 * i + 1:8 * i + 5])
awake = sum(1 for i in range(NT) if m.memory[S["things"] + 8 * i] and m.memory[S["things"] + 8 * i] < 16 and m.memory[S["things"] + 8 * i + 5] in (1, 2))
say("     C things after 300 frames (%d steps): %d live, %d moved, %d enemies awake (chase/attack); health %d" % (ticks // 5, live, moved, awake, m.memory[S["health"]]))
# ---- H hp units
m.set_memory_block(BANKM, b"\x10"); call("bank_init")
for ty, hits in ((3, 3), (4, 6), (5, 12), (6, 40)):
    m.set_memory_block(S["things"], bytes([ty, 128, 5, 128, 5, 0, rows[ty][0], 0]) + bytes(NT * 8 - 8)); m.set_memory_block(S["kills"], b"\x00")
    n = 0
    while n < 100 and m.memory[S["things"] + 5] != 3:
        call("enemy_hit", pre=bytes([0xDD, 0x21, S["things"] & 255, S["things"] >> 8])); n += 1      # ld ix,things / call enemy_hit
    check(n == hits and m.memory[S["kills"]] == 1 and m.memory[S["things"] + 6] == 0xC0, "H type %d (%s): dead after %d pistol hits (ETAB hp %d units = %d hp), kills %d, hp byte C0h (0 + flash)" % (
        ty, {3: "shotgunner", 4: "floater", 5: "brute", 6: "boss"}[ty], n, rows[ty][0], rows[ty][0] * 10, m.memory[S["kills"]]))
say("== %s (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILED", len(fails))); sys.exit(1 if fails else 0)
