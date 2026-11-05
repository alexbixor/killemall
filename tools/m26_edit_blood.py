#!/usr/bin/env python3
"""m26_edit_blood.py - M2.6 blood 1 (red flash) + muzzle flash: idempotent source edits (3 Nov 2026). Run it twice; the second
run must print 'changed: nothing'. Pieces:
 1. src/common/blood.asm (new): ds_inkl moved out of lowcode.asm (the low block had 4 B left) into the alignment padding before
    COLBASE / HTABN (tools/gen48.py, next to floor.asm), now with the flash: thing hp byte bits 6..7 = red frames left,
    decremented once per frame the sprite is drawn, ink BRIGHT red while non-zero (live enemy or corpse alike).
 2. src/common/lowcode.asm: ds_inkl removed (INKTAB, ds_ink, dc_white, dc_mark stay).
 3. tools/gen48.py: include blood.asm right after floor.asm (48K and 128K images both use gen/tables48.asm).
 4. src/common/game_g.asm enemy_hit: hp = bits 0..4; every hit (including the fatal one) sets the counter to 3.
 5. src/common/attr.asm attr_write tail: muzzle flash = window cells (row 9, byte columns 11..12) BRIGHT yellow while
    weapon_frame != 0 (the pistol fire frame, 5 frames per shot).
 6. tools/p2e_oracle.py: ink_of(typ, state, hp) -> red while a flash is pending; expected(..., muzzle); engine_expectation(m, tint, pre).
 7. tools/test_game_enemies.py: thing()['hp'] masked (& 31), 'flash' = bits 6..7."""
import sys, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
changed = []

def edit(rel, pairs, must=None):
    p = ROOT / rel; s = p.read_text(); o = s
    for old, new in pairs:
        if new.startswith(old):                                  # pure insertion after old: undo any doubled insertion
            ins = new[len(old):]
            while ins + ins in s: s = s.replace(ins + ins, ins)
        if new in s: continue                                    # already applied
        if old not in s: sys.exit("%s: anchor not found:\n%s" % (rel, old))
        assert s.count(old) == 1, (rel, old)
        s = s.replace(old, new)
    if must and must not in s: sys.exit("%s: expected text missing: %s" % (rel, must))
    if s != o: p.write_text(s); changed.append(rel)

def put(rel, text):
    p = ROOT / rel
    if p.exists() and p.read_text() == text: return
    p.write_text(text); changed.append(rel)

# 1. blood.asm
put("src/common/blood.asm", r"""; blood.asm - M2.6 blood 1 "red flash" (3 Nov 2026; mock chosen 2 Nov: 'Show me 1 first' -> 'The one on the right looks
; great'). An enemy that was hit (game_g.asm enemy_hit: hp -= 10, the fatal hit included) is drawn BRIGHT red for the next 3
; rendered frames instead of its own colour (imp magenta, zombie green, corpse white). The frame counter lives in the two top
; bits of the thing's hp byte (record +6: hp 0..30 uses bits 0..4; bits 6..7 = frames left, enemy_hit sets 3) and is
; decremented HERE, once per frame the sprite is drawn, so a flash shows exactly 3 drawn frames and costs nothing off screen.
; Placed in the alignment padding before COLBASE / HTABN (tools/gen48.py, like floor.asm): the low block (lowcode.asm) had
; 4 bytes left, so ds_inkl moved here from lowcode.asm (INKTAB and ds_ink stay there; the call in sprites_e.asm is unchanged).
;
; ds_inkl: draw_sprite (sprites_e.asm), HL -> thing record, C = type and 31 (C kept; A, B, DE, HL free there).
; ds_ink = INKTAB[type] (ink << 4; 0 = this sprite colours nothing: barrel, lamp, spare types). Enemies (types < 16):
; 0x20 = red while the flash counter is non-zero (counter -= 1), else 0 for a corpse (state 3), else INKTAB.
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
        xor a                  ; corpse: no colour (window ink)
dsi1:   ld (ds_ink),a
        ret
""")

# 2. lowcode.asm: drop the old ds_inkl (span from its comment to dc_white's comment)
p = ROOT / "src/common/lowcode.asm"; s = p.read_text()
A = "; ds_inkl: draw_sprite (sprites_e.asm)"; B = "; dc_white: sprites_f.asm"
NOTE = ("; ds_inkl (draw_sprite's ink lookup) lives in ../common/blood.asm since M2.6 blood 1 (3 Nov 2026): it grew by 12 bytes\n"
        "; for the red flash and this low block had 4 bytes left. INKTAB and ds_ink below stay here.\n\n")
if A in s:
    i = s.index(A); j = s.index(B, i)
    s = s[:i] + NOTE + s[j:]; p.write_text(s); changed.append("src/common/lowcode.asm")
assert "ds_inkl:" not in s and NOTE in s

# 3. gen48.py: include blood.asm after floor.asm
FLOOR = "         '        include \"../common/floor.asm\"',                    # M2.3: floor lines code+data in the alignment padding\n"
BLOOD = "         '        include \"../common/blood.asm\"',                    # M2.6: ds_inkl + blood 1 red flash, same padding (lowcode.asm is full)\n"
edit("tools/gen48.py", [(FLOOR, FLOOR + BLOOD)])

# 4. enemy_hit
edit("src/common/game_g.asm", [(
"enemy_hit:\n        ld a,(ix+6)\n        sub 10\n        jr c,eh_dead\n        jr z,eh_dead\n        ld (ix+6),a\n",
"enemy_hit:\n        ld a,(ix+6)\n        and 31                 ; M2.6 blood 1: bits 6..7 = red flash frames left (blood.asm ds_inkl)\n"
"        sub 10\n        jr c,eh_dead\n        jr z,eh_dead\n        or 0xC0                ; flash 3 frames\n        ld (ix+6),a\n"), (
"eh_dead:\n        ld (ix+6),0\n",
"eh_dead:\n        ld (ix+6),0xC0         ; hp 0 + flash 3 frames: the corpse flashes red, then turns white\n")])

# 5. muzzle flash at the end of attr_write
edit("src/common/attr.asm", [(
"        pop af\n        dec a\n        jr nz,aw_g\n        ret\n; aw_col:",
"        pop af\n        dec a\n        jr nz,aw_g\n"
"; M2.6 muzzle flash (3 Nov 2026): while the pistol shows its fire frame (weapon_frame = 1 for the 5 frames after a shot) the\n"
"; two window cells at the muzzle = BRIGHT yellow: cell row 9, byte columns 11..12 (the starburst is rows 72..76 of the 32-px\n"
"; gun drawn at byte columns 10..13 - hud_b.asm draw_weapon). Written last, so it wins over sprite and wall cells.\n"
"        ld a,(weapon_frame)\n        or a\n        ret z\n        ld hl,ATTRWIN+9*32+11\n        ld (hl),0x46\n        inc l\n        ld (hl),0x46\n        ret\n"
"; aw_col:")])

# 6. oracle
edit("tools/p2e_oracle.py", [(
"def ink_of(typ, state):\n    typ &= 31\n    if typ < 16 and state == 3: return 0                        # corpse: window ink\n",
"def ink_of(typ, state, hp=0):\n    typ &= 31\n"
"    if typ < 16 and hp & 0xC0: return 2                         # M2.6 blood 1: red flash frames pending (hp bits 6..7)\n"
"    if typ < 16 and state == 3: return 0                        # corpse: window ink\n"), (
"def expected(tint, zbuf, sprites):\n",
"def expected(tint, zbuf, sprites, muzzle=False):\n"), (
"    for bc, (f, l, ink) in marks.items():\n        for r in range(f, l + 1): A[r][bc] = ink | 0x40\n    return A\n",
"    for bc, (f, l, ink) in marks.items():\n        for r in range(f, l + 1): A[r][bc] = ink | 0x40\n"
"    if muzzle: A[9][11] = A[9][12] = 0x46                      # M2.6 muzzle flash: BRIGHT yellow while weapon_frame != 0\n    return A\n"), (
"def engine_expectation(m, tint=None):\n",
"def engine_expectation(m, tint=None, pre=None):\n"), (
"clear the CMIN marks the extra draws left, return the expected matrix.\"\"\"\n",
"clear the CMIN marks the extra draws left, return the expected matrix.\n"
"    pre = the 128-byte things table as it was BEFORE that render (M2.6 blood 1: the flash counter the render consumed); without\n"
"    it the post-render counter is used, which misses the last of the 3 red frames.\"\"\"\n"), (
"        rec = things[8 * idx:8 * idx + 8]\n        ink = ink_of(rec[0], rec[5])\n",
"        rec = things[8 * idx:8 * idx + 8]\n        ink = ink_of(rec[0], rec[5], (pre or things)[8 * idx + 6])\n"), (
"    clear_marks(m)\n    return expected(tint, zbuf, sprites)\n",
"    clear_marks(m)\n    return expected(tint, zbuf, sprites, muzzle=m.memory[SYM[\"weapon_frame\"]] != 0)\n")])

# 7. enemies test: hp without the flash bits
edit("tools/test_game_enemies.py", [(
"state=r[5], hp=r[6], t=r[7])", "state=r[5], hp=r[6] & 31, flash=r[6] >> 6, t=r[7])")])

print("changed:", changed if changed else "nothing (already applied)")
for rel, marker in (("src/common/blood.asm", "ds_inkl:"), ("src/common/lowcode.asm", "blood.asm"), ("tools/gen48.py", "blood.asm"),
                    ("src/common/game_g.asm", "or 0xC0"), ("src/common/attr.asm", "weapon_frame"), ("tools/p2e_oracle.py", "muzzle"),
                    ("tools/test_game_enemies.py", "flash=r[6] >> 6")):
    assert marker in (ROOT / rel).read_text(), (rel, marker)
print("verify: all markers present")
