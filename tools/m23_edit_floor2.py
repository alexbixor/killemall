#!/usr/bin/env python3
"""m23_edit_floor2.py - M2.3 fix: an axis whose table delta is 0 (axis-aligned heading) is no movement -> skip the cell
check, the store and the floor phase step (7 B in move_by). Without this, walking face-on into a wall at angle 0/64/128/192
still advanced the floor phase through the zero axis (half-speed flow while standing still)."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
p = ROOT / "src/48k/kea48.asm"; t = p.read_text()
old_x = ("        ld de,MOVXTAB\n        add hl,de\n        ld e,(hl)\n        inc hl\n        ld d,(hl)\n        ld hl,(posx)\n")
new_x = ("        ld de,MOVXTAB\n        add hl,de\n        ld e,(hl)\n        inc hl\n        ld d,(hl)\n        ld a,d\n        or e\n        jr z,mb1               ; M2.3: zero x delta = no x movement (no store, no floor phase step)\n        ld hl,(posx)\n")
old_y = ("        ld de,MOVYTAB\n        add hl,de\n        ld e,(hl)\n        inc hl\n        ld d,(hl)\n        ld hl,(posy)\n")
new_y = ("        ld de,MOVYTAB\n        add hl,de\n        ld e,(hl)\n        inc hl\n        ld d,(hl)\n        ld a,d\n        or e\n        ret z                  ; M2.3: zero y delta = no y movement\n        ld hl,(posy)\n")
for old, new in ((old_x, new_x), (old_y, new_y)):
    if new in t: continue
    if t.count(old) != 1: print("pattern count", t.count(old)); sys.exit(2)
    t = t.replace(old, new, 1)
p.write_text(t); print("edited kea48.asm move_by")