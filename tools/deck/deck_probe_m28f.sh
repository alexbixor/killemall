#!/bin/bash
# deck_probe_m28f.sh - READ-ONLY, runs ON the Deck ('bash -s'). What INPUT DEVICE does the Moonlight session use?
# Sunshine creates virtual gamepads/keyboards/mice lazily (libvirtualhid "created ..."). List every creation since boot,
# every kernel input registration since boot, and the client names per session. Changes nothing.
set -u
echo "deck time $(date -u +%H:%MZ)"
echo "--- sunshine.log: every 'created' line (all device kinds) since 1 Nov"
grep -h -E "created|destroy|removed" ~/.config/sunshine/sunshine.log 2>/dev/null | grep -E "2026-11-0[1-3]" | cut -c1-120 | tail -30
echo "--- sunshine.log: client names/ids around session starts today"
grep -h -i -E "client|session started|launch|resume|Executing \[" ~/.config/sunshine/sunshine.log 2>/dev/null | grep "2026-11-03" | grep -v -i -E "disconnected" | cut -c1-140 | tail -24
echo "--- kernel: input device registrations since boot (virtual = libvirtualhid / X-Box / Xbox / gamepad)"
journalctl -k -b -o short-iso 2>/dev/null | grep -E "input: " | cut -c1-150 | tail -40
echo "--- the persistent libvirtualhid keyboard: capabilities (does it carry KEY_Z=44 / KEY_X=45?)"
for d in /sys/class/input/event8; do echo "$(cat $d/device/name): key bitmap = $(cat $d/device/capabilities/key)"; done
echo "--- Steam controller log tail (does Steam grab the virtual keyboard/gamepad?)"
tail -30 ~/.steam/steam/logs/controller_ui.log 2>/dev/null | grep -i -E "virtualhid|1209|28de|xbox|opened|closed|device" | cut -c1-160 | tail -12
date -u +%H:%MZ
