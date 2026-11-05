#!/usr/bin/env python3
"""patch_ay1.py - T3: trim ay.asm by a few bytes (player 1539 B -> <= 1536 B)."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent.parent / "src/128k/ay.asm"
s = P.read_text()
# 1. mus_stop: write volumes via a 3-byte ld hl / ld (hl) sequence -> use ldir-free shorter form: ld (ay_regs+8),a etc. is longer;
#    instead reuse: xor a; ld (mus_on),a; ld hl,ay_regs+8; ld (hl),a; inc hl; ld (hl),a; inc hl; ld (hl),a  (already compact)
# 2. dc_inst: 'push hl; inc hl x3; ld (hl),a; pop hl' (7 B) -> 'ld (cs_inst_tmp)...' no; use ex: keep
# 3. sfx_end: drop the explicit R10/mixer clear (mf_env re-writes C the next frame anyway; the SFX's last frame already
#    carried its own volume) - saves 13 bytes but leaves R10 at the SFX's last value for 1 frame. Keep behaviour, trim elsewhere.
# 4. snd_fx1 / mus_n3 pattern: 'ld a,(hl); inc hl; ld h,(hl); ld l,a' fine.
# 5. mus_st: the two 'ld (mus_order),de / ld (mus_opos),de' are needed.
# 6. cs_init copies 36 bytes with ldir: fine.
# Real savings: the ay_regs write loop is unrolled (11 x 10 B = 110 B). Use a 4-register unrolled loop body x 3 (R0..R11) -> 11 writes.
old_a = s.index("        ; ---- write R0..R10 from the shadow block (unrolled: 52 T per register)")
old_b = s.index("        pop hl\n        pop de\n        pop bc\n        pop af\n        ret\n\n; ---------------------------------------------------------------- music: start")
new = """        ; ---- write R0..R10 from the shadow block (R11 too: harmless, keeps the loop 3 x 4 registers)
        ld hl,ay_regs
        ld d,0FFh
        ld e,0
        ld c,0FDh
isr_wr: ld b,d
        out (c),e               ; select register E (port FFFDh)
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a               ; data (port BFFDh)
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld a,e
        cp 12
        jr nz,isr_wr
"""
s = s[:old_a] + new + s[old_b:]
s = s.replace("""ay_regs:
        db 0,0,0,0,0,0,0,03Fh,0,0,0
""", """ay_regs:
        db 0,0,0,0,0,0,0,03Fh,0,0,0,0
""")
P.write_text(s)
print("patched")
