; attrfill.asm - aw_fill of attr.asm (M2.6 P2E), moved here on 3 Nov 2026 for M2.6 blood 3 "floor stain": the 48K high block
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
