#!/bin/bash
# lanes_watch.sh - orchestrator's zero-LLM status of the phase-1 lanes: newest file per lane, result files, oracle RESULT lines.
cd ~/work/killemall
date -u
for lane in N1 N1D N1A L E G N1M; do
  n=$(ls build/night/${lane}_* 2>/dev/null | wc -l)
  newest=$(ls -t build/night/${lane}_* 2>/dev/null | head -1)
  res=""
  [ -f build/night/${lane}_result.out ] && res="RESULT: $(grep -h -m1 -i 'RESULT' build/night/${lane}_result.out | cut -c1-100)"
  q=""; [ -f build/night/${lane}_QUESTIONS.md ] && q="Q:$(grep -c '^-\|^[0-9]' build/night/${lane}_QUESTIONS.md)"
  printf "%-4s files %3d  newest %-45s %s %s\n" "$lane" "$n" "$(basename "$newest" 2>/dev/null)" "$res" "$q"
done
echo "--- modified tracked files (git), by top dir:"
git status --short | awk '{print $2}' | cut -d/ -f1-2 | sort | uniq -c | sort -rn | head -12
echo "--- untracked new files outside build/night:"
git status --short | grep '^??' | grep -v 'build/night' | awk '{print $2}' | head -20
echo "--- release artefacts unchanged?"
md5sum build/release/killemall-0.27.1.zip build/killemall48_m25.tap build/killemall128_m2.tap | cut -c1-12,34-
