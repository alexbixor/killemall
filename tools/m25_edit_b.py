#!/usr/bin/env python3
"""m25_edit_b.py - M2.5 step B: textured ceiling (user 30 Oct: "add the ceiling and tint"). Idempotent source edits:

 1. tools/gen48.py
    - CLRBUF: the 24 ceiling pushes (rows 47..0) now push the alternate-set words DE' = 0x1144 (sparse dots: even row 0x44,
      odd row 0x11) or HL' = 0x11FF (motion line: even row 46-2w solid = mirror of the floor line row 49+2w) instead of BC = 0.
      Labels: cl_ce (ld de,dots), cl_cw (ld hl,line word), cl_cl (first ceiling push). Opcodes stay D5/E5 so fl_set patches
      both halves with the same values.
    - bands: every row does (byte and C) or B - the rows above the horizon used plain OR because the ceiling was black; with
      dots there the wall's own slot bits must be cleared first (+1 B / +4 T per row above the horizon, 1,320 B of code).
    - tables: cos(a) = sin(a+64) exactly (same rounding), likewise plx/ply and movx/movy -> COSTAB/PLXTAB/MOVXTAB become
      aliases 128 B into SINTAB/PLYTAB/MOVYTAB, each extended by 64 wrap entries (320 words). Saves 1,152 B. Asserted.
 2. src/common/floor.asm: fl_set writes each word's opcode twice: floor push (DE, word 23..0 upward) and the mirrored ceiling
    push (IX from cl_cl+23 downward) -> the ceiling lines are the exact mirror of the floor lines (same phase, same flow).
 3. src/48k/kea48.asm: apply_opts also patches cl_ce+1 / cl_cw+1 (DETAIL LOW -> plain black ceiling, lines 0x00FF).
The 128K build inherits everything via make128.py (same gen files, same floor.asm)."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
G, F, K = ROOT / "tools/gen48.py", ROOT / "src/common/floor.asm", ROOT / "src/48k/kea48.asm"

def edit(path, pairs, marker):
    s = path.read_text()
    if marker in s:
        print("%s: step B already applied" % path.name); return
    for old, new in pairs:
        assert s.count(old) == 1, "anchor not unique/found in %s: %r" % (path.name, old[:60])
        s = s.replace(old, new)
    path.write_text(s); print("%s: step B applied" % path.name)

# ---- 1. gen48.py
g_pairs = [
 ('  CLRBUF   PUSH-fills the buffer: rows 0-47 zero, rows 48-95 the floor checker (0xAA even rows / 0x55 odd rows).',
  '  CLRBUF   PUSH-fills the buffer: rows 48-95 the floor checker (0xAA even rows / 0x55 odd rows) + distance lines, rows 0-47\n'
  '           (M2.5B) the ceiling: sparse dots (0x44 even rows / 0x11 odd rows) + the mirrored distance lines (alternate set).'),
 ('           B = texel & IXL; rows above the horizon: byte |= B; rows below (over the floor checker): byte = (byte & C) | B.',
  '           B = texel & IXL; every row: byte = (byte & C) | B (M2.5B: the ceiling has dots, so rows above the horizon mask too).'),
 ('         "SINTAB:", dw(sin), "COSTAB:", dw(cos), "PLXTAB:", dw(plx), "PLYTAB:", dw(ply),\n'
  '         "MOVXTAB:", dw(movx), "MOVYTAB:", dw(movy),\n',
  '         # M2.5B: cos(a) == sin(a+64) exactly (same rounding), likewise plx/ply and movx/movy -> the x tables are aliases\n'
  '         # 128 B into the y tables, which carry 64 wrap entries (320 words each). 1,152 B saved for the textured ceiling bands.\n'
  '         "SINTAB:", dw(sin + sin[:64]), "COSTAB  equ SINTAB+128",\n'
  '         "PLYTAB:", dw(ply + ply[:64]), "PLXTAB  equ PLYTAB+128",\n'
  '         "MOVYTAB:", dw(movy + movy[:64]), "MOVXTAB equ MOVYTAB+128",\n'),
 ('    htabn = [wall_height(i / 64) for i in range(256)]\n',
  '    htabn = [wall_height(i / 64) for i in range(256)]\n'
  '    assert all(cos[a] == sin[(a + 64) & 255] for a in range(256)), "COSTAB alias"\n'
  '    assert all(plx[a] == ply[(a + 64) & 255] for a in range(256)), "PLXTAB alias"\n'
  '    assert all(movx[a] == movy[(a + 64) & 255] for a in range(256)), "MOVXTAB alias"\n'),
 ('            if r >= lower_from:\n                s.append("        and c")\n',
  '            s.append("        and c")                      # M2.5B: also above the horizon (ceiling dots under the wall slot)\n'),
 ('    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2048", "        ld bc,0", "cl_de:  ld de,%d" % (0x55 * 256 + 0xAA),\n',
  '    # M2.5B: ceiling words live in the alternate set: DE\' = dots 0x1144 (D odd row 0x11, E even row 0x44), HL\' = line word\n'
  '    #        0x11FF (even row 46-2w solid = mirror of the floor line row 49+2w). apply_opts patches cl_ce+1 / cl_cw+1.\n'
  '    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2048", "        exx",\n'
  '          "cl_ce:  ld de,%d" % (0x11 * 256 + 0x44), "cl_cw:  ld hl,%d" % (0x11 * 256 + 0xFF), "        exx",\n'
  '          "cl_de:  ld de,%d" % (0x55 * 256 + 0xAA),\n'),
 ('    s += ["cl_fl:  push de"] + ["        push de"] * 23 + ["        push bc"] * 24   # M2.3: fl_set patches cl_fl..+23 (D5/E5)\n',
  '    s += ["cl_fl:  push de"] + ["        push de"] * 23                              # M2.3: fl_set patches cl_fl..+23 (D5/E5)\n'
  '    s += ["        exx", "cl_cl:  push de"] + ["        push de"] * 23 + ["        exx"]   # M2.5B: ceiling word 0 (rows 47/46) .. 23 (rows 1/0); fl_set mirrors cl_cl..+23\n'),
]
edit(G, g_pairs, "cl_cl:  push de")

# ---- 2. floor.asm
f_pairs = [
 ('        ld hl,FL_D4+24\n        ld de,cl_fl            ; first floor push = word 23 (rows 95,94) ... last = word 0 (rows 49,48)\n',
  '        ld hl,FL_D4+24\n        ld de,cl_fl            ; first floor push = word 23 (rows 95,94) ... last = word 0 (rows 49,48)\n'
  '        ld ix,cl_cl+23         ; M2.5B: ceiling push of word 23 (rows 1,0); ceiling pushes run word 0 (cl_cl, rows 47,46) .. 23\n'),
 ('fl_w:   ld (de),a\n        inc de\n',
  'fl_w:   ld (de),a\n        ld (ix+0),a            ; M2.5B: same opcode for the mirrored ceiling word (DE\'/HL\' in CLRBUF: dots / line)\n'
  '        inc de\n        dec ix\n'),
 ('; blocked axis adds nothing, so standing against a wall does not flow. Cost: fl_set 2,880 T per frame (<1%).\n',
  '; blocked axis adds nothing, so standing against a wall does not flow. Cost: fl_set 2,880 T per frame (<1%).\n'
  '; M2.5B: the 24 ceiling pushes (cl_cl, rows 47..0, alternate set DE\' = dots 0x1144 / HL\' = line 0x11FF) get the same opcode as\n'
  '; their mirror floor word (ceiling rows 46-2w,47-2w <-> floor rows 48+2w,49+2w), so the ceiling lines mirror the floor lines\n'
  '; exactly and flow the same way. IX is free here (set per ray later). Cost ~3,600 T per frame.\n'),
]
edit(F, f_pairs, "ld ix,cl_cl+23")

# ---- 3. kea48.asm
k_pairs = [
 ('apply_opts:                    ; opt_detail 0 -> plain floor (CLRBUF fill 0x0000), 1 -> dithered 0x55AA\n'
  '        ld hl,0x55AA\n        ld a,(opt_detail)\n        or a\n        jr nz,ao1\n        ld h,a\n        ld l,a\nao1:    ld (cl_de+1),hl\n        ret\n',
  'apply_opts:                    ; opt_detail 0 -> plain floor + ceiling (CLRBUF fills 0x0000, lines stay), 1 -> floor checker 0x55AA + ceiling dots 0x1144\n'
  '        ld hl,0x55AA\n'
  '        ld de,0x1144           ; M2.5B: ceiling dots word (DE\' in CLRBUF)\n'
  '        ld bc,0x11FF           ; M2.5B: ceiling line word (HL\' in CLRBUF): even row solid line, odd row dots\n'
  '        ld a,(opt_detail)\n        or a\n        jr nz,ao1\n        ld h,a\n        ld l,a\n        ld d,a\n        ld e,a\n'
  '        ld b,a                 ; DETAIL LOW: ceiling line word 0x00FF (plain black around the line)\n'
  'ao1:    ld (cl_de+1),hl\n        ld (cl_ce+1),de\n        ld (cl_cw+1),bc\n        ret\n'),
 ('        call CLRBUF            ; back buffer: ceiling black, floor checker + lines (PUSH fill)\n',
  '        call CLRBUF            ; back buffer: ceiling dots + mirrored lines, floor checker + lines (PUSH fill, M2.5B)\n'),
]
edit(K, k_pairs, "ld (cl_ce+1),de")
print("done")
