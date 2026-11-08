#!/bin/bash
# build48.sh - generate tables, compile levels, assemble the 48K edition to build/kea48.tap
set -e
cd "$(dirname "$0")/.."   # repo root
python3 tools/gen48.py
python3 tools/mapc.py 48k src/48k/gen/level48.bin assets/levels/01_entry.txt
cd src/48k && pasmo --tapbas kea48.asm ../../build/kea48.tap ../../build/kea48.sym && cd ../..
ls -la build/kea48.tap | awk '{print "tap bytes", $5}'
