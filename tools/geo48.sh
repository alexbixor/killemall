#!/bin/bash
# geo48.sh - run the geometry check from several viewpoints covering all four DDA quadrants, near and far walls.
cd ~/work/killemall
for v in "3.5 7.5 0" "3.5 7.5 64" "3.5 7.5 128" "3.5 7.5 192" "9.0 10.0 150" "25.5 3.5 40" "12.2 14.7 230" "1.3 1.3 32" "20.5 20.5 96"; do
  set -- $v
  timeout 300 .venv/bin/python tools/test48.py $1 $2 $3 > /tmp/geo_t.out 2>&1
  .venv/bin/python tools/chk48.py build/test48_scr.bin src/48k/gen/level48.bin $1 $2 $3 > /tmp/geo_c.out 2>&1
  echo "view $v : $(grep -oE 'render T-states [0-9]+' /tmp/geo_t.out) : $(tail -1 /tmp/geo_c.out)"
  grep '^ray' /tmp/geo_c.out | head -3
done
