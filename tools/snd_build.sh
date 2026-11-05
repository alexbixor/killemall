#!/bin/bash
# snd_build.sh - T3 sound lane: standalone sound test tapes.
#   build/snd_test48.tap  (48K: plays SFX 1..10, then loops the beeper menu tune; keys 1..0 = SFX)
#   build/snd_test128.tap (128K: AY menu track; M = menu track, G = game track, S = stop, keys 1..0 = SFX)
# Same pasmo invocation as tools/build48.sh (pasmo --tapbas => autostart BASIC loader + code block).
set -e
cd ~/work/killemall
PY=.venv/bin/python
$PY tools/music/gen_beeper.py > build/gen_beeper.out
$PY tools/music/compile_music.py > build/compile_music.out
cd tools/music
pasmo --tapbas snd_test48.asm ../../build/snd_test48.tap ../../build/snd_test48.sym
pasmo --tapbas snd_test128.asm ../../build/snd_test128.tap ../../build/snd_test128.sym
cd ../..
ls -la build/snd_test48.tap build/snd_test128.tap | awk '{print $9, "tap bytes", $5}'
