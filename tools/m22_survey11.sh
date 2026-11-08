#!/bin/bash
# m22_survey11.sh - read-only: do the relocated tables get walked with inc l / dec l (page assumptions), ROM calls that would touch 0x5D00+
cd ~/work/killemall
echo "== zbuf / things / vis / door_log / fe_tmpk users"
grep -n "zbuf\|things\|\bvis\b\|door_log\|fe_tmpk" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/state.asm\|^\S*:[0-9]*:;" | head -60
echo "== inc l / dec l / ld l near them (sprites.asm sprites_b.asm game_b.asm game_c.asm)"
grep -n "inc l\|dec l\|ld l,\|inc h\b" src/common/sprites.asm src/common/sprites_b.asm src/common/game_b.asm src/common/game_c.asm src/common/game_d.asm | head -40
echo "== ROM calls (rst / call < 0x4000)"
grep -n "rst \|call 0x0\|call 0x1\|call 0x2\|call 0x3\|call [0-9]\{1,5\}$" src/common/*.asm src/48k/kea48.asm | grep -v "^\S*:[0-9]*:;" | head
echo "== test harness: hard-coded addresses for things/vis?"
grep -n "things\|0xF6\|0xf6\|sym\[" tools/test_sprite_scale.py tools/test_game_sprites.py tools/test48.py | head -20
