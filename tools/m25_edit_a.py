#!/usr/bin/env python3
"""m25_edit_a.py - M2.5 step A: ONE INK for the whole 3D window + masked sprites (zero attribute clash, Zosya/TTT style).
Idempotent source edits (asserts on every anchor; prints what it did):
 1. tools/gen48.py: drop CODEINK/ATTRTAB (tables48), ATTR_d x7 + ATTRCOPY (unrolled48); runs16() grows a 1-px black halo
    around every ink pixel (transparent 8-neighbours of ink become black) so a white figure stays readable on a white wall.
 2. src/48k/kea48.asm: no per-byte-column attribute write in the ray loop (attr_jp block), no ATTRCOPY call, no ATTRBUF.
    The window attributes are 0x07 (white ink, black paper) from cls and are never touched again.
 3. src/common/sprites_f.asm: the pre-M2.4 masked blit (white runs OR slot, black runs AND not slot, transparent runs leave
    the wall) without the card and without the per-cell attribute span (dc_mark/dc_attr). Base copy:
    build/pre_m25/sprites_f_pre_m24.asm (extracted from build/pre_m24/src_pre_m24.tgz).
usage: m25_edit_a.py   (run from anywhere; exit 1 on a missing anchor)"""
import pathlib, re, sys, tarfile, io

ROOT = pathlib.Path(__file__).resolve().parents[1]
done = []

def edit(path, pairs, tag):
    p = ROOT / path
    s = p.read_text()
    changed = False
    for old, new, once_marker in pairs:
        if once_marker in s and old not in s:
            continue                                   # already applied
        assert old in s, "%s: anchor missing:\n%s" % (path, old[:200])
        s = s.replace(old, new, 1); changed = True
    if changed:
        p.write_text(s); done.append(tag)
    return changed

# ---------------------------------------------------------------- 1. gen48.py
HALO_MARK = "M2.5 halo"
edit("tools/gen48.py", [
    ('         "CODEINK:", "        defb 0,2,7,6,5,4,7,3,6,2,1,2,4,0,0,0",\n', '', 'M2.5: one ink'),
    ('         "ATTRTAB:", "        defw ATTR_0,ATTR_1,ATTR_2,ATTR_3,ATTR_4,ATTR_5,ATTR_6",\n',
     '         # M2.5: one ink for the whole window - no CODEINK / ATTRTAB / ATTR_d / ATTRCOPY\n', 'M2.5: one ink'),
], "gen48 tables")

g = (ROOT / "tools/gen48.py").read_text()
a0 = g.find("    # ---- ATTR_d: attributes of one byte column into ATTRBUF")
a1 = g.find("    # ---- COPYBUF: buffer -> screen")
if a0 != -1:
    assert a1 > a0
    g = g[:a0] + "    # M2.5: ATTR_d / ATTRCOPY removed (one ink for the whole window, set once by cls)\n" + g[a1:]
    (ROOT / "tools/gen48.py").write_text(g); done.append("gen48 unrolled ATTR_d/ATTRCOPY removed")
else:
    assert "M2.5: ATTR_d / ATTRCOPY removed" in g

g = (ROOT / "tools/gen48.py").read_text()
old = '''        m = [1] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h: bc * 2 * h + h]]
        p = [0] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h + h: bc * 2 * h + 2 * h]]
        codes = [0 if m[v] else (3 if p[v] else 1) for v in range(box)]
'''
new = '''        m = [1] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h: bc * 2 * h + h]]
        p = [0] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h + h: bc * 2 * h + 2 * h]]
        codes = [0 if (m[v] and not halo[v][u]) else (3 if p[v] else 1) for v in range(box)]   # M2.5 halo
'''
if HALO_MARK not in g:
    assert old in g, "runs16 anchor missing"
    g = g.replace(old, new, 1)
    old2 = '''    cols = []
    for u in range(16):
        bc, bit = u >> 3, 7 - (u & 7)
'''
    new2 = '''    cols = []
    # M2.5 halo: every transparent pixel with an ink pixel among its 8 neighbours (inside the 16 x box) becomes black, so a
    # white figure keeps a 1-px dark outline on a white wall (TTT-style masked sprite; one ink for the whole window).
    def ink_at(u, v):
        if not (0 <= u < 16 and box - h <= v < box): return 0
        return (data[(u >> 3) * 2 * h + h + (v - (box - h))] >> (7 - (u & 7))) & 1
    halo = [[any(ink_at(u + du, v + dv) for du in (-1, 0, 1) for dv in (-1, 0, 1) if du or dv) for u in range(16)]
            for v in range(box)]
    for u in range(16):
        bc, bit = u >> 3, 7 - (u & 7)
'''
    assert old2 in g, "runs16 header anchor missing"
    g = g.replace(old2, new2, 1)
    (ROOT / "tools/gen48.py").write_text(g); done.append("gen48 runs16 halo")

# ---------------------------------------------------------------- 2. kea48.asm
k = (ROOT / "src/48k/kea48.asm").read_text()
MARK2 = "M2.5: one ink for the whole window"
if MARK2 not in k:
    b0 = k.find("        ld a,(sub4)\n        or a\n        jr nz,rd_band\n; first ray of the byte: attributes")
    b1 = k.find("attr_jp:\n        call 0\nrd_band:\n")
    assert b0 != -1 and b1 > b0, "kea48 attr block anchors missing"
    k = k[:b0] + "; " + MARK2 + " (0x07 white on black from cls, never rewritten): no per-column attributes\n" + k[b1 + len("attr_jp:\n        call 0\n"):]
    old = "        call ATTRCOPY          ; M2.1: window attributes in one go (walls + sprite ink), before the pixels land\n"
    assert old in k; k = k.replace(old, "", 1)
    old = "ATTRBUF equ 27168          ; M2.1: 0x6A20..0x6ADF, 12 rows x 16 window attributes built per frame (walls, then sprite ink) -> ATTRCOPY\n"
    assert old in k; k = k.replace(old, "", 1)
    old = "; screen in one burst (COPYBUF) at the end of render; attributes are written directly, once per byte column.\n"
    assert old in k
    k = k.replace(old, "; screen in one burst (COPYBUF) at the end of render. M2.5: the window has ONE ink (0x07, set by cls) - walls, floor,\n"
                       "; ceiling and sprites are all white on black, so no attribute cell can ever clash (Zosya/TTT style); the HUD keeps its colours.\n", 1)
    old = "        call draw_things       ; T1: scaled masked sprites with zbuf depth test (M2.1: + sprite ink cells into ATTRBUF)\n"
    assert old in k
    k = k.replace(old, "        call draw_things       ; T1: scaled masked sprites with zbuf depth test (M2.5: masked blit, no attributes)\n", 1)
    (ROOT / "src/48k/kea48.asm").write_text(k); done.append("kea48 attr code removed")

# ---------------------------------------------------------------- 3. sprites_f.asm
base = ROOT / "build/pre_m25/sprites_f_pre_m24.asm"
if not base.exists():
    with tarfile.open(ROOT / "build/pre_m24/src_pre_m24.tgz") as t:
        base.write_bytes(t.extractfile("src/common/sprites_f.asm").read())
    done.append("base sprites_f extracted")
f = (ROOT / "src/common/sprites_f.asm").read_text()
MARK3 = "M2.5 masked blit"
if MARK3 not in f:
    s = base.read_text()
    h0 = s.find("ds_cols:\n")
    assert h0 != -1
    s = ("; sprites_f.asm (T1) - per-column sprite blit, " + MARK3 + " (one ink for the whole window: zero attribute clash).\n"
         "; Column c (0..63): zbuf[c] <= hv (no nearer wall) -> visible. Buffer byte column c/4, slot bits SLOTM[c&3]. Each run\n"
         "; (v0..v1 source rows, code 1 black / 3 white; tools/gen48.py runs16 adds a 1-px black halo round the ink) maps through\n"
         "; ROWTAB to rows r0..r1 and goes through the SCHAIN with n = r1 - r0 rows: B = or-bits (slot for white, 0 for black),\n"
         "; C = and-mask (255 for white, not slot for black). Transparent runs leave the wall pixels. No attribute work at all.\n") + s[h0:]
    old = "        ld (ds_cnt),a\n        ld hl,ds_rmin\n        ld b,16\n        ld a,255\ndc_clr: ld (hl),a              ; rmin = 255 (no ink), rmax = 0\n        set 4,l\n        ld (hl),0\n        res 4,l\n        inc l\n        djnz dc_clr\n"
    assert old in s, "sprites_f dc_clr anchor"
    s = s.replace(old, "        ld (ds_cnt),a\n", 1)
    old = ("; buffer address: D = BUF/256 + (c>>3), E = (c&4)<<5 ; slot mask ; byte column for the attribute span\n"
           "        ld a,(ds_c)\n        ld c,a\n        rrca\n        rrca\n        and 15\n        add a,ds_rmin and 255\n        ld (dc_rmin+1),a       ; -> ds_rmin[bc] (ds_rmax = ds_rmin + 16, same page)\n")
    assert old in s, "sprites_f buffer address anchor"
    s = s.replace(old, "; buffer address: D = BUF/256 + (c>>3), E = (c&4)<<5 ; slot mask\n        ld a,(ds_c)\n        ld c,a\n", 1)
    old = "        ld a,(dc_code)\n        cp 3\n        call z,dc_mark         ; ink run: widen the byte column's ink span (B, C preserved)\n"
    assert old in s, "sprites_f dc_mark call anchor"
    s = s.replace(old, "", 1)
    old = "        jp nz,dc_l\n        jp dc_attr\n"
    assert old in s, "sprites_f dc_attr jump anchor"
    s = s.replace(old, "        jp nz,dc_l\n        ret\n", 1)
    m0 = s.find("; dc_mark: C = r0, B = n")
    m1 = s.find("dc_run: defw 0\n")
    assert m0 != -1 and m1 > m0, "sprites_f dc_mark/dc_attr block anchors"
    s = s[:m0] + s[m1:]
    old = "        ; ds_rmin[16] then ds_rmax[16] -> DRAM (state.asm, M2.2): 32-byte aligned so bit 4 of the address toggles between them\n"
    assert old in s
    s = s.replace(old, "", 1)
    (ROOT / "src/common/sprites_f.asm").write_text(s); done.append("sprites_f masked blit")

print("m25_edit_a:", ", ".join(done) if done else "already applied (no changes)")
