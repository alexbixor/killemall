; fe_stubs.asm - T2 local stand-ins for T3 (snd_fx, snd_menu_tick) and T1 (hud_message). Same labels/contracts as
; ARCH_M2.md; they only count calls so tools/test_frontend.py can assert "snd_fx 6 on every move/toggle" and
; "snd_menu_tick every frame". Replaced by the real beeper.asm / hud.asm at integration.
snd_fx:
        ld (stub_fx_last),a
        ld hl,stub_fx_count
        inc (hl)
        ret
snd_menu_tick:
        ld hl,stub_tick_count
        inc (hl)
        ret
hud_message:
        ld (stub_msg),hl
        ret
stub_fx_last:   defb 0
stub_fx_count:  defb 0
stub_tick_count: defb 0
stub_msg:       defw 0
