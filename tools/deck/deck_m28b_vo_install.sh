#!/bin/bash
# deck_m28b_vo_install.sh - runs ON the Deck (bash -s). Alex approved "push" (3 Nov 23:3xZ).
# Fix for "strafe, X Z, still does not work" via Moonlight: ZEsarUX --vo xwindows under Xwayland drops every LETTER key
# (Q A O P M Z X never reach the emulated Spectrum keyboard; arrows/SPACE do), proven live 23:08Z/23:09Z 3 Nov
# (build/m28_deck_live1.out vs live2.out). --vo sdl delivers all keys. Change: launchers use --vo sdl, nothing else.
# Previous launchers kept as *.bak-m28-vo for rollback. Then: full-screen size + audio + pad check (window opens for ~12 s).
set -u
echo "deck $(date -u +%H:%M:%SZ)"
pgrep -x zesarux >/dev/null && { echo "ABORT: a game is running"; exit 3; }
if pgrep -f "reaper SteamLaunch" >/dev/null; then echo "ABORT: Steam game running"; exit 3; fi   # (v1 used "| head -1 &&" = always true)
B=~/.local/bin
for L in launch-killemall launch-killemall128; do
  [ -f $B/$L ] || { echo "ABORT: $B/$L missing"; exit 3; }
  grep -q -- '--vo xwindows --ao pulse' $B/$L || { echo "ABORT: $L does not contain the expected '--vo xwindows --ao pulse'"; exit 3; }
  [ -f $B/$L.bak-m28-vo ] || cp -p $B/$L $B/$L.bak-m28-vo
  sed -i 's/--vo xwindows --ao pulse/--vo sdl --ao pulse/' $B/$L
  sed -i 's|^# Keyboard always works: Q A O P M SPACE Z X, CAPS+SPACE pause, F5/ESC emulator menu.|# Keyboard always works: Q A O P M SPACE Z X, CAPS+SPACE pause, F5/ESC emulator menu. --vo sdl: xwindows under Xwayland drops letter keys (3 Nov 2026).|' $B/$L
  echo "$L: $(grep -c -- '--vo sdl' $B/$L) sdl line(s), md5 $(md5sum $B/$L | cut -c1-12), backup $(md5sum $B/$L.bak-m28-vo | cut -c1-12)"
  bash -n $B/$L && echo "  syntax ok"
done
echo "--- headless self-tests (no window)"
KEA_HEADLESS=1 timeout 30 $B/launch-killemall >/dev/null 2>&1; echo "48K headless rc=$?"
KEA_HEADLESS=1 timeout 30 $B/launch-killemall128 >/dev/null 2>&1; echo "128K headless rc=$?"
echo "--- live check: 128K full screen via sdl for ~14 s (window geometry, audio stream, pad attached)"
eval "$(systemctl --user show-environment | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS)=' | sed 's/^/export /')"
cat > /tmp/hal_win.js <<'EOF'
for (const w of workspace.windowList()) {
  if ((w.caption || "").indexOf("ZEsarUX") >= 0 || (w.resourceClass || "").toLowerCase().indexOf("zesarux") >= 0)
    print("HALWIN caption=" + w.caption + " class=" + w.resourceClass + " frame=" + w.frameGeometry.width + "x" + w.frameGeometry.height +
          "@" + w.frameGeometry.x + "," + w.frameGeometry.y + " fullScreen=" + w.fullScreen + " active=" + w.active + " screen=" + (w.output ? w.output.name : "?"));
}
EOF
timeout 22 $B/launch-killemall128 & LP=$!
sleep 10
echo "zesarux: $(pgrep -x zesarux | head -1 | xargs -r -I{} sh -c 'echo pid {}; tr "\0" " " < /proc/{}/cmdline | grep -o -- "--vo [a-z]*"')"
SID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript /tmp/hal_win.js halwin 2>&1)
echo "kwin script id: $SID"
qdbus6 org.kde.KWin /Scripting/Script$SID org.kde.kwin.Script.run 2>&1 | head -1
sleep 1
journalctl --user -o cat --since -15s 2>/dev/null | grep HALWIN | tail -3
qdbus6 org.kde.KWin /Scripting/Script$SID org.kde.kwin.Script.stop >/dev/null 2>&1
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript halwin >/dev/null 2>&1
echo "screens: $(kscreen-doctor -o 2>/dev/null | grep -E 'Output|Geometry|enabled' | tr -s ' ' | tr '\n' ' ' | cut -c1-200)"
echo "audio streams now:"
pw-dump 2>/dev/null | python3 -c "
import json,sys
for n in json.load(sys.stdin):
    p=n.get('info',{}).get('props',{})
    if p.get('media.class')=='Stream/Output/Audio': print('  stream app=%s node=%s state=%s' % (p.get('application.name'), p.get('node.name'), n.get('info',{}).get('state')))" 2>/dev/null | head -6
echo "pad: $(grep -o 'js=[^ ]*' ~/.local/state/deck/killemall128.log | tail -1)"
wait $LP 2>/dev/null; echo "live run ended rc=$? (124 = killed by timeout as planned)"
pkill -x zesarux 2>/dev/null; sleep 0.5; pgrep -x zesarux >/dev/null && echo "WARN zesarux still running" || echo "no zesarux left"
grep -iE "sdl|error|cannot|fail|fullscreen|video" ~/.local/state/deck/killemall128.log | grep -viE "kidding" | tail -4 | cut -c1-150
date -u +%H:%M:%SZ
