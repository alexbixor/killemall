#!/usr/bin/env python3
"""m26_edit_p2e.py - Track 2 step 2 (2 Nov 'go', scheme P2E approved 13:13Z): per-cell colour in the 3D window of the REAL build.
Idempotent source edits (re-running changes nothing). Files it writes are hand-written (src/common/lowcode.asm, attr.asm,
tools/p2e_oracle.py, tools/test_p2e.py); this script wires them in:
 1. src/common/state.asm    : CMIN equ DRAM+0x40 (48 B of marks in the DRAM spare ds_rmin/ds_rmax, unused since M2.5)
 2. src/common/sprites.asm  : things_init clears the 48 mark bytes (a new level / new game starts with no marks)
 3. src/common/sprites_e.asm: draw_sprite calls ds_inkl (sprite ink from INKTAB / corpse rule) once per sprite
 4. src/common/sprites_f.asm: dc_vis stores the byte column (dc_bcol); white runs call dc_white; dc_next calls dc_mark
 5. src/48k/kea48.asm       : render = ... COPYBUF then attr_write (jp COPYBUF -> call COPYBUF / jp attr_write); win_tint
                              stores the tint in at_tint; attr.asm included in the high block; lowcode.asm after level_data
 6. tools/build_m25_48.sh   : low_end <= 0x8000 gate
 7. tools/test_one_ink.py, tools/test_tint.py, tools/test_sprite_scale.py: the one-ink / no-attribute-write assertions become
    P2E oracle checks (tools/p2e_oracle.py): the window attributes after render must equal the independent expectation.
usage: .venv/bin/python tools/m26_edit_p2e.py"""
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
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

# 1. marks in the DRAM spare
edit("src/common/state.asm", [(
"ds_rmin     equ DRAM+0x40       ; 16 B, 32-aligned: bit 4 of the address flips between ds_rmin and ds_rmax (dc_mark)\nds_rmax     equ DRAM+0x50       ; 16 B\n",
"CMIN        equ DRAM+0x20       ; M2.6 P2E: 24 x (12 - first marked cell row | 0 = none, ink << 4 | last row + 1) sprite colour\n                                ; marks per byte column (lowcode.asm dc_mark, attr.asm attr_write): 48 B 0x5D20..0x5D4F, one\n                                ; page (ROWTAB holds 25 BYTES, 0x5D00..0x5D18; the old 32 B ds_rmin/ds_rmax slot is inside this range)\n")])

# 2. things_init clears the marks
edit("src/common/sprites.asm", [(
"things_init:\n        ld hl,things\n        ld de,things+1\n        ld bc,NTHINGS*8-1\n        ld (hl),0\n        ldir\n",
"things_init:\n        ld hl,CMIN             ; M2.6 P2E: no sprite colour marks at the start of a level (48 B)\n        ld de,CMIN+1\n        ld bc,47\n        ld (hl),0\n        ldir\n        ld hl,things\n        ld de,things+1\n        ld bc,NTHINGS*8-1\n        ld (hl),0\n        ldir\n")])

# 3. draw_sprite: ink of this sprite
edit("src/common/sprites_e.asm", [(
"        ld de,things\n        add hl,de\n        ld a,(hl)\n        and 31\n        ld c,a\n        ld a,(ds_hv)\n        bit 4,c\n        call z,enemy_h         ; M2.2: enemies 0.8 x (items keep hv)\n",
"        ld de,things\n        add hl,de\n        ld a,(hl)\n        and 31\n        ld c,a\n        call ds_inkl           ; M2.6 P2E: ds_ink = INKTAB[type] << 4 (0 for corpses / decor), HL and C kept (lowcode.asm)\n        ld a,(ds_hv)\n        bit 4,c\n        call z,enemy_h         ; M2.2: enemies 0.8 x (items keep hv)\n")])

# 4. blitter: byte column, white runs, end of ray column
edit("src/common/sprites_f.asm", [(
"        add a,a\n        add a,e\n        add a,(hl)             ; bytecol\n        add a,a\n        add a,COLBASE and 255\n",
"        add a,a\n        add a,e\n        add a,(hl)             ; bytecol\n        ld (dc_bcol),a         ; M2.6 P2E: byte column of this ray column (dc_mark)\n        add a,a\n        add a,COLBASE and 255\n"), (
"        ld a,(dc_code)\n        cp 3\n        jr z,dc_go\n        ld a,b\n        cpl\n        ld c,a                 ; black: and not slot, or 0\n        ld b,0\ndc_go:  call jp_hl\n        jr dc_run_l\njp_hl:  jp (hl)\ndc_next:\n",
"        ld a,(dc_code)\n        cp 3\n        jr z,dc_go\n        ld a,b\n        cpl\n        ld c,a                 ; black: and not slot, or 0\n        ld b,0\ndc_go:  call jp_hl\n        jr dc_run_l\njp_hl:  jp (hl)\ndc_next:\n        ld a,(dc_wlo)\n        inc a\n        call nz,dc_mark        ; M2.6 P2E: this ray column drew white rows -> mark its byte column (lowcode.asm)\n"), (
"        ld b,a                 ; B = n rows\n        ld hl,(dc_buf)\n        ld a,l\n        add a,c\n        ld l,a\n",
"        ld b,a                 ; B = n rows\n        ld a,(dc_code)\n        cp 3\n        call z,dc_white        ; M2.6 P2E: white run of B rows from row C -> dc_wlo / dc_whi (lowcode.asm, B C HL DE kept)\n        ld hl,(dc_buf)\n        ld a,l\n        add a,c\n        ld l,a\n")])

# 5. kea48.asm: render tail, win_tint, includes
edit("src/48k/kea48.asm", [(
"        call draw_things       ; T1: scaled masked sprites with zbuf depth test (M2.5: masked blit, no attributes)\n        jp COPYBUF             ; one burst copy of the back buffer to the screen window (ends with ret)\n",
"        call draw_things       ; T1: scaled masked sprites with zbuf depth test (M2.5: masked blit, no attributes)\n        call COPYBUF           ; one burst copy of the back buffer to the screen window\n        jp attr_write          ; M2.6 P2E: window attributes from zbuf + sprite marks (attr.asm, ends with ret)\n"), (
"        ld a,(hl)              ; ink 0..7, paper black, no bright\n        ld hl,ATTRWIN\n        ld c,12\n",
"        ld a,(hl)              ; ink 0..7, paper black, no bright\n        ld (at_tint),a         ; M2.6 P2E: attr_write repaints the window from this tint every frame (attr.asm)\nwt_fill:\n        ld hl,ATTRWIN\n        ld c,12\n"), (
"        include \"../common/hud_b.asm\"\n; T1: gen/sprites48.asm begins with \"org 27904\" -> sprites, SCHAIN, NCTAB/STEPTAB/VSTEP, SPG page and level_data load low (27904..32767)\nhi_end  equ $\n        include \"gen/sprites48.asm\"\nlevel_data:\n        incbin \"gen/level48.bin\"   ; low block (ends below 32768; Z80-core test harnesses live in page 0x6A)\n        org hi_end\n",
"        include \"../common/hud_b.asm\"\n        include \"../common/attr.asm\"           ; M2.6 P2E: per-frame window attribute writer\n; T1: gen/sprites48.asm begins with \"org 27904\" -> sprites, SCHAIN, NCTAB/STEPTAB/VSTEP, SPG page and level_data load low (27904..32767)\nhi_end  equ $\n        include \"gen/sprites48.asm\"\nlevel_data:\n        incbin \"gen/level48.bin\"   ; low block (ends below 32768; Z80-core test harnesses live in page 0x6A)\n        include \"../common/lowcode.asm\"        ; M2.6 P2E: sprite colour marks, in the free tail of the low block (low_end <= 0x8000)\n        org hi_end\n")])

# 6. build gate
edit("tools/build_m25_48.sh", [(
"""awk '$1=="level_data"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "level_data 0x%04X + 1081 = 0x%04X, free below 0x8000: %d B\\n", v, v+1081, 32768-(v+1081); if (32768-(v+1081) < 0) { print "LOW BLOCK OVERFLOWS 0x8000"; exit 1 } }' build/kea48.sym\n""",
"""awk '$1=="level_data"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "level_data 0x%04X + 1081 = 0x%04X, free below 0x8000: %d B\\n", v, v+1081, 32768-(v+1081); if (32768-(v+1081) < 0) { print "LOW BLOCK OVERFLOWS 0x8000"; exit 1 } }' build/kea48.sym
awk '$1=="low_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "low_end 0x%04X (lowcode.asm after level_data), free below 0x8000: %d B\\n", v, 32768-v; if (32768-v < 0) { print "LOW BLOCK (lowcode) OVERFLOWS 0x8000"; exit 1 } }' build/kea48.sym\n""")])

# 7a. test_one_ink: the window must equal the P2E expectation (not all 0x07); poison test -> repaint test
edit("tools/test_one_ink.py", [(
" (a) ONE INK: after render with 0, 1 and 2 sprites at several distances and in front of every wall texture, all 12 x 16\n     window attribute cells are 0x07 (white ink, black paper, no bright, no flash) -> no attribute can clash, ever.\n",
" (a) P2E (M2.6): after render with 0, 1 and 2 sprites at several distances and in front of every wall texture, the 12 x 24\n     window attribute cells equal tools/p2e_oracle.py's expectation: tint everywhere, tint | BRIGHT on near-wall cells, sprite\n     ink | BRIGHT exactly on the cells holding a coloured sprite's white pixels (nearest sprite wins) -> nothing can clash.\n"), (
"from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR\n",
"from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR\nfrom p2e_oracle import engine_expectation, diff        # M2.6 P2E: per-cell expectation from zbuf + sprites drawn alone\n"), (
"        call(m, \"render\")\n        a = attrs(m)\n        bad = [(bc, r) for r in range(12) for bc in range(24) if a[r][bc] != 7]\n        nvis = m.memory[SYM[\"nvis\"]]\n        print(\"%-24s nvis %d | attr cells != 0x07: %d\" % (name, nvis, len(bad)))\n",
"        call(m, \"render\")\n        a = attrs(m)\n        bad = diff(a, engine_expectation(m))                 # M2.6 P2E: cells that differ from the independent expectation\n        nvis = m.memory[SYM[\"nvis\"]]\n        print(\"%-24s nvis %d | attr cells != P2E expectation: %d\" % (name, nvis, len(bad)))\n"), (
"        set_thing(m, 0, 2, 5.5, 7.5); call(m, \"render\"); a = attrs(m)\n        bad = [(bc, r) for r in range(12) for bc in range(24) if a[r][bc] != 7]\n        if bad: print(\"   FAIL wall code %d: attr cells != 0x07 %s\" % (code, bad[:6])); fails += 1\n",
"        set_thing(m, 0, 2, 5.5, 7.5); call(m, \"render\"); a = attrs(m)\n        bad = diff(a, engine_expectation(m))\n        if bad: print(\"   FAIL wall code %d: attr cells != P2E expectation %s\" % (code, bad[:6])); fails += 1\n"), (
"    poisoned = all(m.memory[ATTRWIN + 32 * r + c] == 0x55 for r in range(12) for c in range(24))\n    print(\"render never writes the window attributes (poison test):\", poisoned)\n    if not poisoned: fails += 1\n",
"    poisoned = not diff(attrs(m), engine_expectation(m))     # M2.6 P2E: render repaints every window cell each frame\n    print(\"render repaints all 288 window cells from the tint + marks (poison test):\", poisoned)\n    if not poisoned: fails += 1\n")])

# 7b. test_tint: after render the window equals the P2E expectation for that tint
edit("tools/test_tint.py", [(
"from test_game_sprites import machine, call, set_player, clear_things, set_thing\n",
"from test_game_sprites import machine, call, set_player, clear_things, set_thing\nfrom p2e_oracle import engine_expectation        # M2.6 P2E\n"), (
"        w2 = win(m); bad2 = [i for i, v in enumerate(w2) if v != want]\n",
"        exp = engine_expectation(m, want); w2 = win(m); bad2 = [i for i, v in enumerate(w2) if v != exp[i // 24][i % 24]]   # M2.6 P2E\n")])

# 7c. test_sprite_scale: the sprite changes exactly the cells the P2E oracle predicts
# 7c-pre (3 Nov): the 2 Nov run of this script imported without clear_marks -> upgrade that line in place (no-op otherwise)
_p = ROOT / "tools/test_sprite_scale.py"; _s = _p.read_text()
_old_imp = "from p2e_oracle import engine_expectation, diff        # M2.6 P2E\n"
_new_imp = "from p2e_oracle import engine_expectation, diff, clear_marks        # M2.6 P2E\n"
if _old_imp in _s: _p.write_text(_s.replace(_old_imp, _new_imp)); changed.append("tools/test_sprite_scale.py")
edit("tools/test_sprite_scale.py", [(
"from test_game_doors import fake_input\n",
"from test_game_doors import fake_input\n" + _new_imp), (
# 3 Nov: silhouette() calls draw_things OUTSIDE render, so the CMIN marks it leaves are never consumed; the next render's
# attr_write would paint them (walls-only reference frame of (e) carried the imp's 58 magenta cells -> 'attr changed' FAIL
# with 0 changed pixels). In the game draw_things only runs inside render (kea48.asm), right before attr_write.
'    m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)\n    c1, p1 = changed_columns(bytes(N), white)\n',
'    m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)\n    clear_marks(m)                                     # M2.6 P2E: draw_things outside render leaves CMIN marks; attr_write would paint them next frame\n    c1, p1 = changed_columns(bytes(N), white)\n'), (
"            at = attrs(m)\n            bad = [(bc, r) for r in range(12) for bc in range(24) if at[r][bc] != a0[r][bc]]\n            if bad:\n                print(\"      attr FAIL: window cells changed by the sprite %s\" % bad[:6]); fails += 1\n",
"            at = attrs(m)\n            bad = diff(at, engine_expectation(m))             # M2.6 P2E: cells = tint / near-wall BRIGHT / sprite ink\n            if bad:\n                print(\"      attr FAIL: window cells != P2E expectation %s\" % bad[:6]); fails += 1\n")])

print("changed:", changed if changed else "nothing (already applied)")
for rel, marker in (("src/common/state.asm", "CMIN        equ DRAM+0x20"), ("src/common/sprites.asm", "ld hl,CMIN"),
                    ("src/common/sprites_e.asm", "call ds_inkl"), ("src/common/sprites_f.asm", "call nz,dc_mark"),
                    ("src/common/sprites_f.asm", "call z,dc_white"), ("src/48k/kea48.asm", "jp attr_write"),
                    ("src/48k/kea48.asm", "wt_fill:"), ("src/48k/kea48.asm", 'include "../common/lowcode.asm"'),
                    ("tools/build_m25_48.sh", "low_end"), ("tools/test_one_ink.py", "engine_expectation"),
                    ("tools/test_tint.py", "engine_expectation"), ("tools/test_sprite_scale.py", "engine_expectation")):
    assert marker in (ROOT / rel).read_text(), (rel, marker)
print("verify: all markers present")
