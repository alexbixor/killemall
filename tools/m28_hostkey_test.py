#!/usr/bin/env python3
"""m28_hostkey_test.py - reproduce "strafe, X Z, still does not work" (Alex 20:20Z 3 Nov 2026) through the Deck's REAL input
path instead of ZRCP matrix injection. On the Deck the keys travel Moonlight -> Sunshine -> libvirtualhid Keyboard -> XWayland
-> ZEsarUX (--vo xwindows) while the Steam virtual pad sits attached and idle on --realjoystickpath with the launcher's
--joystickkeybt table (left stick X axis -> keys z / x). Here: Xvfb X server, ZEsarUX 13.0 (same build as the Deck) with the
launcher's exact joystick arguments, a uinput clone of the pad (PAD=1, default) or no pad (PAD=0, control), host keys sent
with xdotool (XTEST = real X key events). For every key: Spectrum keyboard matrix while held (get-ui-io-ports) and player
position/angle before and after. Then the pad itself: L1 / R1 buttons and left stick X. Appends to build/m28_hostkey.out."""
import os, re, sys, time, pathlib, socket, subprocess, shlex
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = os.environ.get("TAP", str(ROOT / "build/killemall48_m25.tap"))
PAD = os.environ.get("PAD", "1") == "1"
DISP = os.environ.get("XVFB_DISPLAY", ":77")
PORT = int(os.environ.get("ZRCP_PORT", "10178"))
out = open(ROOT / "build/m28_hostkey.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); out.write(s + "\n"); out.flush()
log("== m28_hostkey_test %s tap=%s PAD=%d" % (time.strftime("%H:%M:%SZ", time.gmtime()), os.path.basename(TAP), PAD))
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}

# ---- X server
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sock = "/tmp/.X11-unix/X" + DISP[1:]
for _ in range(50):
    if os.path.exists(sock): break
    time.sleep(0.1)
env = dict(os.environ, DISPLAY=DISP)
if os.environ.get("XKB_LAYOUT"):   # mimic the Deck: KDE layout list gr,us -> Xwayland keymap groups [gr, us]
    subprocess.run(["setxkbmap", "-layout", os.environ["XKB_LAYOUT"]], env=env, check=False)
    log("host X keyboard layout set to:", os.environ["XKB_LAYOUT"])
def xdo(*a):
    return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)

# ---- virtual pad (same capability set as the Steam virtual 'Microsoft X-Box 360 pad 0', 28de:11ff)
ui = None; js = None
if PAD:
    from evdev import UInput, AbsInfo, ecodes as e
    caps = {e.EV_KEY: [e.BTN_A, e.BTN_B, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR],
            e.EV_ABS: [(e.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)), (e.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                       (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)), (e.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                       (e.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)), (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
                       (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)), (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0))]}
    ui = UInput(caps, name="Microsoft X-Box 360 pad 0", vendor=0x28de, product=0x11ff, version=1)
    time.sleep(1.0)
    for d in sorted(pathlib.Path("/sys/class/input").glob("js*")):
        if (d / "device/name").read_text().strip() == "Microsoft X-Box 360 pad 0":
            js = "/dev/input/" + d.name
    log("virtual pad:", js)

# ---- joystick arguments verbatim from the Deck launcher
args = []
if PAD:
    for line in (ROOT / "tools/deck/launch-killemall.sh").read_text().splitlines():
        s = line.strip().rstrip("\\").strip()
        if s.startswith("--joystick") or s.startswith("--cleareventlist"):
            args += shlex.split(s)
    args = [js if a in ('"$JS"', "$JS") else a for a in args]
cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)] + args + [TAP]
zlog = open("/tmp/zes_hostkey.log", "w")
p = subprocess.Popen(cmd, stdout=zlog, stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); xvfb.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)

def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2))
    return int(m.group(1), 16) if m else -1
def rd(addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.3)
    h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
def rd16(a):
    b = rd(a, 2); return b[0] | (b[1] << 8)
def pos():
    return rd16(SYM["posx"]), rd16(SYM["posy"]), rd(SYM["angle"], 1)[0]
ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]
def matrix():
    r = zrcp(s, "get-ui-io-ports", 0.2)
    m = re.search(r"\b([0-9A-Fa-f]{18})\b", r)
    if not m: return "?", 0
    hx = m.group(1).upper(); keys = []
    for row in range(8):
        v = int(hx[2 * row:2 * row + 2], 16)
        for b in range(5):
            if not v & (1 << b):
                keys.append({"\x01": "SPACE", "\x02": "ENTER", "\x03": "CAPS", "\x04": "SYM"}.get(ROWS[row][b], ROWS[row][b]))
    return "+".join(keys) or "-", int(hx[16:18], 16)

t0 = time.time()
while time.time() - t0 < 90 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600):
    time.sleep(0.5)
log("menu reached after %.1f s (pc=%04X)" % (time.time() - t0, pc()))

# ---- X window focus (no window manager on Xvfb: set input focus directly)
wid = ""
for _ in range(20):
    r = xdo("search", "--onlyvisible", "--name", ".")
    ids = [w for w in r.stdout.split() if w.isdigit()]
    if ids: wid = ids[-1]; break
    time.sleep(0.5)
log("X window id:", wid or "NONE", "| names:", " / ".join(xdo("getwindowname", w).stdout.strip() for w in ids[:3]))
xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "200", "150"); time.sleep(0.3)
log("focused window:", xdo("getwindowfocus").stdout.strip())

def hold_key(k, secs=0.6):
    xdo("keydown", k); time.sleep(0.15); mx = matrix(); time.sleep(secs - 0.15); xdo("keyup", k); time.sleep(0.25); return mx
def show(tag, a, b, mx):
    log("%-18s matrix while held: %-10s joy=%02X | posx %.3f->%.3f (%+.3f) posy %.3f->%.3f (%+.3f) angle %d->%d" % (
        tag, mx[0], mx[1], a[0] / 256, b[0] / 256, (b[0] - a[0]) / 256, a[1] / 256, b[1] / 256, (b[1] - a[1]) / 256, a[2], b[2]))

# start the game with the host SPACE key (menu: SPACE selects START GAME); read the matrix while it is held
xdo("keydown", "space"); time.sleep(0.15); mx_sp = matrix(); time.sleep(0.2); xdo("keyup", "space"); time.sleep(2.0)
f0 = rd16(SYM["frames"]); time.sleep(0.5); f1 = rd16(SYM["frames"])
log("SPACE held: matrix %s joy=%02X -> frames %d -> %d (%s), pc=%04X" % (mx_sp[0], mx_sp[1], f0, f1, "render loop running" if f1 > f0 else "menu still up", pc()))
if f1 <= f0:
    xdo("keydown", "Return"); time.sleep(0.15); mx_en = matrix(); time.sleep(0.2); xdo("keyup", "Return"); time.sleep(2.0)
    f0 = rd16(SYM["frames"]); time.sleep(0.5); f1 = rd16(SYM["frames"])
    log("ENTER held: matrix %s joy=%02X -> frames %d -> %d (%s), pc=%04X" % (mx_en[0], mx_en[1], f0, f1, "render loop running" if f1 > f0 else "menu still up", pc()))
log("in game: frames %d -> %d (render loop %s), health %d" % (f0, f1, "running" if f1 > f0 else "NOT running", rd(SYM["health"], 1)[0]))

log("-- host keyboard keys via X11 (XTEST), pad %s" % ("attached+idle" if PAD else "absent"))
for k, name in (("q", "Q forward"), ("a", "A back"), ("o", "O turn L"), ("z", "Z strafe L"), ("x", "X strafe R"), ("z", "Z again")):
    a = pos(); mx = hold_key(k); b = pos(); show(name, a, b, mx)
if PAD:
    log("-- pad inputs via the launcher table (L1/R1 -> z/x keys, left stick X -> z/x keys)")
    def pad_hold(evs_down, evs_up, secs=0.6):
        for t, c, v in evs_down: ui.write(t, c, v)
        ui.syn(); time.sleep(0.15); mx = matrix(); time.sleep(secs - 0.15)
        for t, c, v in evs_up: ui.write(t, c, v)
        ui.syn(); time.sleep(0.25); return mx
    for name, dn, up in (("L1 (strafe L)", [(e.EV_KEY, e.BTN_TL, 1)], [(e.EV_KEY, e.BTN_TL, 0)]),
                         ("R1 (strafe R)", [(e.EV_KEY, e.BTN_TR, 1)], [(e.EV_KEY, e.BTN_TR, 0)]),
                         ("stick left", [(e.EV_ABS, e.ABS_X, -30000)], [(e.EV_ABS, e.ABS_X, 0)]),
                         ("stick right", [(e.EV_ABS, e.ABS_X, 30000)], [(e.EV_ABS, e.ABS_X, 0)]),
                         ("stick up (fwd)", [(e.EV_ABS, e.ABS_Y, -30000)], [(e.EV_ABS, e.ABS_Y, 0)])):
        a = pos(); mx = pad_hold(dn, up); b = pos(); show(name, a, b, mx)
    log("-- host key Z once more after the pad was used")
    a = pos(); mx = hold_key("z"); b = pos(); show("Z after pad", a, b, mx)
    log("-- host key Z while the stick is pushed RIGHT (x) at the same time")
    ui.write(e.EV_ABS, e.ABS_X, 30000); ui.syn(); time.sleep(0.1)
    a = pos(); mx = hold_key("z"); b = pos(); show("Z + stick right", a, b, mx)
    ui.write(e.EV_ABS, e.ABS_X, 0); ui.syn(); time.sleep(0.2)
zlog.flush()
txt = open("/tmp/zes_hostkey.log").read()
hits = [l for l in txt.splitlines() if re.search(r"joystick|realjoy|keyb|key ", l, re.I)]
log("zesarux log lines about joystick/keys: %d" % len(hits))
for l in hits[:12]: log("   " + l[:150])
try: zrcp(s, "exit-emulator", 0.3)
except Exception: pass
try: p.wait(5)
except subprocess.TimeoutExpired: p.kill()
if ui: ui.close()
xvfb.kill()
log("== done %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
