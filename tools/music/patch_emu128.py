#!/usr/bin/env python3
"""patch_emu128.py - T3: make snd_emu128.py prove the SFX pre-emption on the emulator (SFX 10 = 31 frames, fast polling)."""
import pathlib
P = pathlib.Path(__file__).resolve().parent / "snd_emu128.py"
s = P.read_text()
old = s[s.index('    zrcp(s, "send-keys-ascii 1", 0.05); time.sleep(0.06)'):s.index('    ok = (r0 != r1)')]
new = '''    # SFX 10 (player death, 31 frames = 620 ms): press key 0, then poll ay_regs quickly
    zrcp(s, "send-keys-ascii 0", 0.02)
    seen = []
    for i in range(8):
        r = zrcp(s, "read-memory %d 12" % SYM["ay_regs"], 0.02)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        if len(h) >= 24:
            regs = bytes.fromhex(h[:24]); seen.append(regs)
            print("  poll %d: R4/R5 %02x %02x  R6 %02x  R7 %02x  R10 %02x" % (i, regs[4], regs[5], regs[6], regs[7], regs[10]))
    attr = mem(s, 22528, 16)
    print("attr row 0 (cell 11 = SFX 10 marker 70):", attr.hex(" "))
    r4 = r5 = None
    sfx_seen = any(((r[5] << 8) | r[4]) >= 250 and r[10] >= 12 for r in seen)
    print("SFX 10 visible on channel C during the polls:", sfx_seen)
'''
s = s.replace(old, new)
P.write_text(s); print("patched")
