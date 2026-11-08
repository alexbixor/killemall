#!/bin/bash
# m24_status.sh - append the M2.4 section to build/m22_status.txt (facts from the build/gate outputs, no hand-typed numbers)
cd ~/work/killemall || exit 1
{
echo
echo "== M2.4 ($(date -u +%Y-%m-%d\ %H:%MZ)) - sprite cell card (no colour bleeding) + zombie art"
echo "tape: build/killemall48_m24.tap $(stat -c %s build/killemall48_m24.tap) B sha $(sha256sum build/killemall48_m24.tap | cut -c1-16); m23/m22/m2 untouched"
grep -E "^(hi_end|level_data|spr_table)\s" build/kea48.sym | tr '\n' ' '; echo
grep -E "hi_end 0x|free below" build/m24_build.out
grep -E "exit [0-9]+ :" build/m24_gates.out | sed 's/^/gate: /'
grep -E "fps" build/m24_v4_shots.out 2>/dev/null | head -8 | sed 's/^/zes: /'
echo "card: per byte column, cells k0..k1 spanned by the ink -> one chain call black (and 0/or 0), attr = TYPEINK; black runs no longer drawn"
echo "layout: shotgun sprites 16/17 aliased to 14/15 (weapon_frame never selects them); sprite low block grew into the freed bytes"
echo "art: assets/sprites/04..07 zombie v12-14 (hunched 3/4 shambler, arms forward, lunge attack, prone corpse); 00..03 'bloater' = mirrored body + own skull"
echo "oracles: test_sprite_card.py (new, 23 scenes), test_sprite_scale/test_game_sprites updated for whole-cell card (byte-column span, first ink row)"
echo "deck: ~/Emulation/roms/zxspectrum/killemall48_m24.tap installed $(date -u +%H:%MZ), launcher picks newest, headless self-test rc 0"
} >> build/m22_status.txt
tail -22 build/m22_status.txt
