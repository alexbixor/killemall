#!/bin/bash
# deck_steam_shortcut.sh - add the launcher as a Non-Steam game via steam:// URL (desktop session), verify in shortcuts.vdf; drop the unused Fuse flatpak
set -u
export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
echo "mode: $(systemctl --user -q is-active gamescope-session.service && echo GAME || echo DESKTOP); steam: $(pgrep -x steam >/dev/null && echo running || echo stopped)"
VDF=$(ls ~/.steam/steam/userdata/*/config/shortcuts.vdf 2>/dev/null | head -1)
echo "shortcuts.vdf: ${VDF:-none}  before: $(grep -c -a 'launch-killemall' "${VDF:-/dev/null}" 2>/dev/null)"
timeout 20 steam "steam://addnonsteamgame//home/alex/.local/bin/launch-killemall" >/dev/null 2>&1; echo "url rc=$?"
sleep 6
VDF=$(ls ~/.steam/steam/userdata/*/config/shortcuts.vdf 2>/dev/null | head -1)
echo "after: $(grep -c -a 'launch-killemall' "${VDF:-/dev/null}" 2>/dev/null) hit(s) in ${VDF:-none}"
grep -a -o 'launch-killemall[^"]*' "${VDF:-/dev/null}" 2>/dev/null | head -2
flatpak uninstall --user -y --noninteractive net.sourceforge.fuse_emulator.Fuse >/dev/null 2>&1 && echo "fuse flatpak removed (unused)"
date -u +%H:%MZ
