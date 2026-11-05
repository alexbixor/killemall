#!/usr/bin/env python3
"""m25_edit_tint.py - M2.5 per-level window tint (user 30 Oct: "yes add the tint"). Idempotent source edit of src/48k/kea48.asm:
init_game starts with `call win_tint`, which writes TINTTAB[level] (ink on black paper, non-bright) into the 12 x 16 window
attribute cells (rows 1..12, cols 8..23). render never writes attributes (test_one_ink.py), so the tint is one write per level
start / restart. HUD cells (frame cols 7 and 24, rows 13..23) are not touched. The 128K build inherits it via make128.py."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "src/48k/kea48.asm"
s = P.read_text()
if "win_tint" in s:
    print("kea48.asm: tint already applied"); sys.exit(0)
a1 = "init_game:\n        ld hl,SOLIDPG*256      ; M2.2: solid texture page"
assert s.count(a1) == 1, "anchor init_game"
s = s.replace(a1, "init_game:\n        call win_tint          ; M2.5: window ink for this level (TINTTAB) into the 12x16 ATTRWIN cells; render never writes attributes\n"
              "        ld hl,SOLIDPG*256      ; M2.2: solid texture page")
a2 = "        jp things_init\n\n; A = x int, C = y int -> HL = map pointer / A = cell code\n"
assert s.count(a2) == 1, "anchor things_init"
tint = """        jp things_init

; M2.5 win_tint: the whole 3D window has ONE ink (zero attribute clash); it is chosen per level from TINTTAB and written once
; into the window attribute cells (12 rows x 16 cells, rows 1..12 cols 8..23). Frame cells (cols 7 / 24) and the HUD stay as they are.
win_tint:
        ld hl,TINTTAB
        ld a,(level)           ; 0-based; and 3 keeps a stale value inside the 4-entry table
        and 3
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld a,(hl)              ; ink 0..7, paper black, no bright
        ld hl,ATTRWIN
        ld c,12
wt1:    ld b,16
wt2:    ld (hl),a
        inc l                  ; 16 cells of one row never cross a page (row low byte 0x28/0x48/../0xE8/0x08..)
        djnz wt2
        ld de,16               ; +32 per row: 16 done by inc l, 16 here
        add hl,de
        dec c
        jr nz,wt1
        ret
TINTTAB: defb 7,5,6,7          ; level 1 Entry white, 2 Barracks cyan, 3 Furnace yellow, (spare) white

; A = x int, C = y int -> HL = map pointer / A = cell code
"""
s = s.replace(a2, tint)
P.write_text(s)
print("kea48.asm: win_tint + TINTTAB added, init_game calls it")
