#!/bin/bash
# deck_fuse_install.sh - install the standalone Fuse Spectrum emulator (user flatpak) on alex-deck
set -u
echo "mode: $(systemctl --user -q is-active gamescope-session.service && echo GAME || echo DESKTOP)  dpms: $(cat /sys/class/drm/card1-DP-1/dpms 2>/dev/null)"
df -h ~ | tail -1
t0=$(date +%s)
flatpak install --user -y --noninteractive flathub net.sourceforge.fuse_emulator.Fuse 2>&1 | grep -vE '^\s*$|^Installing|^Updating|^\[' | tail -8
echo "install rc=${PIPESTATUS[0]} in $(( $(date +%s) - t0 )) s"
flatpak info --user net.sourceforge.fuse_emulator.Fuse 2>/dev/null | grep -E 'ID|Version|Runtime|Installed'
echo "--- fuse options of interest"
timeout 20 flatpak run --command=fuse net.sourceforge.fuse_emulator.Fuse --help 2>&1 | grep -iE 'joystick|kempston|full|machine|auto|tape|sound|speed|graphics' | head -30
echo "--- fuse binary/UI"
timeout 20 flatpak run --command=fuse net.sourceforge.fuse_emulator.Fuse --version 2>&1 | head -3
date -u +%H:%MZ
