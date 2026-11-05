#!/usr/bin/env python3
"""m24_edit_layout.py - M2.4 memory layout: (1) the unused shotgun sprites 16/17 (386 B, weapon_frame only ever selects
14/15) become aliases of 14/15 in the generated low block; (2) sprites_e.asm (draw_sprite + TYPEINK, ~244 B) moves from
the high block into the freed low-block room (included from gen/sprites48.asm after SCHAIN_END); (3) the zbuf index never
crosses a page (DRAM+0x60..+0x9F) - the two page-carry fixups in sprites_f.asm go. Idempotent."""
import pathlib, re
R = pathlib.Path.home() / "work/killemall"

g = R / "tools/gen48.py"; s = g.read_text()
old = ('    for i in range(14, 18):\n'
       '        h, data = spr.get(i, (24, bytes(192)))\n'
       '        s += ["spr_%d:" % i, "        defb %d" % h, db(list(data))]\n'
       '    s += ["SCHAIN:"] + ["        ld a,(de)", "        and c", "        or b", "        ld (de),a", "        inc e"] * 96\n'
       '    s += ["SCHAIN_END:", "        ret"]\n')
new = ('    for i in range(14, 16):                      # M2.4: ids 16/17 (shotgun) are not drawn by any code path (hud_b: 14 + frame 0/1):\n'
       '        h, data = spr.get(i, (24, bytes(192)))   # their 386 B make room for sprites_e.asm in the low block\n'
       '        s += ["spr_%d:" % i, "        defb %d" % h, db(list(data))]\n'
       '    s += ["spr_16  equ spr_14", "spr_17  equ spr_15"]\n'
       '    s += ["SCHAIN:"] + ["        ld a,(de)", "        and c", "        or b", "        ld (de),a", "        inc e"] * 96\n'
       '    s += ["SCHAIN_END:", "        ret",\n'
       '          \'        include "../common/sprites_e.asm"     ; M2.4: draw_sprite + TYPEINK live in the low block\']\n')
if old in s:
    s = s.replace(old, new); g.write_text(s); print("gen48.py: shotgun aliases + sprites_e include")
else:
    assert new in s, "gen48.py: sprite emit block not found"; print("gen48.py: already edited")

k = R / "src/48k/kea48.asm"; s = k.read_text()
old = '        include "../common/sprites_e.asm"\n'
if old in s:
    s = s.replace(old, '; M2.4: sprites_e.asm (draw_sprite, TYPEINK) is included from gen/sprites48.asm (low block)\n')
    k.write_text(s); print("kea48.asm: sprites_e include moved")
else:
    assert "sprites_e.asm (draw_sprite, TYPEINK) is included from gen/sprites48.asm" in s; print("kea48.asm: already edited")

f = R / "src/common/sprites_f.asm"; s = f.read_text()
old1 = ('dc_la1: ld hl,zbuf\n        add a,l\n        ld l,a\n        jr nc,$+3\n        inc h\n')
new1 = ('dc_la1: ld hl,zbuf\n        add a,l\n        ld l,a                 ; zbuf = DRAM+0x60: index 0..63 never crosses the page\n')
old2 = ('dc_l:   ld a,(ds_c)\n        ld hl,zbuf\n        add a,l\n        ld l,a\n        jr nc,$+3\n        inc h\n')
new2 = ('dc_l:   ld a,(ds_c)\n        ld hl,zbuf\n        add a,l\n        ld l,a\n')
n = 0
for o, w in ((old1, new1), (old2, new2)):
    if o in s: s = s.replace(o, w); n += 1
f.write_text(s); print("sprites_f.asm: zbuf page fixups removed:", n)
