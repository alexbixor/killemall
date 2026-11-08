#!/bin/bash
# m23_status.sh - append the M2.3 record to build/m22_status.txt (facts from build/m23_gates.out, m23_pad_test.out, Deck install)
cd ~/work/killemall
SHA=$(sha256sum build/killemall48_m23.tap | cut -c1-16); SZ=$(stat -c %s build/killemall48_m23.tap)
cat >> build/m22_status.txt <<EOF

== M2.3 - $(date -u +%Y-%m-%d\ %H:%MZ) == floor distance lines + SPACE fires / M opens (defaults; REDEFINE KEYS unchanged)
Tape build/killemall48_m23.tap $SZ B sha256 $SHA (tools/build_m23_48.sh). M2.2 tape 672bfe8c and M2.1 tape untouched.
Keys: in_keys defaults Q A O P SPACE M Z X (src/common/input.asm). Pad: A -> SPACE (fire), X -> M (open), B = joystick Fire
= SPACE (fire too). tools/m22_pad_test.py 17/17 + end-to-end on the M2.3 tape (build/m23_pad_test.out).
Floor: src/common/floor.asm (fl_set 2,959 T/frame, 92 B code+data) placed in the alignment padding before HTABN (0 B of code
budget; build script asserts HTABN stays 0xD800). CLRBUF push opcodes patched per frame (D5 checker / E5 line word 0xFFAA =
1-px line). Half-cell grid lines nearer than 4 cells, perspective rows from FL_D4[w] = round(384/w); phase fl_ph += 38 per
moving tick (0.15 cell) forward, -38 back, 0 when blocked or turning. tools/test_floor_lines.py 11/11 (oracle
tools/m23_floor_model.py). DETAIL LOW keeps the lines over a plain floor.
Gates (build/m23_gates.out): 6 lane tests PASS, geo48 9/9, test_sprite_scale PASS, test_128 PASS, stack 18 B (gap 66 B),
hi_end 0xFD9C (+4 B vs M2.2: the two zero-delta checks in move_by, net of the push-opcode patch). ZEsarUX real ROM
(tools/m23_shots.py): 9.7 fps start view (M2.2: 9.0), SPACE fires ammo 50->49, M does not; floor phase 0->40 walking,
unchanged turning. Stills build/m23_start_v1.png, build/m23_floor_v2.png; clip build/m23_walk_v1.mp4.
Deck: tape installed ~/Emulation/roms/zxspectrum/killemall48_m23.tap (newest -> launcher picks it), launcher updated,
headless self-test rc=0 (tools/deck/deck_m23_install.sh). Known: m22_pad_test.py default tape is now m23 (PAD_TAP overrides).
EOF
tail -3 build/m22_status.txt | cut -c1-80