#!/usr/bin/env python3
"""m26_edit_stain.py - M2.6 blood 3 "floor stain": idempotent source edits (3 Nov 2026; user 11:2xZ: 'no, stain after the
video'). Run it twice; the second run must print 'changed: nothing'. Apply AFTER tools/m26_edit_blood.py (that script's put()
rewrites blood.asm wholesale and would undo piece 2). Pieces:
 1. src/common/attr.asm attr_write: the sprite-ink decode honours CMX bit 7 = "not BRIGHT" (after the 4 rrca it is bit 3):
    cells of such a sprite get ink only (dim). +6 B.
 2. src/common/blood.asm ds_inkl: a corpse (state 3, flash over) colours its cells 0xA0 = red, not BRIGHT, instead of 0
    (window ink). The dead frames lie on the floor, so the enemy's cells become a dark red stain exactly where it fell, for
    as long as the level lasts. The fatal hit still flashes BRIGHT red for 3 frames first. +1 B (padding before COLBASE).
 3. src/common/attrfill.asm (new): aw_fill moved out of attr.asm (13 B) into the 22 B alignment padding before TEX
    (tools/gen48.py, after dsp_tab), because the 48K high block had exactly the 40 B gate left. Net high block: +6 - 13 = -7 B.
 4. tools/gen48.py: include attrfill.asm after dsp_tab (48K and 128K images both use gen/tables48.asm).
 5. tools/build_m25_48.sh: gate af_end <= TEX (the routine stays inside the padding, TEX stays page aligned).
 6. tools/p2e_oracle.py: ink_of returns the attribute byte (ink | BRIGHT, 0x42 flash, 0x02 corpse stain); expected() writes it.
 7. src/common/lowcode.asm, attr.asm: comments for the CMX bit-7 meaning."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
changed = []

def edit(rel, pairs, must=None):
    p = ROOT / rel; s = p.read_text(); o = s
    for old, new in pairs:
        if new.startswith(old):                                  # pure insertion after old: undo any doubled insertion
            ins = new[len(old):]
            while ins + ins in s: s = s.replace(ins + ins, ins)
        if new in s: continue                                    # already applied
        if old not in s: sys.exit("%s: anchor not found:\n%s" % (rel, old))
        assert s.count(old) == 1, (rel, old)
        s = s.replace(old, new)
    if must and must not in s: sys.exit("%s: expected text missing: %s" % (rel, must))
    if s != o: p.write_text(s); changed.append(rel)

def put(rel, text):
    p = ROOT / rel
    if p.exists() and p.read_text() == text: return
    p.write_text(text); changed.append(rel)

# 3. attrfill.asm (new): aw_fill verbatim from attr.asm
put("src/common/attrfill.asm", """; attrfill.asm - aw_fill of attr.asm (M2.6 P2E), moved here on 3 Nov 2026 for M2.6 blood 3 "floor stain": the 48K high block
; had exactly the 40 B build gate left and the stain decode in attr_write (CMX bit 7 = not BRIGHT) costs 6 B, so this 13-byte
; routine went into the 22 B alignment padding before TEX (tools/gen48.py -> gen/tables48.asm, right after dsp_tab; the 128K
; image has the same padding one page up). Build gate (tools/build_m25_48.sh): af_end <= TEX and TEX page aligned.
; aw_fill: B cells of attribute A down the byte column at HL (row-0 cell, kept) from cell row C; DE = 32.
aw_fill:
        push hl
        inc c
        dec c
        jr z,af2
af1:    add hl,de              ; skip C rows
        dec c
        jr nz,af1
af2:    ld (hl),a
        add hl,de
        djnz af2
        pop hl
        ret
af_end  equ $                  ; must stay <= TEX (build gate)
""")

# 1. + 7. attr.asm: dim decode, aw_fill removed, comments
edit("src/common/attr.asm", [(
";  3. per byte column with sprite marks (lowcode.asm dc_mark -> CMIN): rows first .. last = sprite ink | BRIGHT, marks cleared\n",
";  3. per byte column with sprite marks (lowcode.asm dc_mark -> CMIN): rows first .. last = sprite ink | BRIGHT, marks cleared\n"
";     (M2.6 blood 3, 3 Nov 2026: CMX bit 7 set = that ink WITHOUT BRIGHT - the dark red corpse stain, blood.asm ds_inkl 0xA0)\n"), (
"        and 15\n        or 0x40                ; sprite ink | BRIGHT\n        call aw_fill\naw_next:\n",
"        and 15                 ; bit 3 (= CMX bit 7) set: not BRIGHT - M2.6 blood 3 corpse stain\n"
"        cp 8\n"
"        jr nc,aw_dim\n"
"        or 0x40                ; sprite ink | BRIGHT\n"
"aw_dim: and 0x47\n"
"        call aw_fill\n"
"aw_next:\n"), (
"; aw_fill: B cells of attribute A down the byte column at HL (row-0 cell, kept) from cell row C; DE = 32.\n"
"aw_fill:\n        push hl\n        inc c\n        dec c\n        jr z,af2\naf1:    add hl,de              ; skip C rows\n"
"        dec c\n        jr nz,af1\naf2:    ld (hl),a\n        add hl,de\n        djnz af2\n        pop hl\n        ret\n"
"at_tint: defb 7                ; window ink of this level (win_tint)\n",
"; aw_fill (B cells of attribute A down the byte column at HL from cell row C; DE = 32) lives in ../common/attrfill.asm since\n"
"; M2.6 blood 3 (3 Nov 2026): 13 B moved into the padding before TEX to pay for the 6 B stain decode above (high block gate).\n"
"at_tint: defb 7                ; window ink of this level (win_tint)\n")],
     must="aw_dim: and 0x47")

# 2. blood.asm: corpse = dim red stain
edit("src/common/blood.asm", [(
"; 0x20 = red while the flash counter is non-zero (counter -= 1), else 0 for a corpse (state 3), else INKTAB.\n",
"; 0x20 = red while the flash counter is non-zero (counter -= 1), else 0xA0 for a corpse (state 3; M2.6 blood 3 \"floor stain\",\n"
"; 3 Nov 2026: red with bit 7 = not BRIGHT, attr.asm - the dead frame lies on the floor, so its cells are a dark red stain where\n"
"; the enemy fell, for the rest of the level), else INKTAB.\n"), (
"        xor a                  ; corpse: no colour (window ink)\ndsi1:   ld (ds_ink),a\n",
"        ld a,0xA0              ; corpse: red, not BRIGHT (CMX bit 7) = the floor stain (M2.6 blood 3)\ndsi1:   ld (ds_ink),a\n")],
     must="ld a,0xA0")

# 7. lowcode.asm comment: CMX bit 7
edit("src/common/lowcode.asm", [(
"; cell row that received white sprite pixels this frame (0 = none) and CMX[2c+1] = ink << 4 | last such cell row + 1.\n",
"; cell row that received white sprite pixels this frame (0 = none) and CMX[2c+1] = ink << 4 | last such cell row + 1.\n"
"; CMX bit 7 (ds_ink 0x80, set with the ink by blood.asm ds_inkl for corpses) = write that ink WITHOUT BRIGHT (M2.6 blood 3 stain).\n")])

# 4. gen48.py: attrfill.asm in the padding before TEX
edit("tools/gen48.py", [(
"         \"dsp_tab:\", \"        defw dda_pp,dda_pn,dda_np,dda_nn\",\n",
"         \"dsp_tab:\", \"        defw dda_pp,dda_pn,dda_np,dda_nn\",\n"
"         '        include \"../common/attrfill.asm\"',                 # M2.6 blood 3: aw_fill (13 B) in the 22 B padding before TEX\n")],
     must='include "../common/attrfill.asm"')

# 5. build gate: af_end <= TEX
edit("tools/build_m25_48.sh", [(
"if (hv%256!=0 || ev>hv) exit 1 }' build/kea48.sym\n",
"if (hv%256!=0 || ev>hv) exit 1 }' build/kea48.sym\n"
"awk '$1==\"TEX\"{t=$3; sub(/H$/,\"\",t); tv=strtonum(\"0x\" t)} $1==\"af_end\"{e=$3; sub(/H$/,\"\",e); ev=strtonum(\"0x\" e)} "
"END{ printf \"TEX 0x%04X (page aligned %s), af_end 0x%04X: attrfill.asm inside the padding = %s\\n\", tv, (tv%256==0)?\"yes\":\"NO\", ev, (ev<=tv)?\"yes\":\"NO\"; "
"if (tv%256!=0 || ev>tv) exit 1 }' build/kea48.sym\n")],
     must="af_end")

# 6. oracle: attribute bytes instead of inks
edit("tools/p2e_oracle.py", [(
"def ink_of(typ, state, hp=0):\n    typ &= 31\n"
"    if typ < 16 and hp & 0xC0: return 2                         # M2.6 blood 1: red flash frames pending (hp bits 6..7)\n"
"    if typ < 16 and state == 3: return 0                        # corpse: window ink\n"
"    return INK.get(typ, 0)\n",
"def ink_of(typ, state, hp=0):\n"
"    \"\"\"-> attribute byte of the cells holding this sprite's white pixels (0 = it colours nothing): ink | BRIGHT, except\n"
"    the blood effects: 0x42 BRIGHT red while a flash is pending, 0x02 red NOT bright for a corpse (M2.6 blood 3 floor stain).\"\"\"\n"
"    typ &= 31\n"
"    if typ < 16 and hp & 0xC0: return 0x42                      # M2.6 blood 1: red flash frames pending (hp bits 6..7)\n"
"    if typ < 16 and state == 3: return 0x02                     # M2.6 blood 3: corpse = dark red stain where it fell\n"
"    ink = INK.get(typ, 0)\n"
"    return ink | 0x40 if ink else 0\n"), (
"    for bc, (f, l, ink) in marks.items():\n        for r in range(f, l + 1): A[r][bc] = ink | 0x40\n",
"    for bc, (f, l, ink) in marks.items():\n        for r in range(f, l + 1): A[r][bc] = ink                # ink_of already carries BRIGHT (or not: stain)\n"), (
"    \"\"\"sprites: far -> near list of (ink, [(ray column, row)] white pixels of that sprite drawn alone).\"\"\"\n",
"    \"\"\"sprites: far -> near list of (attribute byte from ink_of, [(ray column, row)] white pixels of that sprite drawn alone).\"\"\"\n")],
     must="return 0x02")

print("changed:", ", ".join(changed) if changed else "nothing")
