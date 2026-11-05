#!/usr/bin/env python3
"""t6_patch_b.py - T6 integration patch 2: new_game / apply_opts / hud_redraw / load_level in kea48.asm (own section
before isr), game_d.asm level_clear -> next level from tape (NLEVELS) or back to the menu."""
import pathlib
P = pathlib.Path("src/48k/kea48.asm"); s = P.read_text()
anchor = "isr:    push hl"
new = """; ---------------------------------------------------------------- T6: game start, options, pause HUD restore, tape levels
new_game:                      ; stats reset + level 1 (resident copy restored from tape only if a later level overwrote it)
        ld a,100
        ld (health),a
        ld a,50
        ld (ammo),a
        xor a
        ld (keys),a
        ld (kills),a
        ld (level),a
        ld (door_cool),a
        call doors_restore
        ld a,(level_data)
        cp 1
        jr z,ng1
        ld a,1
        call load_level        ; level 1 was overwritten by level 2/3: fetch it again from tape
ng1:    jp init_game
apply_opts:                    ; opt_detail 0 -> plain floor (CLRBUF fill 0x0000), 1 -> dithered 0x55AA
        ld hl,0x55AA
        ld a,(opt_detail)
        or a
        jr nz,ao1
        ld h,a
        ld l,a
ao1:    ld (cl_de+1),hl
        ret
hud_redraw:
        call fe_clr_bottom     ; the menu used pixel rows 128..191 / attr rows 16..23
        jp hud_init
NLEVELS equ 3
LDBYTES equ 0x0556             ; ROM loader: IX = dest, DE = length, A = flag, carry = load
; load_level: A = wanted level id (1..3) -> loads 1063-byte blocks (flag 0xFF) from tape into level_data until one whose
; byte 0 is the wanted id arrives (level_data is the only RAM touched). ROM loader runs with DI; returns with EI.
load_level:
        ld (ll_want),a
        ld hl,msg_tape
        call hud_message
        call hud_update
ll_wait:call in_scan
        jr nz,ll_wait          ; every key up (the ROM loader aborts on BREAK)
ll_try: ld ix,level_data
        ld de,1063
        ld a,0xFF
        scf
        call LDBYTES
        push af
        xor a
        out (254),a            ; border black again
        pop af
        jr nc,ll_try
        ld a,(level_data)
        ld hl,ll_want
        cp (hl)
        jr nz,ll_try
        ret
ll_want: defb 0
msg_tape: defb "LOADING NEXT LEVEL",0

"""
assert s.count(anchor) == 1
s = s.replace(anchor, new + anchor)
P.write_text(s)
G = pathlib.Path("src/common/game_d.asm"); g = G.read_text()
old = g[g.index("        ld hl,level\n        inc (hl)"):g.index("player_dead:")]
new = """        ld hl,level
        inc (hl)
        ld a,(hl)
        cp NLEVELS             ; T6: levels 2..3 come from tape (kea48.asm load_level)
        jr c,lc_next
        jp menu                ; T6: all levels cleared -> title menu (menu resets SP)
lc_next:
        inc a                  ; level id 1..3 = level + 1
        call load_level
        jp restart_level
"""
G.write_text(g.replace(old, new))
print("patched kea48.asm + game_d.asm")
