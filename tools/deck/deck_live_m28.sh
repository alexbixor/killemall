#!/bin/bash
# deck_live_m28.sh - runs ON the Deck via 'bash -s'. Alex approved ("yes go", 3 Nov). Live Z/X experiment on the REAL path:
# start the 128K game with the launcher's exact arguments (plus a local-only ZRCP port so we can read the Spectrum keyboard
# matrix), in the Plasma session (Xwayland), then type keys from a uinput keyboard (kernel -> libinput -> KWin -> Xwayland ->
# ZEsarUX, same as Sunshine's virtual keyboard). For each key: matrix while held + player position. Kills the game at the end.
# Touches no files except /tmp; launchers and tapes unchanged.
set -u
VO="$(cat /tmp/hal_vo 2>/dev/null || echo --vo xwindows)"; echo "video args: $VO"; export VO
echo "deck $(date -u +%H:%M:%SZ)"
pgrep -x zesarux >/dev/null && { echo "ABORT: a game is already running"; exit 3; }
eval "$(systemctl --user show-environment | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR)=' | sed 's/^/export /')"
echo "env DISPLAY=${DISPLAY:-?} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-?}"
cat > /tmp/hal_live_m28.py <<'EOF'
import os, re, sys, time, socket, subprocess, glob
from evdev import UInput, ecodes as e
ROMS = os.path.expanduser("~/Emulation/roms/zxspectrum")
TAP = max(glob.glob(ROMS + "/killemall128_*.tap"), key=os.path.getmtime)
SYM = dict(fe_run=0xEA68, frames=0x85D0, posx=0x85D2, posy=0x85D4, angle=0x85D6)
PORT = 10199
def log(*a): print(time.strftime("%H:%M:%S", time.gmtime()), *a, flush=True)
log("tape", os.path.basename(TAP))
js = "/dev/input/js0"
for j in sorted(glob.glob("/dev/input/js*")):
    n = open("/sys/class/input/%s/device/name" % os.path.basename(j)).read()
    if any(k in n for k in ("X-Box", "Steam", "Xbox")): js = j; break
L = open(os.path.expanduser("~/.local/bin/launch-killemall128")).read()
import shlex
args = []
for line in L.splitlines():
    s = line.strip().rstrip("\\").strip()
    if s.startswith("--joystick") or s.startswith("--cleareventlist"): args += shlex.split(s)
args = [js if a == "$JS" else a for a in args]
Z = os.path.expanduser("~/Applications/zesarux")
VO = os.environ.get("VO", "--vo xwindows").split()
cmd = ["./zesarux", "--noconfigfile", "--machine", "128k"] + VO + ["--ao", "null", "--zoom", "3", "--hidemousepointer",
       "--nosplash", "--nowelcomemessage", "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol",
       "--remoteprotocol-port", str(PORT)] + args + [TAP]
env = dict(os.environ, LD_LIBRARY_PATH=Z + "/libs")
kb = UInput({e.EV_KEY: [e.KEY_Q, e.KEY_A, e.KEY_O, e.KEY_P, e.KEY_Z, e.KEY_X, e.KEY_M, e.KEY_SPACE, e.KEY_ENTER,
                        e.KEY_UP, e.KEY_DOWN, e.KEY_LEFT, e.KEY_RIGHT]}, name="hal test keyboard")
time.sleep(0.5)
p = subprocess.Popen(cmd, cwd=Z, env=env, stdout=open("/tmp/hal_live_zes.log", "w"), stderr=subprocess.STDOUT)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if not s: log("no ZRCP"); p.kill(); sys.exit(2)
def z(c, w=0.25):
    s.sendall((c + "\n").encode()); time.sleep(w); out = b""; s.settimeout(1.5)
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            out += d
            if out.rstrip().endswith(b"command>"): break
    except socket.timeout: pass
    return out.decode(errors="replace")
z("", 0.3)
def rd(a, n):
    h = "".join(c for c in z("read-memory %d %d" % (a, n)) if c in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
def rd16(a): b = rd(a, 2); return b[0] | b[1] << 8
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", z("get-registers")); return int(m.group(1), 16) if m else -1
def pos(): return rd16(SYM["posx"]) / 256, rd16(SYM["posy"]) / 256, rd(SYM["angle"], 1)[0]
ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]
def matrix():
    m = re.search(r"\b([0-9A-Fa-f]{18})\b", z("get-ui-io-ports"))
    if not m: return "?"
    hx = m.group(1); k = []
    for r in range(8):
        v = int(hx[2 * r:2 * r + 2], 16)
        for b in range(5):
            if not v & (1 << b): k.append({"\x01": "SPACE", "\x02": "ENTER", "\x03": "CAPS", "\x04": "SYM"}.get(ROWS[r][b], ROWS[r][b]))
    return "+".join(k) or "-"
t0 = time.time()
while time.time() - t0 < 60 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
log("menu after %.1f s" % (time.time() - t0))
def hold(code, secs=0.6):
    kb.write(e.EV_KEY, code, 1); kb.syn(); time.sleep(0.2); mx = matrix(); time.sleep(secs - 0.2)
    kb.write(e.EV_KEY, code, 0); kb.syn(); time.sleep(0.3); return mx
time.sleep(1.0)
mx = hold(e.KEY_SPACE, 0.4); time.sleep(2.0)
f0 = rd16(SYM["frames"]); time.sleep(0.5); f1 = rd16(SYM["frames"])
log("SPACE matrix %s -> frames %d->%d (%s)" % (mx, f0, f1, "IN GAME" if f1 > f0 else "menu still up"))
for code, name in ((e.KEY_Q, "Q fwd"), (e.KEY_Z, "Z strafe L"), (e.KEY_X, "X strafe R"), (e.KEY_UP, "UP arrow"),
                   (e.KEY_LEFT, "LEFT arrow"), (e.KEY_RIGHT, "RIGHT arrow"), (e.KEY_Z, "Z again"), (e.KEY_X, "X again")):
    a = pos(); mx = hold(code); b = pos()
    log("%-12s matrix while held: %-8s pos (%.2f,%.2f)->(%.2f,%.2f) d=(%+.2f,%+.2f) angle %d->%d" % (
        name, mx, a[0], a[1], b[0], b[1], b[0] - a[0], b[1] - a[1], a[2], b[2]))
try: z("exit-emulator", 0.3)
except Exception: pass
try: p.wait(5)
except subprocess.TimeoutExpired: p.kill()
kb.close()
log("done; zesarux exit", p.returncode)
EOF
VO="${VO:---vo xwindows}" timeout 150 python3 -u /tmp/hal_live_m28.py 2>&1
pkill -x zesarux 2>/dev/null; sleep 0.5
pgrep -fa zesarux | grep -v pgrep | head -1 || echo "no zesarux left"
grep -viE "just kidding|licen|copyright|warranty|^$" /tmp/hal_live_zes.log | tail -8 | cut -c1-140
date -u +%H:%M:%SZ
