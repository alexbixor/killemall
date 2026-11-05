#!/bin/bash
# deck_watch_m28.sh - runs ON the Deck ('bash -s'). Alex approved (21:3xZ 3 Nov: "2 yes"). Starts a READ-ONLY 20-minute
# input watcher (root transient unit hal-kea-keys, needs root to read the built-in keyboards) that logs, with the Deck's
# timestamps, key/button/stick events from every keyboard and pad device (incl. Sunshine's lazily created virtual devices,
# re-scanned every 2 s) ONLY WHILE a zesarux process is running (so nothing he types in Slack etc. is recorded). No grab,
# no writes to any device, no change to the game or launchers. Log: /tmp/hal-kea-keys.log (root-owned, world-readable).
set -u
echo "deck time $(date -u +%H:%M:%SZ)"
echo "--- streaming / game state now (read-only)"
~/.local/bin/sunshine-stream-hook status 2>/dev/null | head -3
pgrep -fa zesarux | grep -v pgrep | cut -c1-120 | head -2 || echo "no zesarux running"
grep -E "CLIENT CONNECTED|CLIENT DISCONNECTED|Executing" ~/.config/sunshine/sunshine.log 2>/dev/null | tail -3
echo "--- KDE keyboard layouts configured (kxkbrc)"
grep -E "^(LayoutList|Use|DisplayNames)" ~/.config/kxkbrc 2>/dev/null || echo "kxkbrc: no layout list (default = system layout)"
cat > /tmp/hal_kea_keys.py <<'EOF'
import os, struct, select, time, glob
KEYS = {16:"Q",30:"A",24:"O",25:"P",44:"Z",45:"X",50:"M",57:"SPACE",28:"ENTER",42:"LSHIFT",54:"RSHIFT",29:"LCTRL",1:"ESC",63:"F5",
        21:"Y",304:"BTN_A",305:"BTN_B",307:"BTN_X",308:"BTN_Y",310:"L1",311:"R1",314:"SELECT",315:"START",316:"GUIDE",317:"LSTICK",318:"RSTICK"}
AXES = {0:"left-stick X",1:"left-stick Y",3:"right-stick X",4:"right-stick Y",16:"dpad X",17:"dpad Y"}
PAT = ("Keyboard","keyboard","X-Box","Xbox","Steam Controller","Gamepad","gamepad","Controller","Joystick")
SKIP = ("Mouse","Touchscreen","Pen Tablet")
fds = {}; opened = set(); axis_state = {}
def scan():
    for p in sorted(glob.glob("/dev/input/event*")):
        if p in opened: continue
        try: n = open("/sys/class/input/%s/device/name" % os.path.basename(p)).read().strip()
        except OSError: continue
        if any(k in n for k in PAT) and not any(k in n for k in SKIP):
            try:
                fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK); fds[fd] = "%s[%s]" % (os.path.basename(p), n); opened.add(p)
                print(ts(), "opened", fds[fd], flush=True)
            except OSError as e: print(ts(), "cannot open", p, n, e, flush=True); opened.add(p)
def ts(): t = time.time(); return time.strftime("%H:%M:%S", time.gmtime(t)) + ".%03d" % int((t % 1) * 1000)
def game():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open("/proc/%s/comm" % d).read().strip() == "zesarux":
                    cmd = open("/proc/%s/cmdline" % d, "rb").read().split(b"\0")
                    tape = [c.decode(errors="replace") for c in cmd if c.endswith(b".tap")]
                    return d, (os.path.basename(tape[0]) if tape else "?")
            except OSError: pass
    return None
scan(); print(ts(), "watcher up; logging only while zesarux runs", flush=True)
g = game(); print(ts(), "game running:" if g else "no game running yet", g or "", flush=True)
last_scan = last_game = time.time(); nkeys = 0
while True:
    r, _, _ = select.select(list(fds), [], [], 0.5)
    now = time.time()
    if now - last_game >= 1.0:
        g2 = game(); last_game = now
        if bool(g2) != bool(g): print(ts(), ("GAME STARTED pid %s tape %s" % g2) if g2 else "GAME ENDED (%d key events logged)" % nkeys, flush=True); nkeys = 0
        g = g2
    if now - last_scan >= 2.0: scan(); last_scan = now
    for fd in r:
        try: data = os.read(fd, 24 * 64)
        except OSError:
            print(ts(), "device gone:", fds.pop(fd, "?"), flush=True); continue
        if not g: continue
        for i in range(0, len(data) - 23, 24):
            sec, usec, typ, code, val = struct.unpack("llHHi", data[i:i + 24])
            t = time.strftime("%H:%M:%S", time.gmtime(sec)) + ".%03d" % (usec // 1000)
            if typ == 1 and val in (0, 1):
                nkeys += 1; print(t, fds[fd], KEYS.get(code, "key%d" % code), "down" if val else "up", flush=True)
            elif typ == 3 and code in AXES and "Keyboard" not in fds[fd]:
                if code in (16, 17): b = val
                else: b = -1 if val < -16000 else (1 if val > 16000 else 0)
                if axis_state.get((fd, code)) != b:
                    axis_state[(fd, code)] = b; print(t, fds[fd], AXES[code], {-1: "NEG(left/up)", 0: "centre", 1: "POS(right/down)"}[b], flush=True)
EOF
sudo -n systemctl stop hal-kea-keys.service 2>/dev/null
sudo -n systemd-run --unit hal-kea-keys --collect -p RuntimeMaxSec=1200 \
  bash -c 'exec /usr/bin/python3 -u /tmp/hal_kea_keys.py > /tmp/hal-kea-keys.log 2>&1' && sleep 2
echo "unit: $(sudo -n systemctl is-active hal-kea-keys.service) (stops by itself after 20 min)"
cat /tmp/hal-kea-keys.log
date -u +%H:%M:%SZ
