#!/usr/bin/env python3
"""t1_fix_f1.py - rewrite the run blit (dc_run_l .. dc_next) in sprites_f.asm cleanly."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "src/common/sprites_f.asm"
s = P.read_text()
i0 = s.index("dc_run_l:\n")
i1 = s.index("dc_next:\n")
new = """dc_run_l:
        ld hl,(dc_run)
        ld a,(hl)
        or a
        jr z,dc_next
        inc hl
        ld (dc_run),hl
        ld c,a
        and 7
        ld (dc_code),a         ; 0 transparent, 1 black, 3 white
        ld a,c
        rrca
        rrca
        rrca
        and 31                 ; v_end (1..24)
        ld c,a
        ld hl,dc_v0
        ld l,(hl)              ; L = v0
        ld (dc_v0),a           ; next run starts at v_end
        ld a,(dc_code)
        or a
        jr z,dc_run_l          ; transparent run
        ld h,ROWTAB/256
        ld a,(hl)              ; r0 = ROWTAB[v0]
        ld l,c
        ld b,(hl)              ; r1 = ROWTAB[v_end]
        ld c,a
        ld a,b
        sub c
        jr z,dc_run_l          ; no rows
        ld hl,(dc_buf)
        ld l,c
        ex de,hl               ; DE = BUF column + r0
        add a,a
        add a,CHJ and 255
        ld l,a
        ld h,CHJ/256           ; HL -> CHJ[n]
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                 ; HL = chain entry (n rows)
        ld a,(dc_slot)
        ld b,a                 ; B = slot bits (or), C = 255: white
        ld c,255
        ld a,(dc_code)
        cp 3
        jr z,dc_go
        ld a,b
        cpl
        ld c,a                 ; black: and not slot, or 0
        ld b,0
dc_go:  call jp_hl
        jr dc_run_l
jp_hl:  jp (hl)
"""
s = s[:i0] + new + s[i1:]
s = s.replace("dc_v0:  defb 0\n", "dc_v0:  defb 0\ndc_code: defb 0\n")
P.write_text(s)
print("ok", len(s.splitlines()))
