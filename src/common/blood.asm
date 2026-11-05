; blood.asm - M2.6 blood 1 "red flash" (3 Nov 2026; mock chosen 2 Nov: 'Show me 1 first' -> 'The one on the right looks
; great'). An enemy that was hit (game_g.asm enemy_hit: hp -= 10, the fatal hit included) is drawn BRIGHT red for the next 3
; rendered frames instead of its own colour (imp magenta, zombie green, corpse white). The frame counter lives in the two top
; bits of the thing's hp byte (record +6: hp 0..30 uses bits 0..4; bits 6..7 = frames left, enemy_hit sets 3) and is
; decremented HERE, once per frame the sprite is drawn, so a flash shows exactly 3 drawn frames and costs nothing off screen.
; Placed in the alignment padding before COLBASE / HTABN (tools/gen48.py, like floor.asm): the low block (lowcode.asm) had
; 4 bytes left, so ds_inkl moved here from lowcode.asm (INKTAB and ds_ink stay there; the call in sprites_e.asm is unchanged).
;
; ds_inkl: draw_sprite (sprites_e.asm), HL -> thing record, C = type and 31 (C kept; A, B, DE, HL free there).
; ds_ink = INKTAB[type] (ink << 4; 0 = this sprite colours nothing: barrel, lamp, spare types). Enemies (types < 16):
; 0x20 = red while the flash counter is non-zero (counter -= 1), else 0xA0 for a corpse (state 3; M2.6 blood 3 "floor stain",
; 3 Nov 2026: red with bit 7 = not BRIGHT, attr.asm - the dead frame lies on the floor, so its cells are a dark red stain where
; the enemy fell, for the rest of the level), else INKTAB.
ds_inkl:
        ld b,0
        ex de,hl               ; DE -> thing
        ld hl,INKTAB
        add hl,bc
        ld a,(hl)              ; ink << 4
        bit 4,c
        jr nz,dsi1             ; item / decor: fixed colour
        ld hl,6
        add hl,de              ; HL -> hp | flash frames << 6
        ld b,a
        ld a,(hl)
        sub 0x40
        jr c,dsi0              ; no flash pending (hp < 64)
        ld (hl),a              ; one flash frame used
        ld a,0x20              ; red (attr_write adds BRIGHT)
        jr dsi1
dsi0:   dec hl                 ; HL -> state (0 idle 1 chase 2 attack 3 dead)
        ld a,(hl)
        cp 3
        ld a,b
        jr nz,dsi1
        ld a,0xA0              ; corpse: red, not BRIGHT (CMX bit 7) = the floor stain (M2.6 blood 3)
dsi1:   ld (ds_ink),a
        ret
