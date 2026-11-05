; fe_integ_check.asm - T2 integration smoke: assemble state.asm + input.asm + frontend.asm together with T3's real
; beeper.asm and T1's stubs.asm minus the labels T2/T3 now provide (checks for duplicate labels / missing externals only;
; the result is not run). Built by tools/fe_build.sh into build/fe_integ.bin.
        org 32768
hud_message: ret
ticks:  defw 0
        include "src/common/state.asm"
        include "src/common/input.asm"
        include "src/common/frontend.asm"
        include "src/common/beeper.asm"
