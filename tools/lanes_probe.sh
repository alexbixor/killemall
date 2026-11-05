#!/bin/bash
# Kill'em all M2 lane probe: one line per delegation lane + new build artefacts.
# Usage: bash tools/lanes_probe.sh [deleg_id]  (default deleg_6a8ffa74) → prints to stdout
D=${1:-deleg_6a8ffa74}
LIVE=/home/ubuntu/.hermes/cache/delegation/live/$D
date -u +%H:%M:%SZ
for i in 0 1 2 3 4; do
  L=$LIVE/task-$i.log
  if [ -f "$L" ]; then
    n=$(wc -l < "$L")
    sz=$(stat -c %s "$L")
    last=$(tail -c 2000 "$L" | tr -d '\r' | grep -v '^\s*$' | tail -1 | cut -c1-110)
    echo "T$((i+1)) lines=$n bytes=$sz mtime=$(stat -c %y "$L" | cut -c12-19) | $last"
  else
    echo "T$((i+1)) NO LOG YET"
  fi
done
echo "--- artefacts (build/) newer than ARCH_M2.md:"
find /home/ubuntu/work/killemall/build /home/ubuntu/work/killemall/src /home/ubuntu/work/killemall/assets /home/ubuntu/work/killemall/tools \
  -newer /home/ubuntu/work/killemall/ARCH_M2.md -type f 2>/dev/null | grep -v -E '/\.venv/|__pycache__' | sed 's#/home/ubuntu/work/killemall/##' | sort | head -40
