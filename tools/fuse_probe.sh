#!/bin/bash
# fuse_probe.sh — find a working headless path: does Fuse under Xvfb see keys (F10 quit) and flush the FMF movie?
set -u
TMP=$(mktemp -d); export TMP
TAP=/tmp/kea_smoke/fill48.tap; export TAP
xvfb-run -a -s "-screen 0 800x600x24" bash -c '
  export SDL_AUDIODRIVER=dummy
  fuse-sdl --machine 48 --no-sound --no-confirm-actions --auto-load --tape "$TAP" --movie-start "$TMP/run.fmf" --movie-compr none > "$TMP/fuse.log" 2>&1 &
  FP=$!; sleep 6
  echo "windows: $(xdotool search --onlyvisible --name . 2>/dev/null | while read w; do xdotool getwindowname $w; done | tr "\n" "|")"
  echo "fmf size during run: $(stat -c %s "$TMP/run.fmf" 2>/dev/null)"
  WID=$(xdotool search --name "Fuse" | head -n 1); echo "fuse wid=$WID"
  xdotool key --window "$WID" F10 2>/dev/null; sleep 1; echo "after F10: alive=$(kill -0 $FP 2>/dev/null && echo yes || echo no) fmf=$(stat -c %s "$TMP/run.fmf" 2>/dev/null)"
  xdotool key --window "$WID" Return 2>/dev/null; sleep 2; echo "after Return: alive=$(kill -0 $FP 2>/dev/null && echo yes || echo no) fmf=$(stat -c %s "$TMP/run.fmf" 2>/dev/null)"
  if kill -0 $FP 2>/dev/null; then kill -INT $FP; sleep 2; echo "after SIGINT: alive=$(kill -0 $FP 2>/dev/null && echo yes || echo no) fmf=$(stat -c %s "$TMP/run.fmf" 2>/dev/null)"; fi
  kill -0 $FP 2>/dev/null && { kill -TERM $FP; sleep 2; echo "after SIGTERM: alive=$(kill -0 $FP 2>/dev/null && echo yes || echo no) fmf=$(stat -c %s "$TMP/run.fmf" 2>/dev/null)"; }
  kill -9 $FP 2>/dev/null; wait $FP 2>/dev/null
'
fmfconv -G -o "$TMP/frame" "$TMP/run.fmf" 2>&1 | grep -E 'frames' | cut -c1-120
echo "png frames: $(ls "$TMP"/frame*.png 2>/dev/null | wc -l)"
rm -rf "$TMP"
