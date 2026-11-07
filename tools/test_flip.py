#!/usr/bin/env python3
"""test_flip.py - lane F (5 Nov 2026) oracle B for the 128K shadow-screen flip FOUNDATION (pasmo --equ FLIP=1 build).
Python Z80 core + a 7FFDh paging model with bank 7 (the shadow screen) and a "displayed screen" flag. Proves, with the
real 128K image (build/kea128.tap + build/bank1.bin):
 1 PAGEN keeps the display latch (bit 3) from BANKM: with BANKM = 18h (bank 7 shown) snd_music/snd_fx/load_level/snd_isr
   write 19h then 18h - the picture is never flipped back to screen 0 by a sound call or a tick (rule F1).
 2 snd_isr restores the bank it interrupted: with bank 7 paged (BANKM 1Fh) it writes 11h then 1Fh, so an interrupt in the
   middle of a bank-7 copy phase returns to bank 7 (rule F2) - the old build forced bank 0 (would have overwritten bank-0 code).
 3 a pending fl_req (18h) is applied by snd_isr at the next interrupt (BANKM + port) and cleared; a 0 request does nothing (F3).
 4 COPYBUF honours cb_hi: with cb_hi = C0h and bank 7 paged the 2304 window bytes land in bank 7 exactly where they would
   in screen 0 (+8000h), zero writes reach screen 0 (4000h-5AFFh), bank 0 is untouched, SP is restored; with cb_hi = 40h
   it is the pre-F behaviour (all 2304 bytes to screen 0) (rule F4). The window bytes are compared with BUF byte for byte.
 5 the 50 Hz tick is not lost across the copy: 60 interrupts injected every 69,888 T while the engine runs render+steps
   with the shadow destination -> ticks advances by exactly 60 (IM2 vector mirrored in bank 7 as the design requires).
What this does NOT prove (not built tonight): the main-loop alternation and the tear-freedom of a running game -
see build/night/F_result.out.  Exit 0 = all checks pass; output also to build/night/F_test_flip.out."""
import sys, re, struct, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import z80, tapdump
OUT = open(ROOT / "build/night/F_test_flip.out", "w"); fails = []
def say(s): print(s); print(s, file=OUT, flush=True)
def check(ok, msg):
    say(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea128.sym").read_text(), re.M)}
check("cb_hi" in S and "fl_req" in S and "fl_frame" in S and "hud_dirty" in S, "FLIP build: cb_hi/fl_req/fl_frame/hud_dirty symbols present (pasmo --equ FLIP=1)")
bl = tapdump.blocks((ROOT / "build/kea128.tap").read_bytes())
start, code = next((struct.unpack_from("<H", b, 14)[0], bytes(bl[i + 1][1:1 + struct.unpack_from("<H", b, 12)[0]])) for i, b in enumerate(bl) if b[0] == 0 and b[1] == 3)
b1 = (ROOT / "build/bank1.bin").read_bytes()
# lane M2 (7 Nov 2026): the default build pages RAM bank 3 (hr_pass in the low code block, 131 B) for every sprite of the vis list:
# the bank-3 image (build/bank3.bin at bank3_org from build/bank3.sym: blitter + types 3..6 art + IM2 mirror) is part of the machine model
S3 = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/bank3.sym").read_text(), re.M)}
b3 = (ROOT / "build/bank3.bin").read_bytes(); b3org = S3["bank3_org"] - 0xC000
m = z80.Z80Machine(); m.set_memory_block(start, code)
BANKM = 23388
banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1)), 3: bytes(b3org) + b3 + bytes(16384 - b3org - len(b3)), 7: bytes(16384)}
cur = [0]; shown = [0]; outs = []
def on_out(port, val):
    outs.append((port, val))
    if port == 0x7FFD:
        shown[0] = (val >> 3) & 1
        if (val & 7) != cur[0]:
            banks[cur[0]] = bytes(m.memory[0xC000:0x10000]); b = val & 7
            if b not in banks: banks[b] = bytes(16384)
            m.set_memory_block(0xC000, banks[b]); cur[0] = b
m.set_output_callback(on_out); m.set_input_callback(lambda p: 0xFF)
def bank(n): return bytes(m.memory[0xC000:0x10000]) if cur[0] == n else banks[n]
TRAP, SCR = 0x5B00, 0x5B10   # lane K1 (6 Nov 2026): was 5EC0h/5ED0h = door_log/fe_tmpk under LEVELS8 -> dead editor page below BANKM (5B5Ch)
def call(label, a=None, limit=2_000_000):
    stub = (bytes([0x3E, a]) if a is not None else b"") + bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8])
    m.set_memory_block(SCR, stub); m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8])); m.pc = SCR; m.sp = S["FSTACK"]
    m.set_breakpoint(TRAP); used = 0
    while used < limit and m.pc != TRAP:
        m.ticks_to_stop = 20000; m.run(); used += 20000 - m.ticks_to_stop
    m.clear_breakpoint(TRAP); assert m.pc == TRAP, "%s did not return (pc=%04x)" % (label, m.pc); return used
def pg(): return [v for p, v in outs if p == 0x7FFD]
def set_bankm(v):
    m.set_memory_block(BANKM, bytes([v]))
    if (v & 7) != cur[0]: on_out(0x7FFD, v)
    shown[0] = (v >> 3) & 1
# ---- 1 rule F1: display latch kept by every paging wrapper
call("bank_init"); del outs[:]
set_bankm(0x18)                                   # bank 0 paged, bank 7 SHOWN
for lab, a in (("snd_music", 2), ("snd_fx", 3)):
    del outs[:]; call(lab, a)
    check(pg() == [0x19, 0x18] and m.memory[BANKM] == 0x18 and cur[0] == 0, "F1 %s with screen 1 shown: 7FFD writes %s (bit 3 kept, bank 0 back)" % (lab, [hex(v) for v in pg()]))
del outs[:]; call("load_level", 2)
check(pg() == [0x19, 0x18] and m.memory[BANKM] == 0x18, "F1 load_level with screen 1 shown: 7FFD writes %s" % [hex(v) for v in pg()])
del outs[:]; call("isr")
check(pg() == [0x19, 0x18] and m.memory[BANKM] == 0x18, "F1 isr (snd_isr) with screen 1 shown and no request: 7FFD writes %s" % [hex(v) for v in pg()])
# ---- 2 rule F2: snd_isr returns to the interrupted bank
set_bankm(0x1F); del outs[:]; call("isr")
check(pg() == [0x19, 0x1F] and cur[0] == 7 and m.memory[BANKM] == 0x1F, "F2 isr while bank 7 paged + shown: 7FFD writes %s, bank 7 paged again" % [hex(v) for v in pg()])
set_bankm(0x10)
# ---- 3 rule F3: fl_req applied in the ISR, then cleared
m.set_memory_block(S["fl_req"], b"\x18"); del outs[:]; call("isr")
check(pg() == [0x19, 0x18] and m.memory[S["fl_req"]] == 0 and m.memory[BANKM] == 0x18 and shown[0] == 1,
      "F3 fl_req 18h: isr writes %s (the switch rides on the bank-1 page-in, i.e. the first port write of the ISR), fl_req cleared, screen 1 shown" % [hex(v) for v in pg()])
m.set_memory_block(S["fl_req"], b"\x10"); del outs[:]; call("isr")
check(pg() == [0x11, 0x10] and shown[0] == 0 and m.memory[S["fl_req"]] == 0, "F3 fl_req 10h: isr writes %s, screen 0 shown again" % [hex(v) for v in pg()])
del outs[:]; call("isr"); check(pg() == [0x11, 0x10], "F3 fl_req 0: plain tick %s (no switch)" % [hex(v) for v in pg()])
# ---- 4 rule F4: COPYBUF destination by cb_hi (window bytes vs BUF, screen 0 untouched when bank 7 is the target)
call("init_game", limit=5_000_000)
m.set_memory_block(S["posx"], struct.pack("<HH", 0x0380, 0x0780)); m.set_memory_block(S["angle"], b"\x00")
copy0 = bytes(m.memory[S["COPYBUF"]]) if False else None
save = bytes(m.memory[S["fl_frame"]:S["fl_frame"] + 1]); m.set_memory_block(S["fl_frame"], b"\xc9")   # render without the copy phase
call("render", limit=5_000_000); m.set_memory_block(S["fl_frame"], save)
buf = bytes(m.memory[S["BUF"]:S["BUF"] + 2304])
def window(base):
    mem = m.memory if base == 0x4000 else None
    out = bytearray()
    for c in range(24):
        for r in range(96):
            y = 8 + r; addr = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (4 + c)
            out.append(m.memory[base + addr] if base == 0x4000 else bank(7)[addr])
    return bytes(out)
writes = {"scr0": 0, "b7": 0, "other": 0}
def hook(addr, value):
    if 0x4000 <= addr < 0x5B00: writes["scr0"] += 1
    elif 0xC000 <= addr < 0xDB00 and cur[0] == 7: writes["b7"] += 1
    elif addr >= 0xC000: writes["other"] += 1
# NOTE: the z80 core's marked-write hook REPORTS the write but the written value does not land (measured: 1637 mismatches
# with the hook on, 0 without) -> every copy is run twice: pass 1 counts writes (hook on), pass 2 compares bytes (hook off).
def copy_twice(tag):
    for k in writes: writes[k] = 0
    m.set_write_callback(hook); m.mark_addrs(0x4000, 0x1B00, m.WRITE_MARK); m.mark_addrs(0xC000, 0x1B00, m.WRITE_MARK)
    call("COPYBUF", limit=5_000_000)
    m.set_write_callback(lambda a, v: None); m.unmark_addrs(0x4000, 0x1B00, m.WRITE_MARK); m.unmark_addrs(0xC000, 0x1B00, m.WRITE_MARK)
    return call("COPYBUF", limit=5_000_000)
b0_before = bank(0)
m.set_memory_block(S["cb_hi"], b"\xc0"); set_bankm(0x17)      # bank 7 paged, screen 0 shown (the hidden-screen copy)
scr0_before = bytes(m.memory[0x4000:0x5B00])
t7 = copy_twice("b7")
w7 = window(0xC000)
check(w7 == buf and writes["b7"] == 2304 and writes["scr0"] == 0 and writes["other"] == 0 and m.sp == S["FSTACK"] and bytes(m.memory[0x4000:0x5B00]) == scr0_before,
      "F4 COPYBUF cb_hi=C0h, bank 7 paged: 2304 B into bank 7 == BUF (%s), screen-0 writes %d (screen 0 bytes unchanged %s), other writes %d, %d T, SP ok" % (w7 == buf, writes["scr0"], bytes(m.memory[0x4000:0x5B00]) == scr0_before, writes["other"], t7))
set_bankm(0x10); check(bank(0) == b0_before, "F4 bank 0 untouched by the bank-7 copy")
m.set_memory_block(S["cb_hi"], b"\x40"); m.set_memory_block(0x4000, bytes(6144))
t0 = copy_twice("scr0")
check(window(0x4000) == buf and writes["scr0"] == 2304 and writes["b7"] == 0, "F4 COPYBUF cb_hi=40h: 2304 B into screen 0 == BUF (%s), %d T (pre-F behaviour)" % (window(0x4000) == buf, t0))
# ---- 5 rule F2 + oracle B part 2: 60 real frames. Stub = main's loop body without `steps`: im 2 / ei / loop: call render.
#      render ends in fl_frame (bank 7 paged during COPYBUF + the attribute copy, interrupts ON), which requests the flip;
#      the ISR (IM2 via the bank-7 mirror written by fl_init) applies it. Per frame we check: (a) the hidden screen holds
#      exactly the rendered window (BUF) + the 288 staged attribute cells, (b) the displayed screen received no write while
#      displayed (tear-free by construction), (c) the switch byte was written only inside isr, (d) ticks were not lost.
m.set_memory_block(S["TABLE"], bytes([0xFD] * 257)); m.set_memory_block(S["ISRVEC"], bytes([0xC3, S["isr"] & 255, S["isr"] >> 8]))  # as start does
set_bankm(0x10); call("bank_init"); call("fl_init")                 # real mirror: ISRVEC + TABLE into bank 7
mir_ok = bank(7)[0xFDFD - 0xC000:0xFF01 - 0xC000] == bytes(m.memory[0xFDFD:0xFF01])
check(mir_ok and cur[0] == 0 and m.memory[BANKM] == 0x10, "F2 fl_init: 260 B IM2 table + ISRVEC mirrored into bank 7 (%s), bank 0 back, BANKM 10h" % mir_ok)
m.set_memory_block(S["hud_dirty"], b"\x01")
m.set_memory_block(S["ticks"], b"\x00\x00"); m.set_memory_block(S["step_t"], b"\x00"); m.set_get_int_vector_callback(lambda: 0xFF)
# lane F2 (7 Nov 2026, rule F6): screen 0 starts as a non-zero pattern = "what the HUD code drew" (frame, rail, labels, bars live
# there); bank 7 starts zeroed. After the frames, bank 7 must equal screen 0 everywhere OUTSIDE the 24 x 12 window (pixels +
# attributes), i.e. fl_hud mirrored the whole screen - lane F copied 4D00h..57FFh + attribute rows 13..23 only (the red window
# frame and the top lines of rows 13..15 never reached bank 7 and flashed at the flip rate on the Deck).
PAT0 = bytes((((i * 29 + 7) & 255) or 1) for i in range(0x1B00))
m.set_memory_block(0x4000, PAT0); set_bankm(0x17); m.set_memory_block(0xC000, bytes(0x1B00)); set_bankm(0x10)
m.set_memory_block(SCR, bytes([0x3E, 0xFE, 0xED, 0x47, 0xED, 0x5E, 0xFB, 0xCD, S["render"] & 255, S["render"] >> 8, 0x18, 0xFB]))
m.pc = SCR; m.sp = S["FSTACK"]
isr_lo, isr_hi = S["isr"], S["cls"]            # isr body lies in [isr, cls)
in_isr = [False]
FL_PG1 = S["fl_pg1"]; FL_PGB = S["fl_pgb"]
bad_disp = [0]; switch_outside_isr = [0]; sw = [0]
def hook2(addr, value):
    # a write into the DISPLAYED screen (pixels or attributes of the window/HUD rows copied per frame) = tear risk
    disp7 = shown[0] == 1
    if (not disp7 and 0x4000 <= addr < 0x5B00) or (disp7 and cur[0] == 7 and 0xC000 <= addr < 0xDB00):
        bad_disp[0] += 1
def on_out2(port, val):
    if port == 0x7FFD and ((val >> 3) & 1) != shown[0]:
        sw[0] += 1
        if not (FL_PG1 <= m.pc < FL_PGB + 12): switch_outside_isr[0] += 1   # the switch byte may only leave via fl_pg1's out (snd_isr)
    on_out(port, val)
m.set_output_callback(on_out2); m.set_write_callback(hook2); m.mark_addrs(0x4000, 0x1B00, m.WRITE_MARK); m.mark_addrs(0xC000, 0x1B00, m.WRITE_MARK)
accepted = 0; del outs[:]; frames_seen = 0; last_frames = 0
req_seen = 0; prev_req = 0
for f in range(60):
    m.ticks_to_stop = 69888
    while m.ticks_to_stop > 0:
        m.run()
        if m.halted: break
    for k in range(8):                     # lane K1 (6 Nov 2026): the ULA holds INT for 32 T, so an INT the core refuses because the
        if m.on_handle_active_int(): accepted += 1; break     # frame boundary fell on an EI / DD-FD-ED-CB prefix is re-offered within that window
        m.ticks_to_stop = 4; m.run()       # (the K1 build's render timing put 2 of 60 boundaries on such instructions; the pre-K1 one none)
    if m.memory[S["fl_req"]]: req_seen += 1
m.ticks_to_stop = 6000; m.run()
# lane F2 (7 Nov 2026): the 60th tick may fall inside a bank-7 copy phase (fl_hud now mirrors 6912 B): let that phase end (fl_pg0)
# before judging the paging state - and before call() re-enters code at C000h.. (with bank 7 paged that is screen data, not code)
for k in range(40):
    if cur[0] == 0 and (m.memory[BANKM] & 7) == 0: break
    m.ticks_to_stop = 5000; m.run()
m.set_write_callback(lambda a, v: None); m.unmark_addrs(0x4000, 0x1B00, m.WRITE_MARK); m.unmark_addrs(0xC000, 0x1B00, m.WRITE_MARK)
m.set_output_callback(on_out)
ticks = struct.unpack_from("<H", bytes(m.memory[S["ticks"]:S["ticks"] + 2]))[0]
forced_bank0_shown = sum(1 for v in pg() if v in (0x10, 0x11, 0x17, 0x18, 0x19, 0x1F))
check(accepted == 60 and ticks == 60 and cur[0] == 0 and (m.memory[BANKM] & 7) == 0,
      "F2 60 INTs @69,888 T through render+flip: accepted %d, ticks=%d (none lost), bank 0 paged after the copy phase, BANKM=%02Xh" % (accepted, ticks, m.memory[BANKM]))
check(sw[0] >= 7 and switch_outside_isr[0] == 0, "F3 display switches: %d (>= 7 in 60 ticks: ~7.5 ticks/frame + ~2 ticks for the first frame's 6.9 KB HUD mirror; lane F: 8 with the 3.1 KB mirror), all written inside the ISR (%d outside)" % (sw[0], switch_outside_isr[0]))
check(bad_disp[0] == 0, "B tear-free: writes into the DISPLAYED screen while displayed = %d (NOTE: the write hook does not land values; counts only)" % bad_disp[0])
# frame content proof (hook off, so values land): one more full frame into the hidden screen, then compare
set_bankm(m.memory[BANKM] | 0)
for k in range(64):                        # lane K1: a flip still pending from the loop's last frame -> let the ISR apply it first (fl_wait
    if not m.memory[S["fl_req"]]: break    # inside render spins until the ISR clears fl_req, and call() injects no interrupts)
    if m.on_handle_active_int(): m.ticks_to_stop = 6000; m.run()
    else: m.ticks_to_stop = 4; m.run()
call("render", limit=6_000_000)                # ends with fl_req set for the hidden screen
hid = 0xC000 if (m.memory[BANKM] & 8) == 0 else 0x4000
buf = bytes(m.memory[S["BUF"]:S["BUF"] + 2304])
def window2(base):
    out = bytearray()
    for c in range(24):
        for r in range(96):
            y = 8 + r; addr = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (4 + c)
            out.append(m.memory[0x4000 + addr] if base == 0x4000 else bank(7)[addr])
    return bytes(out)
def attrs2(base):
    src = m.memory if base == 0x4000 else None
    out = bytearray()
    for row in range(12):
        a0 = 0x1800 + (row + 1) * 32 + 4
        out += bytes(m.memory[0x4000 + a0:0x4000 + a0 + 24]) if base == 0x4000 else bank(7)[a0:a0 + 24]
    return bytes(out)
staged = bytes(m.memory[S["BUF"]:S["BUF"] + 2304])   # BUF is reused as staging AFTER the copy: window bytes == BUF before attr_write? no:
# attr_write stages the 288 cells into BUF+24h.. (stride 32), which overwrites part of BUF after COPYBUF ran. So compare
# the hidden window against BUF *as it was copied*: re-derive it from the hidden screen itself is circular; instead render
# again with fl_frame stubbed to get the pristine BUF for the same camera state.
save = bytes(m.memory[S["fl_frame"]:S["fl_frame"] + 1]); m.set_memory_block(S["fl_frame"], b"\xc9")
hid_win = window2(hid); hid_attr = attrs2(hid)
# lane M2: the frame above left fl_req set; the default build's hr_pass (BANK3) begins every sprite with fl_wait, which spins until
# the ISR clears fl_req - and call() injects no interrupts. Read the request now, clear it for the pristine render (fl_frame is
# stubbed, so nothing sets it again), then put it back so section 6 below starts from the same state as before.
req = m.memory[S["fl_req"]]; m.set_memory_block(S["fl_req"], b"\x00")
call("render", limit=6_000_000); m.set_memory_block(S["fl_frame"], save)
pristine = bytes(m.memory[S["BUF"]:S["BUF"] + 2304])
# staged attributes for that same frame: run attr_write alone (writes BUF+24h..)
call("attr_write", limit=2_000_000)
stage = bytearray()
for row in range(12):
    a0 = S["BUF"] + 0x24 + row * 32
    stage += bytes(m.memory[a0:a0 + 24])
m.set_memory_block(S["fl_req"], bytes([req]))
check(hid_win == pristine, "B hidden screen (%s) pixel window == rendered BUF (2304 B): %s" % ("bank 7" if hid == 0xC000 else "screen 0", hid_win == pristine))
check(hid_attr == bytes(stage), "B hidden screen attribute window == attr_write's 288 staged cells: %s" % (hid_attr == bytes(stage)))
check(req in (0x10, 0x18) and ((req >> 3) & 1) == (1 if hid == 0xC000 else 0), "B fl_req after the frame = %02Xh -> shows the screen just drawn" % req)
# ---- 6 rule F6 (lane F2): outside the window the two screens are identical (bank 7 == screen 0's pattern + HUD-area bytes).
# The 60-frame loop ran with the write hook on (values do not land), so the mirror is exercised here again with the hook off:
# hud_dirty := 1, then frames (with the ISR flip between them) until fl_hud has run - at most 2, since it only copies in a
# frame where bank 7 is the hidden screen.
m.set_memory_block(S["hud_dirty"], b"\x01"); fr6 = 0
while m.memory[S["hud_dirty"]] and fr6 < 3:
    for k in range(64):
        if not m.memory[S["fl_req"]]: break
        if m.on_handle_active_int(): m.ticks_to_stop = 6000; m.run()
        else: m.ticks_to_stop = 4; m.run()
    call("render", limit=6_000_000); fr6 += 1
def outside_window(addr):
    o = addr - 0x4000
    if o >= 0x1800:
        row, col = (o - 0x1800) >> 5, (o - 0x1800) & 31
        return not (1 <= row <= 12 and 4 <= col <= 27)
    y = ((o >> 5) & 0xC0) | ((o >> 8) & 7) | ((o >> 2) & 0x38); x = o & 31
    return not (8 <= y < 104 and 4 <= x <= 27)
b7 = bank(7)
outs6 = [a for a in range(0x4000, 0x5B00) if outside_window(a)]
bad6 = [a for a in outs6 if b7[a - 0x4000] != m.memory[a]]
pat_kept = sum(1 for a in outs6 if m.memory[a] == PAT0[a - 0x4000])
check(fr6 <= 2 and not bad6 and pat_kept == len(outs6) and b7[0x0703] == PAT0[0x0703] and b7[0x08A0] == PAT0[0x08A0] and b7[0x1823] == PAT0[0x1823],
      "F6 hud_dirty cleared after %d frame(s); outside the window (%d of 6912 B: pixel rows 0..7 + 104..191, columns 0..3 / 28..31, attribute rows 0 + 13..23 + frame columns) bank 7 == screen 0: %d mismatches; screen 0 kept its pattern there (%d/%d); frame line 4703h, rail 48A0h, frame attr 5823h mirrored" % (
          fr6, len(outs6), len(bad6), pat_kept, len(outs6)))
w6 = [a for a in range(0x4000, 0x5B00) if not outside_window(a)]
check(len(w6) == 2304 + 288 and sum(1 for a in w6 if m.memory[a] != PAT0[a - 0x4000]) > 2000,
      "F6 window region = %d B (2304 pixel + 288 attribute bytes); screen 0's window was redrawn by the frames (%d B differ from the pattern)" % (len(w6), sum(1 for a in w6 if m.memory[a] != PAT0[a - 0x4000])))
say("== %s (%d checks failed)" % ("ALL CHECKS PASSED" if not fails else "FAILED", len(fails))); sys.exit(1 if fails else 0)
