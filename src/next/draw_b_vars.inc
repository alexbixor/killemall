; draw_b_vars.inc - lane N1D: build-time tier flags for the edition B drawers (src/next/draw_b.asm).
; Include AFTER nx_vars.inc and BEFORE draw_b.asm. Spec docs/next_engine_spec_v0.2_flat.md section 4 (plane tiers).
; Exactly one tier is active: PLANES_FLAT wins over PLANES_LO; both 0 = planes-hi (spec v0.1 section 5 exactly).
; Set from the command line with pasmo --equ PLANES_LO=1 (or PLANES_FLAT=1); the defaults below apply otherwise.
        if defined PLANES_LO
        else
PLANES_LO   equ 0               ; 1 = pixels 2k and 2k+1 of a plane row share the texel of column 2k
        endif
        if defined PLANES_FLAT
        else
PLANES_FLAT equ 0               ; 1 = no plane texture: material*16 + 12 - 3*s (floor material 6 flag, ceiling 7 plaster)
        endif
FLAT_FLOOR_MAT  equ 6           ; manifest.json materials: flag
FLAT_CEIL_MAT   equ 7           ; manifest.json materials: plaster
