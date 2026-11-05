#!/bin/bash
# deck_watch_m28_read.sh - READ-ONLY: print the watcher log and the latest game launch lines. Runs ON the Deck (bash -s).
set -u
echo "deck time $(date -u +%H:%M:%SZ)  unit: $(sudo -n systemctl is-active hal-kea-keys.service 2>/dev/null)"
echo "--- /tmp/hal-kea-keys.log ($(wc -l < /tmp/hal-kea-keys.log) lines)"
cat /tmp/hal-kea-keys.log
echo "--- newest launch lines"
tail -2 ~/.local/state/deck/killemall.log 2>/dev/null | cut -c1-150
tail -2 ~/.local/state/deck/killemall128.log 2>/dev/null | cut -c1-150
echo "--- zesarux now"
pgrep -fa zesarux | grep -v pgrep | cut -c1-100 | head -1 || echo "none"
echo "--- sunshine.log tail (input-related + connect)"
grep -iE "CLIENT|gamepad|controller|keyboard|input|created" ~/.config/sunshine/sunshine.log 2>/dev/null | tail -6 | cut -c1-160
