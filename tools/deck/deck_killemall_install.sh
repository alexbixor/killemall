#!/bin/bash
# deck_killemall_install.sh - runs ON the Deck (bash -s): install launcher + desktop entry, headless self-test with the real pad device
set -u
mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/state/deck ~/Emulation/roms/zxspectrum
install -m 755 /tmp/launch-killemall.sh ~/.local/bin/launch-killemall
cp /tmp/killemall48_m22.tap ~/Emulation/roms/zxspectrum/killemall48_m22.tap
echo "tape: $(stat -c '%s B' ~/Emulation/roms/zxspectrum/killemall48_m22.tap) sha256 $(sha256sum ~/Emulation/roms/zxspectrum/killemall48_m22.tap | cut -c1-16)"
cat > ~/.local/share/applications/killemall.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Kill'em all (ZX Spectrum)
Comment=Kill'em all M2.2 in ZEsarUX, full screen, pad or QAOP keys
Exec=/home/alex/.local/bin/launch-killemall
Icon=input-gaming
Terminal=false
Categories=Game;Emulator;
EOF
cp ~/.local/share/applications/killemall.desktop ~/Desktop/Kill_em_all.desktop 2>/dev/null && chmod +x ~/Desktop/Kill_em_all.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null
echo "--- headless self-test on the Deck (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test rc=$?"
tail -3 ~/.local/state/deck/killemall.log | cut -c1-160
grep -ciE 'error|cannot|unknown' ~/.local/state/deck/killemall.log
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
date -u +%H:%MZ
