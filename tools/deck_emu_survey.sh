#!/bin/bash
# deck_emu_survey.sh - READ-ONLY: what Spectrum emulators are on the Deck, where the tapes are
echo "mode: $(systemctl --user -q is-active gamescope-session.service && echo GAME || echo DESKTOP)"
echo "--- flatpaks (emulator-ish)"
flatpak list --app --columns=application,version 2>/dev/null | grep -iE 'retro|fuse|zesar|spec|emu' || echo none
echo "--- native binaries"
for b in fuse fuse-gtk fuse-sdl zesarux retroarch; do command -v $b 2>/dev/null; done
pacman -Qs 'fuse-emulator\|zesarux\|retroarch' 2>/dev/null | grep -E '^local' || echo "no native emu pkgs"
echo "--- tapes on disk"
find ~ /run/media -maxdepth 6 -iname 'killemall*.tap' -printf '%p %s %TY-%Tm-%Td %TH:%TM\n' 2>/dev/null | head
echo "--- flathub: Fuse available?"
timeout 25 flatpak remote-info --system flathub net.sf.fuse_emulator.Fuse 2>&1 | grep -E 'ID|Version|Download' || \
timeout 25 flatpak remote-info --user flathub net.sf.fuse_emulator.Fuse 2>&1 | grep -E 'ID|Version|Download' || echo "fuse not on flathub (or remote missing)"
flatpak remotes --columns=name,options 2>/dev/null
echo "--- retroarch cores (fuse?)"
ls ~/.var/app/org.libretro.RetroArch/config/retroarch/cores 2>/dev/null | grep -i fuse || echo "no fuse core in flatpak RA"
ls ~/.config/retroarch/cores 2>/dev/null | grep -i fuse || true
ls ~/Emulation/roms 2>/dev/null | head -20 || true
echo "--- gamepad seen by kernel"
ls /dev/input/by-id 2>/dev/null | grep -iE 'valve|steam|joystick' || true
date -u +%H:%MZ
