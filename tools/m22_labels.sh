#!/bin/bash
# m22_labels.sh - read-only: label clashes between the new hud.asm and the rest of the 48K build
cd ~/work/killemall
grep -o "^[A-Za-z_][A-Za-z0-9_]*:" src/common/hud.asm | tr -d ':' | sort -u > /tmp/hud_labels.txt
grep -ho "^[A-Za-z_][A-Za-z0-9_]*:" src/common/*.asm src/48k/kea48.asm src/48k/gen/*.asm | tr -d ':' | sort | uniq -d > /tmp/dups.txt
echo "duplicate labels across the build (incl. hud.asm):"; cat /tmp/dups.txt
echo "---- of which from hud.asm:"; comm -12 /tmp/hud_labels.txt /tmp/dups.txt
