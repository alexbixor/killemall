#!/usr/bin/env python3
"""m23_edit_floor3.py - M2.3 rule: the floor phase advances ONCE per tick when the player actually moved (first stored axis
adds B = +-38 = 0.15 cell, then B := 0 so a second stored axis adds nothing). Axis-aligned headings (one zero delta) now
flow at full speed; standing against a wall does not flow. Also fixes the test: PUSH DE with DE = 0x55AA stores E (0xAA)
at the lower address = even row, D (0x55) at the odd row -> checker word is (0xAA, 0x55); flow tests start from phase 8
(no wrap) and track the nearest line = max word (never hidden by the far wall)."""
import pathlib, sys
ROOT = pathlib.Path.home() / "work/killemall"
def sub(path, pairs):
    p = ROOT / path; t = p.read_text()
    for old, new in pairs:
        if new in t: continue
        if t.count(old) != 1: print("count", t.count(old), path, old[:60]); sys.exit(2)
        t = t.replace(old, new, 1)
    p.write_text(t); print("edited", path)
sub("src/48k/kea48.asm", [
    ("        ld (posx),hl\n        call fl_adv            ; M2.3: floor phase += B (set by game_a: +19 forward, -19 back)\nmb1:    pop hl\n",
     "        ld (posx),hl\n        call fl_adv            ; M2.3: floor phase += B (game_a: +38 forward, -38 back = 0.15 cell)\n        ld b,0                 ; once per tick: a second stored axis adds nothing\nmb1:    pop hl\n"),
    ("        jp fl_adv              ; M2.3: second free axis -> phase += B again (38 per tick = 0.15 cell)\n",
     "        jp fl_adv              ; M2.3: phase += B (38 if x did not move, 0 if it did)\n"),
])
sub("src/common/game_a.asm", [
    ("        ld b,19                ; M2.3: floor line phase step per free axis (forward)\n",
     "        ld b,38                ; M2.3: floor line phase step when the move lands (0.15 cell = 38/256), forward\n"),
    ("        ld b,256-19            ; M2.3: backward -> lines flow away\n",
     "        ld b,256-38            ; M2.3: backward -> lines flow away\n"),
])
sub("src/common/floor.asm", [
    ("; perpendicular distance = parallel to the camera plane). fl_ph is advanced by move_by (kea48.asm) via fl_adv with\n"
     "; B = +19 / -19 per free axis (game_a.asm) = +-38 per tick ~ 0.15 cell. Cost: fl_set ~3.5k T per frame (~1%).\n",
     "; perpendicular distance = parallel to the camera plane). fl_ph is advanced by move_by (kea48.asm) via fl_adv with\n"
     "; B = +38 / -38 (game_a.asm) once per tick in which the player actually moved (0.15 cell); a zero-delta axis or a\n"
     "; blocked axis adds nothing, so standing against a wall does not flow. Cost: fl_set 2,880 T per frame (<1%).\n"),
    ("fl_adv: ld a,(fl_ph)           ; B = signed half step; called by move_by after each free axis store\n",
     "fl_adv: ld a,(fl_ph)           ; B = signed step (38 / -38 / 0); called by move_by after each stored axis\n"),
])
sub("tools/test_floor_lines.py", [
    (' (b) walking forward (game_tick with bit 0) advances fl_ph by 38 per tick in open space (2 free axes) and the nearest line\n',
     ' (b) walking forward (game_tick with bit 0) advances fl_ph by 38 per tick (0.15 cell, once per moving tick) and the nearest line\n'),
    ("def floor_words(m, bytecol):\n", "CHK = (0xAA, 0x55)            # push de, DE = 0x55AA: E lands on the even (lower) row, D on the odd row\ndef floor_words(m, bytecol):\n"),
    ("        pure = sum(1 for lo, hi in ws if (lo, hi) in ((0x55, 0xAA), (0xAA, 0x55), (0xFF, 0xFF), (0, 0))) + w0(m, bc)\n",
     "        pure = sum(1 for lo, hi in ws if (lo, hi) in (CHK, (0xFF, 0xFF), (0, 0))) + w0(m, bc)\n"),
    ("    others_ok = all((lo, hi) == (0x55, 0xAA) for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None\n",
     "    others_ok = all((lo, hi) == CHK for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None\n"),
    ('check(ph1 == 38, "(b) forward tick in open space: fl_ph 0 -> %d (38 = 2 axes x 19)" % ph1)\n',
     'check(ph1 == 38, "(b) forward tick in open space: fl_ph 0 -> %d (38 = 0.15 cell, once per tick)" % ph1)\n'),
    ("# advance until the nearest line jumps: it must move to a larger word index (down the screen = toward the player)\n"
     "moved = None\nfor _ in range(6):\n    call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc)\n    if l[0] != l0[0]: moved = l[0] - l0[0]; break\n",
     "# from phase 8 (no wrap): the nearest line (lowest on screen = max word) must move to a larger word (down = toward the player)\n"
     "set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM[\"fl_ph\"], bytes([128])); call(m, \"render\"); l0 = line_words(m, bc)\n"
     "call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); moved = max(l) - max(l0)\n"),
    ("moved = None\nfor _ in range(6):\n    call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc)\n    if l[0] != l0[0]: moved = l[0] - l0[0]; break\n"
     "check(moved is not None and moved < 0,",
     "set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM[\"fl_ph\"], bytes([128])); call(m, \"render\"); l0 = line_words(m, bc)\n"
     "call(m, \"game_tick\"); call(m, \"render\"); l = line_words(m, bc); moved = max(l) - max(l0)\n"
     "check(moved < 0,"),
    ("set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM[\"fl_ph\"], bytes([0])); call(m, \"render\"); l0 = line_words(m, bc)\n"
     "fake_input(m, 0x04);",
     "set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM[\"fl_ph\"], bytes([128])); call(m, \"render\"); l0 = line_words(m, bc); wa = w0(m, bc)\n"
     "fake_input(m, 0x04);"),
    ("lt = line_words(m, bc); wt = max(w0(m, bc), 3)\n"
     "check(m.memory[SYM[\"fl_ph\"]] == 0 and [w for w in lt if w >= wt] == [w for w in l0 if w >= wt], \"(b) turning: fl_ph stays 0, floor lines unchanged (%s vs %s)\" % (lt, l0))\n",
     "lt = line_words(m, bc); wt = max(w0(m, bc), wa)\n"
     "check(m.memory[SYM[\"fl_ph\"]] == 128 and [w for w in lt if w >= wt] == [w for w in l0 if w >= wt], \"(b) turning: fl_ph stays 128, floor lines unchanged (%s vs %s)\" % (lt, l0))\n"),
    ('check(line_words(m, bc) == [] and all((lo, hi) == (0x55, 0xAA) for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure checker")\n',
     'check(line_words(m, bc) == [] and all((lo, hi) == CHK for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure checker")\n'),
])
print("floor3 done")