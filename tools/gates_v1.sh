#!/bin/bash
# gates_v1.sh (lane G, 5 Nov 2026) - every release gate of both editions in one run, one line per gate + RESULT.
#  * the 14 gates of tools/m25_gates.sh (build_m25_48.sh + t6_gates.sh: 6 lane tests + geo48, then one_ink, tint, floor_lines,
#    ceiling, sprite_scale, test_128 (which runs build128.sh), m22_stack) - unchanged scripts, so "what green looks like" is
#    still build/m29b_gates.out;
#  * NEW: test_game_replay.py = 600 deterministic steps of the current 48K build against the pre-G tape
#    (build/night/pre_G/build/killemall48_m25.tap): same posx/posy/health/kills/things bytes at every step.
# Side effect of m25_gates.sh (as always): build_m25_48.sh rewrites build/killemall48_m25.tap with the CURRENT build. This
# script keeps the current one as build/killemall48_g.tap and puts the shipped m25 tape back from build/night/pre_G/build/.
# usage: bash tools/gates_v1.sh > build/night/G_gates.out 2>&1 ; exit 0 only when every gate passed.
cd "$(dirname "$0")/.."   # repo root
fail=0
bash tools/m25_gates.sh > build/gates_v1_m25.out 2>&1
cat build/gates_v1_m25.out
grep -q "build exit 0" build/gates_v1_m25.out || fail=1
for t in test_game_sprites test_game_doors test_game_enemies test_game_hud test_frontend test_sound test_one_ink test_tint test_floor_lines test_ceiling test_sprite_scale test_128 m22_stack; do
  grep -q "^$t exit 0" build/gates_v1_m25.out || { echo "GATE FAILED: $t"; fail=1; }
done
grep -q "geo48 views with 0 wrong columns: 9/9" build/gates_v1_m25.out || { echo "GATE FAILED: geo48"; fail=1; }
cp build/killemall48_m25.tap build/killemall48_g.tap
if [ -f build/night/pre_G/build/killemall48_m25.tap ]; then
  cp build/night/pre_G/build/killemall48_m25.tap build/killemall48_m25.tap
  echo "shipped m25 tape restored: $(sha256sum build/killemall48_m25.tap | cut -c1-16) ; current build kept as build/killemall48_g.tap $(sha256sum build/killemall48_g.tap | cut -c1-16)"
fi
timeout 500 .venv/bin/python tools/test_game_replay.py > build/gates_v1_replay.out 2>&1
rc=$?
echo "test_game_replay exit $rc : $(tail -1 build/gates_v1_replay.out | cut -c1-90)"
[ $rc -eq 0 ] || fail=1
grep -E "^(hi_end|low_end|ETAB)\s" build/kea48.sym | tr '\n' ' '; echo
grep -E "^(hi_end)\s" build/kea128.sym | sed 's/^/128K /'
echo "RESULT $([ $fail -eq 0 ] && echo 'ALL GATES GREEN (15: 14 + replay)' || echo FAIL)"
exit $fail
