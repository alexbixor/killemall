#!/usr/bin/env python3
"""t6_patch_a.py - T6 integration patch 1 on src/48k/kea48.asm:
 * start: title.scr stays on screen (no cls / title text); mt_outer=2; menu: snd_music 1, fe_run, snd_music 0, cls,
   new_game (stats reset, level 1 resident), hud_init, main.
 * main loop: after game_tick, in_break -> fe_pause (A=0 resume -> hud_redraw, A=1 -> menu).
 * old read_input (direct keyboard; game_a.asm uses in_read) removed.
 * include block: stubs.asm -> input.asm + frontend.asm (grouped includes stay at the end)."""
import pathlib
P = pathlib.Path("src/48k/kea48.asm"); s = P.read_text()
old_start = s[s.index("        call cls\n        call init_game"):s.index("isr:    push hl")]
new_start = """        ld a,2
        ld (mt_outer),a        ; T3 knob: real 2-voice menu tune (the menu frame has the CPU)
menu:   ld sp,65008            ; reached by jp from deep inside the game (level_clear): fresh stack
        ld a,1
        call snd_music         ; menu tune on (honours opt_music)
        call fe_run            ; T2 menu over the title screen; returns when START is chosen
        xor a
        call snd_music
        call cls               ; black screen, white ink
        call new_game
        call apply_opts
        call hud_init
main:   ld hl,(frames)
        inc hl
        ld (frames),hl
        call frame_timer
        call render
        call game_tick
        ld a,(in_break)
        or a
        jp z,main
        call fe_pause          ; BREAK: pause menu over rows 16..23; A = 0 resume, 1 quit to menu
        or a
        jr nz,menu
        call apply_opts
        call hud_redraw        ; the menu used rows 16..23: restore the HUD
        jp main

"""
assert old_start.count("call init_game") == 1
s = s.replace(old_start, new_start)
i0 = s.index("; ---------------------------------------------------------------- input: Q/A/O/P")
i1 = s.index("move_by:")
s = s[:i0] + s[i1:]
assert s.count('        include "../common/stubs.asm"\n') == 1
s = s.replace('        include "../common/stubs.asm"\n', '        include "../common/input.asm"\n        include "../common/frontend.asm"\n')
# fps text only when opt_fps = 1
old = "        ld hl,fps_txt\n        ld de,18593\n        jp print\n"
assert s.count(old) == 1
s = s.replace(old, "        ld a,(opt_fps)\n        or a\n        ret z\n" + old)
# title_txt no longer used
s = s.replace('title_txt:\n        defb "KILL\'EM ALL",0\n', "")
P.write_text(s)
print("patched kea48.asm; lines", s.count("\n"))
