#!/bin/bash
# deck_n3f_hires_install.sh - runs ON the Deck (bash -s), 6 Nov 2026 ~20:10Z (lane N3F follow-up, Alex: "push them in the deck too as desktop icons").
# The 48K (killemall48_m25.tap d4eda089) and 128K (killemall128_m25.tap b1681a3b) tapes sent in chat are ALREADY live and byte-identical
# on the Deck with their two desktop icons, so they are not touched. This adds the THIRD tape: the experimental lane-S hi-res 128K
# build, as its own icon. It is stored in a SUBDIRECTORY (experimental/) so the regular 128K launcher's "newest killemall128_*.tap"
# glob keeps picking killemall128_m25.tap; the new icon passes the tape path explicitly. Also refreshes the stale labels of the two
# existing icons (48K Comment still said "M2.2"). Backups of the 4 touched .desktop files in ~/.local/state/deck/desktop-backup-<ts>/.
# Expects /tmp/killemall128_hires_experimental.tap (scp'd first). Headless self-test only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
EXP=$ROMS/experimental
exph=1ae2d7ae98680be3            # sha256 (first 16 hex) of build/killemall128_hires.tap, lane S 13:38Z 6 Nov 2026
TS=$(date -u +%Y%m%d-%H%M%S)
echo "start $(date -u +%H:%M:%SZ)"
pgrep -x zesarux >/dev/null && { echo "ABORT: a game (zesarux) is running"; exit 3; }
pgrep -f "reaper SteamLaunch" >/dev/null && { echo "ABORT: Steam game running"; exit 3; }
h=$(sha256sum /tmp/killemall128_hires_experimental.tap | cut -c1-16)
[ "$h" = "$exph" ] || { echo "ABORT: hires tape hash $h != $exph"; exit 3; }
# --- 1. the two shipped tapes: assert they are already live, identical to what was sent in chat
echo "live 48K  : $(ls -t $ROMS/killemall48_*.tap | head -1 | xargs -I{} sh -c 'echo $(basename {}) $(sha256sum {} | cut -c1-16)')"
echo "live 128K : $(ls -t $ROMS/killemall128_*.tap | head -1 | xargs -I{} sh -c 'echo $(basename {}) $(sha256sum {} | cut -c1-16)')"
# --- 2. hi-res tape into the subdirectory (outside the launcher glob)
mkdir -p $EXP ~/.local/state/deck/desktop-backup-$TS
cp /tmp/killemall128_hires_experimental.tap $EXP/killemall128_hires_experimental.tap
echo "hires tape: $(stat -c '%s B' $EXP/killemall128_hires_experimental.tap) sha256 $(sha256sum $EXP/killemall128_hires_experimental.tap | cut -c1-16)"
echo "128K launcher still picks (newest, glob excludes experimental/): $(basename $(ls -t $ROMS/killemall128_*.tap | head -1))"
# --- 3. backups of the desktop entries we touch
cp -p ~/.local/share/applications/killemall.desktop ~/.local/share/applications/killemall128.desktop \
      ~/Desktop/Kill_em_all.desktop ~/Desktop/Kill_em_all_128K.desktop ~/.local/state/deck/desktop-backup-$TS/ 2>/dev/null
echo "backup: $(ls ~/.local/state/deck/desktop-backup-$TS | wc -l) files in desktop-backup-$TS"
# --- 4. third icon: hi-res experimental (explicit tape path, same 128K launcher = same pad mapping)
cat > ~/.local/share/applications/killemall128hires.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Kill'em all 128K hi-res (experimental)
Comment=Experimental 2-px-column hi-res zombies (lane S, 6 Nov 2026). Same 128K engine and pad keys, ~8-16% slower with zombies close. Plays experimental/killemall128_hires_experimental.tap.
Exec=/home/alex/.local/bin/launch-killemall128 /home/alex/Emulation/roms/zxspectrum/experimental/killemall128_hires_experimental.tap
Icon=input-gaming
Terminal=false
Categories=Game;Emulator;
EOF
cp ~/.local/share/applications/killemall128hires.desktop ~/Desktop/Kill_em_all_128K_hires.desktop && chmod +x ~/Desktop/Kill_em_all_128K_hires.desktop
# --- 5. refresh the labels of the two existing icons (stale "M2.2"); version-free wording so they do not go stale again
for f in ~/.local/share/applications/killemall.desktop ~/Desktop/Kill_em_all.desktop; do
  sed -i -e "s|^Name=.*|Name=Kill'em all 48K (ZX Spectrum)|" \
         -e "s|^Comment=.*|Comment=Kill'em all 48K in ZEsarUX, full screen, pad or QAOP keys. Plays the newest killemall48_*.tap (M2.5 lattice build as of 6 Nov 2026).|" "$f"
done
for f in ~/.local/share/applications/killemall128.desktop ~/Desktop/Kill_em_all_128K.desktop; do
  sed -i -e "s|^Comment=.*|Comment=Kill'em all 128K (AY music, tear-free shadow-screen flip) in ZEsarUX, full screen, pad or QAOP keys. Plays the newest killemall128_*.tap (M2.5 FLIP build as of 6 Nov 2026).|" "$f"
done
update-desktop-database ~/.local/share/applications 2>/dev/null
echo "--- desktop icons now"
for d in ~/Desktop/Kill_em_all*.desktop; do echo "== $(basename $d) ($(stat -c '%a' $d))"; grep -E '^(Name|Exec)=' "$d"; done
# --- 6. headless self-test of the new icon's exact command (no window, 8 s)
echo "--- headless self-test hi-res 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128 /home/alex/Emulation/roms/zxspectrum/experimental/killemall128_hires_experimental.tap; echo "self-test rc=$?"
tail -1 ~/.local/state/deck/killemall128.log | cut -c1-160
echo "errors in 128K log since start: $(grep -ciE 'error|cannot|unknown' ~/.local/state/deck/killemall128.log)"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
rm -f /tmp/killemall128_hires_experimental.tap
echo "end $(date -u +%H:%M:%SZ)"
