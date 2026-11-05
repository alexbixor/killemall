#!/bin/bash
# t6_gates.sh - run every lane test + geo48 (walls-only) against the current build; summary to stdout, details build/t6_*.out
cd ~/work/killemall
for t in test_game_sprites test_game_doors test_game_enemies test_game_hud test_frontend test_sound; do
  timeout 500 .venv/bin/python tools/$t.py > build/t6_$t.out 2>&1
  echo "$t exit $? : $(tail -1 build/t6_$t.out | cut -c1-60)"
done
NOTHINGS=1 bash tools/geo48.sh > build/t6_geo48.out 2>&1
echo "geo48 views with 0 wrong columns: $(grep -c 'mismatches (>2 rows): 0 of 64' build/t6_geo48.out)/9"
grep '^view' build/t6_geo48.out | sed 's/mismatches (>2 rows)://' | awk '{print $2,$3,$4,$8,$9,$12,$13}' | tr '\n' ';'; echo
