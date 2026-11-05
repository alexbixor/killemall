#!/usr/bin/env python3
"""t1_fix_gb1.py - clean key check in door_try (game_b.asm)."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/game_b.asm"
s = P.read_text()
i0 = s.index("door_try:\n")
i1 = s.index("        ld a,(door_cool)\n")
new = """door_try:
        cp 9
        jr c,door_open         ; 8: unlocked
        cp 11
        jr z,door_open         ; secret wall
        sub 8                  ; 9 -> 1 (red, b0), 10 -> 2 (blue, b1)
        ld c,a
        ld a,(keys)
        and c
        jr nz,door_open
"""
s = s[:i0] + new + s[i1:]
P.write_text(s)
print("ok", len(s.splitlines()))
