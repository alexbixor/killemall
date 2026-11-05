#!/usr/bin/env python3
"""t1_fix_gc1.py - clean near-test in pickups and key-message selection (game_c.asm)."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/game_c.asm"
s = P.read_text()
i0 = s.index("        ld l,(ix+1)\n        ld h,(ix+2)\n        ld de,(posx)")
i1 = s.index("        call pickup_item\n")
new = """        call near_player
        jr nc,pk_next
"""
s = s[:i0] + new + s[i1:]
s = s.replace("pickup_item:\n", """; near_player: IX -> thing; carry set when |dx| < 0.5 and |dy| < 0.5 cell (word + 128 has a zero high byte)
near_player:
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(posx)
        or a
        sbc hl,de
        ld de,128
        add hl,de
        ld a,h
        or a
        ret nz                 ; NC: far
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(posy)
        or a
        sbc hl,de
        ld de,128
        add hl,de
        ld a,h
        or a
        ret nz
        scf
        ret
pickup_item:
""", 1)
old = """pi2:    sub 17                 ; 18 -> 1 red, 19 -> 2 blue
        ld hl,keys
        or (hl)
        ld (hl),a
        ld hl,msg_keyr
        bit 1,a
        jr z,pi_done
        ld hl,msg_keyb
"""
new2 = """pi2:    sub 17                 ; 18 -> 1 red, 19 -> 2 blue
        ld c,a
        ld hl,keys
        or (hl)
        ld (hl),a
        ld hl,msg_keyr
        bit 1,c
        jr z,pi_done
        ld hl,msg_keyb
"""
assert old in s
s = s.replace(old, new2)
P.write_text(s)
print("ok", len(s.splitlines()))
