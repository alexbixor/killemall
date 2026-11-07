#!/usr/bin/env python3
"""test_128.py - Kill'em all 128K lane tests (z80 1.2.0 core + static checks). Exit 0 = all pass. Output: build/test_128.out
 1 make128 diff == anchors only (removed lines are exactly the 5 anchored originals; added lines carry the anchor marker)
 2 bank-1 jump table bytes == pasmo .sym addresses (snd_isr/snd_fx/snd_music/lev0..7, count 8, LEV_STRIDE 1141, +32 jp b1_load)
   (lane K1, 6 Nov 2026: LEVELS8 - 8 level slots of 1141 B; the pre-K1 table had lev0..2 at +9 and LEV_STRIDE 1081 at +18)
 3 z80 core with simulated 7FFD banking: bank_init writes 10h; snd_music/snd_fx/snd_isr/load_level each write 11h then
   10h (bits 3..7 = 10h = ROM1/screen0 preserved, bank 0 restored), stack untouched across the switch, requests land in
   bank 1, AY register OUTs happen from snd_isr, load_level copies the exact 1141-byte image (+ the low code block to
   LOWCODE); T-states of snd_isr."""
import sys, re, struct, pathlib, difflib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import z80
OUT = open(ROOT / "build/test_128.out", "w"); fails = []
def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg, file=OUT, flush=True)
    if not ok: fails.append(msg)
def sym(path):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", path.read_text(), re.M)}
subprocess.run(["bash", str(ROOT / "tools/build128.sh")], check=True, capture_output=True)
# 1 anchors
src = (ROOT / "src/48k/kea48.asm").read_text().split("\n"); gen = (ROOT / "src/128k/kea128_gen.asm").read_text().split("\n")[1:]
removed, added = [], []
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, src, gen, autojunk=False).get_opcodes():
    if tag != "equal": removed += src[i1:i2]; added += gen[j1:j2]
exp = [r"^start:\s+di\b", r"^\s*xor a\s*$", r"^load_level:", r"^isr:\s+push hl\b", r'^\s*include "../common/beeper.asm"']
check(len(removed) == 5 and all(any(re.match(p, l) for p in exp) for l in removed), "make128: removed lines = 5 anchored originals %r" % removed)
check(all("T4 128K anchor" in l or l.strip() in ("di", "push hl") for l in added) and len(added) == 8, "make128: %d added lines all anchor-marked" % len(added))
# 2 table vs sym (LEVELS8 layout: +9 dw lev0..lev7, +25/+26 opt copies, +27 count, +28 dw LEV_STRIDE, +30 dw bank1_end, +32 jp b1_load)
b1 = (ROOT / "build/bank1.bin").read_bytes(); S1 = sym(ROOT / "build/bank1.sym"); S = sym(ROOT / "build/kea128.sym")
LEVEL_BLK = S["LEVEL_BLK"]; NLEV = 8
tbl = [struct.unpack_from("<H", b1, 1)[0], struct.unpack_from("<H", b1, 4)[0], struct.unpack_from("<H", b1, 7)[0]] + list(struct.unpack_from("<8H", b1, 9))
check(b1[0] == b1[3] == b1[6] == b1[32] == 0xC3 and tbl == [S1[k] for k in ("snd_isr", "snd_fx", "snd_music") + tuple("lev%d" % i for i in range(NLEV))]
      and struct.unpack_from("<H", b1, 33)[0] == S1["b1_load"], "bank1 table == .sym %s, +32 jp b1_load" % [hex(x) for x in tbl])
check(len(b1) <= 16384 and b1[27] == NLEV and struct.unpack_from("<H", b1, 28)[0] == LEVEL_BLK == 1141 and struct.unpack_from("<H", b1, 30)[0] == S1["bank1_end"],
      "bank1.bin %d B <= 16K, count %d, LEV_STRIDE %d, bank1_end %04Xh" % (len(b1), b1[27], struct.unpack_from("<H", b1, 28)[0], S1["bank1_end"]))
# 3 z80 core
import tapdump
bl = tapdump.blocks((ROOT / "build/kea128.tap").read_bytes())
start, code = next((struct.unpack_from("<H", b, 14)[0], bytes(bl[i + 1][1:1 + struct.unpack_from("<H", b, 12)[0]])) for i, b in enumerate(bl) if b[0] == 0 and b[1] == 3)
m = z80.Z80Machine(); m.set_memory_block(start, code)
banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1))}; cur = [0]; outs = []
def on_out(port, val):
    outs.append((port, val))
    if port == 0x7FFD and (val & 7) != cur[0]:
        banks[cur[0]] = bytes(m.memory[0xC000:0x10000]); m.set_memory_block(0xC000, banks[val & 7]); cur[0] = val & 7
m.set_output_callback(on_out); m.set_input_callback(lambda p: 0xFF)
TRAP, SCR = 0x5B00, 0x5B10          # lane K1: dead 128K editor page below BANKM (5EC0h.. is door_log/fe_tmpk now)
def call(label, a=None, limit=400000):
    stub = (bytes([0x3E, a]) if a is not None else b"") + bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8])
    m.set_memory_block(SCR, stub); m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8])); m.pc = SCR; m.sp = S.get("FSTACK", 65008)   # lane F: fixed-area stack under FLIP (rule F2)
    m.set_breakpoint(TRAP); used = 0
    while used < limit and m.pc != TRAP:            # run() may return early on events: loop until the trap
        m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
    m.clear_breakpoint(TRAP)
    assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc); return used
def b1mem(addr, n): return (banks[1] if cur[0] != 1 else bytes(m.memory[0xC000:0x10000]))[addr - 0xC000:addr - 0xC000 + n]
m.set_memory_block(23388, b"\x07"); del outs[:]; call("bank_init")
check(outs == [(0x7FFD, 0x10)] and m.memory[23388] == 0x10, "bank_init: OUT 7FFD 10h, BANKM 10h")
for lab, a in (("snd_music", 1), ("snd_fx", 3)):
    del outs[:]; t = call(lab, a); pg = [v for p, v in outs if p == 0x7FFD]
    check(pg == [0x11, 0x10] and cur[0] == 0 and m.memory[23388] == 0x10 and m.sp == S.get("FSTACK", 65008),
          "%s %d: 7FFD writes %s (bits 3..7 kept, bank 0 restored, BANKM 10h, SP balanced), %d T" % (lab, a, [hex(v) for v in pg], t))
check(b1mem(S1["mus_req"], 1) == b"\x81" and b1mem(S1["sfx_req"], 2) != b"\0\0", "requests landed in bank 1: mus_req 81h, sfx_req set")
check(b1mem(49152 + 25, 2) == bytes([m.memory[S["opt_music"]], m.memory[S["opt_sfx"]]]), "opt_music/opt_sfx copied into the bank-1 table (+25/+26)")
ts, ay = [], 0
for i in range(120):
    del outs[:]; ts.append(call("snd_isr")); ay += sum(1 for p, v in outs if p == 0xBFFD)
    pg = [v for p, v in outs if p == 0x7FFD]
    if pg != [0x11, 0x10]: check(False, "snd_isr frame %d paging %s" % (i, pg)); break
check(ay == 120 * 12 and max(ts) <= 4300, "snd_isr: 120 frames, %d AY data writes (12/frame), T max %d avg %d (player <= 4,000 + shim)" % (ay, max(ts), sum(ts) // len(ts)))
check(b1mem(S1["ay_regs"] + 8, 1) != b"\0", "AY volume A nonzero after 120 frames (music running)")
lowimg = (ROOT / "build/lowcode128.bin").read_bytes()
for lid in (2, 3, 8, 1):
    m.set_memory_block(S["LOWCODE"], bytes(len(lowimg)))
    del outs[:]; t = call("load_level", lid); img = (ROOT / ("build/lev128_%d.bin" % (lid - 1))).read_bytes()
    check([v for p, v in outs if p == 0x7FFD] == [0x11, 0x10] and bytes(m.memory[S["level_data"]:S["level_data"] + LEVEL_BLK]) == img and len(img) == LEVEL_BLK
          and bytes(m.memory[S["LOWCODE"]:S["LOWCODE"] + len(lowimg)]) == lowimg,
          "load_level %d: image copied (%d B) + low code block (%d B at %04Xh), bank 0 back, %d T" % (lid, LEVEL_BLK, len(lowimg), S["LOWCODE"], t))
del outs[:]; t = call("isr"); check([v for p, v in outs if p == 0x7FFD] == [0x11, 0x10] and m.memory[S["ticks"]] == 1, "engine isr: calls snd_isr, ticks++ (%d T)" % t)
print("== %s (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILED", len(fails)), file=OUT, flush=True)
print(open(ROOT / "build/test_128.out").read().splitlines()[-1]); sys.exit(1 if fails else 0)
