#!/usr/bin/env python3
"""m28_edit_strafe.py - M2.8 fix "strafe is not working" (user 3 Nov 2026 ~17:00Z, playing the pushed M2.6 build on the Deck).
Diagnosis (tools/m28_strafe_probe.py on the real 48K tape): in_read returns b6 (Z) / b7 (X) correctly - in_bits 0x40 / 0x80 while
held - but game_tick (src/common/game_a.asm) never looked at bits 6/7: strafe was 'optional' in ARCH_M2.md and was never wired.
Fix: a 10-byte helper `strafe` (A = heading offset) = move_by with the heading rotated a quarter turn and B = 0 (fl_ph counts
forward distance only; a sideways slide leaves the floor/ceiling line phase alone). Direction convention: turn-right (P) is
angle + 6, so the player's right-hand side is heading + 64 and the left-hand side heading - 64 (= + 192); verified by
tools/m28_strafe_check.py (an imp placed on the screen's left comes closer when Z is held).
Idempotent (run twice -> 'changed: nothing'); v2 of this script (strafe block inside the back-key branch, so it only ran while
walking backwards - found by tools/m28_strafe_dbg.py) is reverted if present. The block has its own label gt3s.
Cost: +30 B high block; the YOU DIED / LEVEL CLEARED strings (23 B) move to the low block (lowcode.asm, 32 B free) so the
48K high block stays above the 40 B gate (49 -> 42 B)."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
changed = []

def edit(rel, pairs, must=None):
    p = ROOT / rel; s = p.read_text(); o = s
    for old, new in pairs:
        if new in s: continue
        if old not in s: sys.exit("%s: anchor not found:\n%s" % (rel, old))
        assert s.count(old) == 1, (rel, old)
        s = s.replace(old, new)
    if must and must not in s: sys.exit("%s: expected text missing: %s" % (rel, must))
    if s != o: p.write_text(s); changed.append(rel)

ORIG = """        bit 1,a
        jr z,gt4
        ld b,256-38            ; M2.3: backward -> lines flow away
        ld a,(angle)
        add a,128
        call move_by
gt4:    ld a,(in_bits)
"""
V1 = """        ld b,256-38            ; M2.3: backward -> lines flow away
        ld a,(angle)
        add a,128
        call move_by
gt3b:   ld a,(in_bits)         ; M2.8 (3 Nov 2026): strafe. Z = b6 slides left = heading + 64 (quarter turn; turn-left is
        bit 6,a                ; angle - 6, so left = +), X = b7 slides right = heading - 64. B = 0: fl_ph counts forward
        jr z,gt3c              ; distance only, a sideways slide leaves the floor/ceiling line phase alone.
        ld b,0
        ld a,(angle)
        add a,64
        call move_by
gt3c:   ld a,(in_bits)
        bit 7,a
        jr z,gt4
        ld b,0
        ld a,(angle)
        add a,256-64
        call move_by
gt4:    ld a,(in_bits)
"""
V2 = """        bit 1,a
        jr z,gt4
        ld b,256-38            ; M2.3: backward -> lines flow away
        ld a,(angle)
        add a,128
        call move_by
        ld a,(in_bits)         ; M2.8 (3 Nov 2026): strafe. Z = b6 slides left = heading - 64 (turn-right P is angle + 6,
        bit 6,a                ; so the right-hand side is + 64 and the left-hand side - 64 = + 192), X = b7 slides right.
        ld a,256-64            ; (ld does not touch the Z flag of the bit test)
        call nz,strafe
        ld a,(in_bits)
        bit 7,a
        ld a,64
        call nz,strafe
gt4:    ld a,(in_bits)
"""
V3 = """        bit 1,a
        jr z,gt3s
        ld b,256-38            ; M2.3: backward -> lines flow away
        ld a,(angle)
        add a,128
        call move_by
gt3s:   ld a,(in_bits)         ; M2.8 (3 Nov 2026): strafe. Z = b6 slides left = heading - 64 (turn-right P is angle + 6,
        bit 6,a                ; so the right-hand side is + 64 and the left-hand side - 64 = + 192), X = b7 slides right.
        ld a,256-64            ; (ld does not touch the Z flag of the bit test)
        call nz,strafe
        ld a,(in_bits)
        bit 7,a
        ld a,64
        call nz,strafe
gt4:    ld a,(in_bits)
"""
STRAFE = """in_bits: defb 0
; M2.8 strafe: A = heading offset (64 right / 192 left) -> move_by along angle + A with B = 0: fl_ph counts forward distance
; only, so a sideways slide leaves the floor/ceiling line phase alone. 10 B.
strafe: ld b,0
        ld c,a
        ld a,(angle)
        add a,c
        jp move_by
"""
# 0. revert v2 if present (v2 bug: strafe block inside the back-key branch), then 1. apply v3 + the helper after in_bits
edit("src/common/game_a.asm", [(V2, ORIG)]) if V2 in (ROOT / "src/common/game_a.asm").read_text() else None
edit("src/common/game_a.asm", [(ORIG, V3), ("in_bits: defb 0\n", STRAFE)], must="gt3s:   ld a,(in_bits)")
edit("src/common/game_a.asm", [(
"; game_a.asm (T1) - game tick: input via in_read contract (b0 fwd b1 back b2 left b3 right b4 fire b5 use), movement.",
"; game_a.asm (T1) - game tick: input via in_read contract (b0 fwd b1 back b2 left b3 right b4 fire b5 use b6/b7 strafe L/R), movement.")])
# 2. the two message strings move from game_d.asm (high block) to lowcode.asm (low block tail): -23 B high, +23 B low
edit("src/common/game_d.asm", [(
"""wf_ret: ret
msg_clear: defb "LEVEL CLEARED",0
msg_dead:  defb "YOU DIED",0
""",
"""wf_ret: ret
; msg_clear / msg_dead live in ../common/lowcode.asm since M2.8 (3 Nov 2026): 23 B moved out of the high block to pay for strafe.
""")])
edit("src/common/lowcode.asm", [(
"""dc_whi:  defb 0                ; end row (exclusive) of the last white run in this ray column
low_end equ $                  ; must stay <= 0x8000 (build gate)""",
"""dc_whi:  defb 0                ; end row (exclusive) of the last white run in this ray column
msg_clear: defb "LEVEL CLEARED",0   ; M2.8 (3 Nov 2026): hud_message strings of game_d.asm, moved here (23 B) to pay for strafe
msg_dead:  defb "YOU DIED",0
low_end equ $                  ; must stay <= 0x8000 (build gate)""")], must='msg_dead:  defb "YOU DIED",0\nlow_end')
print("changed:", ", ".join(changed) if changed else "nothing")
