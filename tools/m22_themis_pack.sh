#!/bin/bash
# m22_themis_pack.sh - stage the M2.2 review packet in Themis's workspace (read-only copies + SHA256SUMS + diff vs pre-M2.2)
set -e
cd ~/work/killemall
W=~/.hermes/profiles/themis/work/killemall-m22-$(date -u +%Y%m%d)
rm -rf "$W"; mkdir -p "$W/src/common" "$W/src/48k/gen" "$W/tools" "$W/build" "$W/pre_m22"
cp src/48k/kea48.asm "$W/src/48k/"
cp src/48k/gen/sprites48.asm src/48k/gen/tables48.asm "$W/src/48k/gen/"
cp src/common/*.asm "$W/src/common/"
cp tools/gen48.py tools/m22_pixdata.py tools/m22_mockup.py tools/test_game_hud.py tools/test_sprite_scale.py tools/test_game_sprites.py \
   tools/test48.py tools/m22_stack.py tools/m22_shots.py tools/t6_zes.py tools/build_m22_48.sh tools/t6_gates.sh tools/make128.py tools/test_128.py "$W/tools/"
cp build/kea48.sym build/killemall48_m22.tap build/m22_sheet.png build/m22_game_live.png build/m22_sprites_near.png build/m22_sprites_mid.png \
   build/m22_sprites_far.png build/m22_dash_low.png build/m22_mockup_1x.png build/m22_themis_r1.md build/m22_gates_step4.out build/test_128.out "$W/build/"
# pre-M2.2 sources for the diff
mkdir -p /tmp/pre22 && tar xzf build/pre_m22/src_pre_m22.tgz -C /tmp/pre22
cp -r /tmp/pre22/src "$W/pre_m22/"
cp build/pre_m22/kea48_pre_m22.sym "$W/pre_m22/"
( cd "$W" && diff -ru pre_m22/src src > DIFF-pre_m22-to-m22.patch || true )
echo "diff lines: $(wc -l < "$W/DIFF-pre_m22-to-m22.patch")"
( cd "$W" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "$W"; du -sh "$W"; wc -l "$W/SHA256SUMS"
