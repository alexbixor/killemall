#!/usr/bin/env python3
"""t6_patch_c.py - gen48.py: label the CLRBUF floor-fill constant (cl_de) so apply_opts can switch the floor dither
(opt_detail); kea48.asm: menu background when returning from the game (clear rows 13..15, print the name)."""
import pathlib
G = pathlib.Path("tools/gen48.py"); g = G.read_text()
old = '"        ld de,%d" % (0x55 * 256 + 0xAA)'
assert g.count(old) == 1
G.write_text(g.replace(old, '"cl_de:  ld de,%d" % (0x55 * 256 + 0xAA)'))
P = pathlib.Path("src/48k/kea48.asm"); s = P.read_text()
old = """hud_redraw:
        call fe_clr_bottom     ; the menu used pixel rows 128..191 / attr rows 16..23
        jp hud_init
"""
new = """hud_redraw:
        call fe_clr_bottom     ; the menu used pixel rows 128..191 / attr rows 16..23
        call clr_rows13        ; stale fps line / message (rows 13..15)
        jp hud_init
clr_rows13:                    ; pixel rows 104..127 (text rows 13..15) = 0
        ld hl,0x48A0
        ld a,8
cr13:   push hl
        ld d,h
        ld e,l
        inc de
        ld (hl),0
        ld bc,95
        ldir
        pop hl
        inc h
        dec a
        jr nz,cr13
        ret
menu_bg:                       ; back from the game: the frozen 3D view stays, rows 13..15 show the name
        call clr_rows13
        ld hl,name_txt
        ld de,18624+10         ; row 14, column 10
        jp print
name_txt: defb "KILL'EM ALL",0
"""
assert s.count(old) == 1
s = s.replace(old, new)
old = """        call fe_pause          ; BREAK: pause menu over rows 16..23; A = 0 resume, 1 quit to menu
        or a
        jr nz,menu
"""
new = """        call fe_pause          ; BREAK: pause menu over rows 16..23; A = 0 resume, 1 quit to menu
        or a
        jr z,resume
menu2:  call menu_bg
        jp menu
resume:
"""
assert s.count(old) == 1
s = s.replace(old, new)
# level_clear's return to the menu goes through menu2 (clears the HUD text rows first)
D = pathlib.Path("src/common/game_d.asm"); d = D.read_text()
old = "        jp menu                ; T6: all levels cleared -> title menu (menu resets SP)\n"
assert d.count(old) == 1
D.write_text(d.replace(old, "        jp menu2               ; T6: all levels cleared -> menu over the frozen view (menu resets SP)\n"))
P.write_text(s)
print("patched gen48.py, kea48.asm, game_d.asm")
