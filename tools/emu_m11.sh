#!/bin/bash
# emu_m11.sh - emulator verification of the current build/kea48.tap as M1.1: fps + PNG + MP4 at the start viewpoint and at the
# near-wall viewpoint, then the frame-integrity check of all grabbed frames.  Outputs under build/ (m11_* files).
cd ~/work/killemall
cp build/kea48.tap build/killemall48_m11.tap
cp build/kea48.sym build/killemall48_m11.sym
SYM=build/killemall48_m11.sym FRAMES_DIR=/tmp/kea_frames_m11 .venv/bin/python tools/demo48.py build/killemall48_m11.tap build/kea48_m11.png build/kea48_m11.mp4 32 > build/demo48_m11_start.out 2>&1
.venv/bin/python tools/framechk48.py /tmp/kea_frames_m11 > build/framechk_m11_start.out 2>&1
SYM=build/killemall48_m11.sym FRAMES_DIR=/tmp/kea_frames_m11_near .venv/bin/python tools/demo48.py build/killemall48_m11.tap build/kea48_m11_near.png build/kea48_m11_near.mp4 32 7.3 7.5 0 > build/demo48_m11_near.out 2>&1
.venv/bin/python tools/framechk48.py /tmp/kea_frames_m11_near > build/framechk_m11_near.out 2>&1
grep -h "fps\|viewpoint\|mp4" build/demo48_m11_start.out build/demo48_m11_near.out
grep -h "^frames" build/framechk_m11_start.out build/framechk_m11_near.out
