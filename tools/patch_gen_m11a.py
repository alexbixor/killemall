#!/usr/bin/env python3
"""patch_gen_m11a.py - one-shot patch of tools/gen48.py for the M1.1a back buffer:
  CLEARW  fills the back buffer (HL = BUF): 16 columns x (48 bytes B, 48 bytes alternating D/E), column stride 128.
  BND_Rn  identical texel maths, but the row step is 'inc l' (column-major buffer, no screen page crossings).
  COPYBUF copies the 16x96 window from BUF to the screen in one burst (DI, SP-based reads, EI), 16 bit at a time:
          for each column: pop 48 words from BUF column, store to the 96 screen rows of that byte column via (hl) with the
          screen row table folded in as immediate adjustments. Register-only, no per-frame table lookups."""
import pathlib
p = pathlib.Path("/home/ubuntu/work/killemall/tools/gen48.py"); t = p.read_text()

def rep(old, new):
    global t
    assert t.count(old) == 1, old
    t = t.replace(old, new)

old_clear = t[t.index("    # ---- CLEARW: HL = SCRWIN"):t.index("    # ---- BND: masked textured band")]
new_clear = '''    # ---- CLEARW: HL = BUF (column-major back buffer, 16 columns x 128 stride); B = 0, D = 0xAA, E = 0x55
    s.append("CLEARW:")
    for c in range(16):
        for r in range(96):
            src = "b" if r < 48 else ("d" if r % 2 == 0 else "e")
            s.append("        ld (hl),%s" % src)
            s.append("        inc l")
        if c != 15:
            s.extend(["        ld a,l", "        add a,32", "        ld l,a", "        jr nc,$+3", "        inc h"])
    s.append("        ret")
    # ---- COPYBUF: back buffer -> screen window, one burst.  Uses SP to read the buffer (DI around it).
    # Interrupts stay ENABLED: the IM2 ISR pushes 4 bytes below SP, i.e. onto buffer bytes already popped (or onto
    # 24572..24575 below the buffer at the very start), so nothing still to be copied can be clobbered.  A 26k-T DI window
    # would lose ~37% of the 32-T ULA interrupt pulses and break the fps counter.
    s.append("COPYBUF:")
    s.append("        ld (cb_sp+1),sp")
    for c in range(16):
        s.append("        ld sp,BUF+%d" % (c * 128))
        for r in range(0, 96, 2):
            s.append("        pop de")
            if r == 0:
                s.append("        ld hl,%d" % (scr_addr(8) + 8 + c))
            else:
                d = (scr_addr(8 + r) + 8 + c) - (scr_addr(8 + r - 1) + 8 + c)
                if d == 256:
                    s.append("        inc h")
                else:
                    s.append("        ld hl,%d" % (scr_addr(8 + r) + 8 + c))
            s.append("        ld (hl),e")
            s.append("        inc h")
            s.append("        ld (hl),d")
    s.append("cb_sp:  ld sp,0")
    s.append("        ei")
    s.append("        ret")
'''
rep(old_clear, new_clear)
old_bnd = '''        s.extend(["        exx", "        ld a,h", "        add hl,bc", "        exx", "        ld e,a",
                  "        ld a,(de)", "        xor (hl)", "        and c", "        xor (hl)", "        ld (hl),a",
                  "        inc h"])
        if r % 8 == 7 and r < 95:
            s.extend(["        ld a,l", "        add a,32", "        ld l,a"])
            if r != 55:
                s.extend(["        ld a,h", "        sub 8", "        ld h,a"])
'''
new_bnd = '''        s.extend(["        exx", "        ld a,h", "        add hl,bc", "        exx", "        ld e,a",
                  "        ld a,(de)", "        xor (hl)", "        and c", "        xor (hl)", "        ld (hl),a",
                  "        inc l"])
'''
rep(old_bnd, new_bnd)
rep('''  CLEARW   fills the 128x96 window: rows 0-47 with B (0), rows 48-95 alternately D/E (0xAA/0x55).  HL = SCRWIN.
  BND_Rn   masked textured column: HL screen, C mask, D texture page; alt set: HL' = u*16.frac accumulator, BC' = step.
           new byte = bg ^ ((texel ^ bg) & mask).  Caller pokes RET at BANDROW[bot] and calls BANDROW[top].''',
'''  CLEARW   fills the 128x96 back buffer (column-major, 16 x 128 stride): rows 0-47 with B (0), rows 48-95 alternately
           D/E (0xAA/0x55).  HL = BUF.
  BND_Rn   masked textured column: HL back-buffer byte (row step inc l), C mask, D texture page; alt set: HL' = u*16.frac
           accumulator, BC' = step.  new byte = bg ^ ((texel ^ bg) & mask).  Caller pokes RET at BANDROW[bot], calls BANDROW[top].
  COPYBUF  copies the buffer to the screen window in one DI/EI burst (SP reads 2 bytes per pop, 1536 bytes).''')
p.write_text(t)
print("patched", p)
