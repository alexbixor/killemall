#!/bin/bash
# run_fuse.sh v2 — headless Fuse (x11 driver on Xvfb), records FMF movie, quits cleanly via F10 so the movie flushes,
# converts the last frame to PNG.  usage: run_fuse.sh <file.tap> <seconds> <out.png> [48|128] [out.mp4]
set -u
TAP=$(readlink -f "$1"); SECS=$2; OUT=$(readlink -f -m "$3"); MACH=${4:-48}; MP4=${5:-}
TMP=$(mktemp -d); export TMP TAP SECS MACH
xvfb-run -a -s "-screen 0 800x600x24" bash -c '
  export SDL_AUDIODRIVER=dummy
  fuse-sdl --machine "$MACH" --no-sound --no-confirm-actions --auto-load --tape "$TAP" --movie-start "$TMP/run.fmf" --movie-compr none > "$TMP/fuse.log" 2>&1 &
  FP=$!
  sleep "$SECS"
  WID=$(xdotool search --name "Fuse" | head -n 1)
  [ -n "$WID" ] && xdotool windowactivate --sync "$WID" key F10 || xdotool key F10
  sleep 1; xdotool key Return 2>/dev/null; sleep 2
  kill -0 $FP 2>/dev/null && { kill $FP; echo "fuse killed (no clean exit)"; }
  wait $FP 2>/dev/null; echo "fuse exit"
' 2>&1 | grep -v -iE '^$'
if [ -s "$TMP/run.fmf" ]; then
  fmfconv -G -o "$TMP/frame" "$TMP/run.fmf" >/dev/null 2>&1
  N=$(ls "$TMP"/frame*.png 2>/dev/null | wc -l)
  LAST=$(ls "$TMP"/frame*.png 2>/dev/null | tail -n 1)
  if [ -n "$LAST" ]; then
    cp "$LAST" "$OUT"; echo "frames=$N fmf=$(stat -c %s "$TMP/run.fmf")B saved=$OUT"
    if [ -n "$MP4" ]; then ffmpeg -loglevel error -y -framerate 50 -pattern_type glob -i "$TMP/frame*.png" -vf "scale=iw*3:ih*3:flags=neighbor,format=yuv420p" -c:v libx264 -crf 20 "$MP4" && echo "mp4=$MP4"; fi
  else echo "no frames decoded"; fi
else echo "no movie written"; grep -v -iE 'warranty|license|copyright|free software|^$|fitness|redistribute|foundation|details|GNU' "$TMP/fuse.log" | head -n 5; fi
rm -rf "$TMP"
