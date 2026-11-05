#!/bin/bash
# deck_m25_128_install.sh - runs ON the Deck (bash -s): second launcher + desktop icon for the 128K edition (AY music).
# Expects /tmp/launch-killemall128.sh and /tmp/killemall128_m25.tap (scp'd first). Headless self-test only - no window on the Deck screen.
set -u
mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/state/deck ~/Emulation/roms/zxspectrum
install -m 755 /tmp/launch-killemall128.sh ~/.local/bin/launch-killemall128
cp /tmp/killemall128_m25.tap ~/Emulation/roms/zxspectrum/killemall128_m25.tap
echo "tape: $(stat -c '%s B' ~/Emulation/roms/zxspectrum/killemall128_m25.tap) sha256 $(sha256sum ~/Emulation/roms/zxspectrum/killemall128_m25.tap | cut -c1-16)"
cat > ~/.local/share/applications/killemall128.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Kill'em all 128K (ZX Spectrum, AY music)
Comment=Kill'em all 128K edition in ZEsarUX (--machine 128k), full screen, pad or QAOP keys
Exec=/home/alex/.local/bin/launch-killemall128
Icon=input-gaming
Terminal=false
Categories=Game;Emulator;
EOF
cp ~/.local/share/applications/killemall128.desktop ~/Desktop/Kill_em_all_128K.desktop 2>/dev/null && chmod +x ~/Desktop/Kill_em_all_128K.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null
echo "48K launcher untouched: $(ls -t ~/Emulation/roms/zxspectrum/killemall48_*.tap | head -1)"
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test rc=$?"
tail -3 ~/.local/state/deck/killemall128.log | cut -c1-160
grep -ciE 'error|cannot|unknown' ~/.local/state/deck/killemall128.log
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
ls -la ~/Desktop/Kill_em_all*.desktop | awk '{print $NF}'
date -u +%H:%MZ
