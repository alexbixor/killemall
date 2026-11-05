#!/usr/bin/env python3
"""m23_edit_floor.py - M2.3 step 2: wire src/common/floor.asm into the build.
 gen48.py   : CLRBUF gets `ld hl,65535` after the SP step (HL = line word) and the label cl_fl on the first floor push;
              tables48.asm includes ../common/floor.asm between RECIP and the 256-B alignment of HTABN (dead padding).
 kea48.asm  : render calls fl_set before CLRBUF; move_by calls fl_adv after each free-axis position store.
 game_a.asm : B = +19 before the forward move_by, B = -19 before the backward one (fl_adv step per free axis).
 test48.py  : NOTHINGS (walls-only geometry check) also switches the floor lines off (fl_k+1 = 0).
Idempotent: a pair whose new text is already present is skipped; exit 2 if an old pattern is missing."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
def sub(path, pairs):
    p = ROOT / path; t = p.read_text()
    for old, new in pairs:
        if old not in t:
            if new in t: continue
            print("NOT FOUND in %s: %r" % (path, old[:70])); sys.exit(2)
        assert t.count(old) == 1, (path, old[:40], t.count(old))
        t = t.replace(old, new, 1)
    p.write_text(t); print("edited", path)
sub("tools/gen48.py", [
    ('          "        ld a,16", "cl_col: ld hl,65504", "        add hl,sp", "        ld sp,hl"]\n'
     '    s += ["        push de"] * 24 + ["        push bc"] * 24\n',
     '          "        ld a,16", "cl_col: ld hl,65504", "        add hl,sp", "        ld sp,hl",\n'
     '          "        ld hl,65535"]                                  # M2.3: HL = floor line word for the patched pushes\n'
     '    s += ["cl_fl:  push de"] + ["        push de"] * 23 + ["        push bc"] * 24   # M2.3: fl_set patches cl_fl..+23 (D5/E5)\n'),
    ('         "RECIP:", dw(recip),\n         ALIGN256,\n',
     '         "RECIP:", dw(recip),\n'
     '         \'        include "../common/floor.asm"\',                    # M2.3: floor lines code+data in the alignment padding\n'
     '         ALIGN256,\n'),
])
sub("src/48k/kea48.asm", [
    ("rp_y:   call CLRBUF            ; back buffer: ceiling black, floor checker (PUSH fill)\n",
     "rp_y:   call fl_set            ; M2.3: patch the 24 floor pushes of CLRBUF (checker / distance line) for this frame's phase\n"
     "        call CLRBUF            ; back buffer: ceiling black, floor checker + lines (PUSH fill)\n"),
    ("        jr nz,mb1\n        ld (posx),hl\nmb1:    pop hl\n",
     "        jr nz,mb1\n        ld (posx),hl\n        call fl_adv            ; M2.3: floor phase += B (set by game_a: +19 forward, -19 back)\nmb1:    pop hl\n"),
    ("        or a\n        ret nz\n        ld (posy),hl\n        ret\n",
     "        or a\n        ret nz\n        ld (posy),hl\n        jp fl_adv              ; M2.3: second free axis -> phase += B again (38 per tick = 0.15 cell)\n"),
])
sub("src/common/game_a.asm", [
    ("        jr z,gt3\n        ld a,(angle)\n        call move_by\n",
     "        jr z,gt3\n        ld b,19                ; M2.3: floor line phase step per free axis (forward)\n        ld a,(angle)\n        call move_by\n"),
    ("        jr z,gt4\n        ld a,(angle)\n        add a,128\n        call move_by\n",
     "        jr z,gt4\n        ld b,256-19            ; M2.3: backward -> lines flow away\n        ld a,(angle)\n        add a,128\n        call move_by\n"),
])
sub("tools/test48.py", [
    ('    if os.environ.get("NOTHINGS") and "things" in SYM:                       # T1: walls-only geometry check (sprites change the scan)\n',
     '    if os.environ.get("NOTHINGS") and "fl_k" in SYM:\n'
     '        m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))                       # M2.3: floor lines off (chk48 scans the checker)\n'
     '    if os.environ.get("NOTHINGS") and "things" in SYM:                       # T1: walls-only geometry check (sprites change the scan)\n'),
])
print("floor step done")