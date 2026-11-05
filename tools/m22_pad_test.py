#!/usr/bin/env python3
"""m22_pad_test.py - prove the Deck launcher's pad mapping on hal-ec2 with ZEsarUX 13.0 (same build as the Deck).
Creates a uinput clone of the Steam virtual 'Microsoft X-Box 360 pad 0' (same axis/button set -> same joydev numbering),
launches ZEsarUX headless with EXACTLY the launcher's joystick arguments, loads killemall48_m22.tap, and checks via ZRCP
that each pad input lands as the expected Spectrum key / Kempston bit (get-ui-io-ports: 8 keyboard half-rows + joystick byte)
and that the game actually turns/fires (view angle / ammo bytes). Prints PASS/FAIL per mapping."""
import os, re, sys, time, pathlib, socket, subprocess, shlex
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from evdev import UInput, AbsInfo, ecodes as e

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = os.environ.get("PAD_TAP", str(ROOT / "build/killemall48_m23.tap"))   # M2.3 default (SPACE fires)
LAUNCHER = ROOT / "tools/deck/launch-killemall.sh"

# ---- virtual pad identical in capability set to the Deck's Steam virtual pad (abs 3003f = X Y Z RX RY RZ HAT0X HAT0Y)
caps = {
    e.EV_KEY: [e.BTN_A, e.BTN_B, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR],
    e.EV_ABS: [(e.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)), (e.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)),
               (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)), (e.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
               (e.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)), (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
               (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)), (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0))]}
ui = UInput(caps, name="Microsoft X-Box 360 pad 0", vendor=0x28de, product=0x11ff, version=1)
time.sleep(1.0)
js = None
for d in sorted(pathlib.Path("/sys/class/input").glob("js*")):
    if (d / "device/name").read_text().strip() == "Microsoft X-Box 360 pad 0":
        js = "/dev/input/" + d.name
if not js:
    sys.exit("virtual pad has no js node")
print("virtual pad:", js)

# ---- pull the joystick arguments verbatim from the launcher (single source of truth)
txt = LAUNCHER.read_text()
args = []
for line in txt.splitlines():
    s = line.strip().rstrip("\\").strip()
    if s.startswith("--joystick") or s.startswith("--cleareventlist"):
        args += shlex.split(s)
args = [js if a in ('"$JS"', "$JS") else a for a in args]
if os.environ.get("PAD_ARGS"):                      # probe mode: explicit argument list instead of the launcher's
    args = ["--realjoystickpath", js] + ([] if os.environ.get("PAD_KEEPEVENTS") else ["--cleareventlist"]) + shlex.split(os.environ["PAD_ARGS"])
assert "--realjoystickpath" in args, args
print("launcher joystick args:", len(args))

port = 10177
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol", "--remoteprotocol-port", str(port)] + args + [TAP]
log = open("/tmp/zes_padtest.log", "w")
p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(80):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)

def ports():
    r = zrcp(s, "get-ui-io-ports", 0.2)
    m = re.search(r"\b([0-9A-Fa-f]{18})\b", r)
    return m.group(1).upper() if m else r.strip()[:60]

def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2))
    return int(m.group(1), 16) if m else -1

t0 = time.time()
while time.time() - t0 < 60 and pc() < 0x8000:
    time.sleep(0.5)
print("game code running after %.1f s, idle ports %s" % (time.time() - t0, ports()))

ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]   # \x01 SPACE \x02 ENTER \x03 CAPS \x04 SYM
def pressed(hexports):
    out = []
    for r in range(8):
        v = int(hexports[2 * r:2 * r + 2], 16)
        for b in range(5):
            if not v & (1 << b):
                out.append({"\x01": "SPACE", "\x02": "ENTER", "\x03": "CAPS", "\x04": "SYM"}.get(ROWS[r][b], ROWS[r][b]))
    return out, int(hexports[16:18], 16)

def send(events):
    for code_type, code, val in events:
        ui.write(code_type, code, val)
    ui.syn(); time.sleep(0.35)

def axis(code, val):
    return [(e.EV_ABS, code, val)]

def btn(code, val):
    return [(e.EV_KEY, code, val)]

checks = [
    ("left stick up  -> joy Up (=Q)",    axis(e.ABS_Y, -30000), axis(e.ABS_Y, 0), ([], 0x08)),
    ("left stick down-> joy Down (=A)",  axis(e.ABS_Y, 30000),  axis(e.ABS_Y, 0), ([], 0x04)),
    ("left stick left-> Z (strafe L)",   axis(e.ABS_X, -30000), axis(e.ABS_X, 0), (["Z"], 0)),
    ("left stick right->X (strafe R)",   axis(e.ABS_X, 30000),  axis(e.ABS_X, 0), (["X"], 0)),
    ("right stick left-> joy Left (=O)", axis(e.ABS_RX, -30000), axis(e.ABS_RX, 0), ([], 0x02)),
    ("right stick right->joy Right(=P)", axis(e.ABS_RX, 30000),  axis(e.ABS_RX, 0), ([], 0x01)),
    ("d-pad up       -> Q",              axis(e.ABS_HAT0Y, -1), axis(e.ABS_HAT0Y, 0), (["Q"], 0)),
    ("d-pad down     -> A",              axis(e.ABS_HAT0Y, 1),  axis(e.ABS_HAT0Y, 0), (["A"], 0)),
    ("d-pad left     -> O",              axis(e.ABS_HAT0X, -1), axis(e.ABS_HAT0X, 0), (["O"], 0)),
    ("d-pad right    -> P",              axis(e.ABS_HAT0X, 1),  axis(e.ABS_HAT0X, 0), (["P"], 0)),
    ("A              -> SPACE (fire)",   btn(e.BTN_A, 1), btn(e.BTN_A, 0), (["SPACE"], 0)),
    ("B              -> joy Fire (=SPACE, fire too)", btn(e.BTN_B, 1), btn(e.BTN_B, 0), ([], 0x10)),
    ("X              -> M (open)",       btn(e.BTN_X, 1), btn(e.BTN_X, 0), (["M"], 0)),
    ("L1             -> Z",              btn(e.BTN_TL, 1), btn(e.BTN_TL, 0), (["Z"], 0)),
    ("R1             -> X",              btn(e.BTN_TR, 1), btn(e.BTN_TR, 0), (["X"], 0)),
    ("Y              -> ENTER",          btn(e.BTN_Y, 1), btn(e.BTN_Y, 0), (["ENTER"], 0)),
    ("START          -> CAPS",           btn(e.BTN_START, 1), btn(e.BTN_START, 0), (["CAPS"], 0)),
]
if os.environ.get("PAD_PROBE"):                     # probe mode: dump what every pad source produces, no expectations
    srcs = [("-0", axis(e.ABS_X, -30000), axis(e.ABS_X, 0)), ("+0", axis(e.ABS_X, 30000), axis(e.ABS_X, 0)),
            ("-1", axis(e.ABS_Y, -30000), axis(e.ABS_Y, 0)), ("+1", axis(e.ABS_Y, 30000), axis(e.ABS_Y, 0)),
            ("+2(LT)", axis(e.ABS_Z, 255), axis(e.ABS_Z, 0)),
            ("-3", axis(e.ABS_RX, -30000), axis(e.ABS_RX, 0)), ("+3", axis(e.ABS_RX, 30000), axis(e.ABS_RX, 0)),
            ("-4", axis(e.ABS_RY, -30000), axis(e.ABS_RY, 0)), ("+4", axis(e.ABS_RY, 30000), axis(e.ABS_RY, 0)),
            ("+5(RT)", axis(e.ABS_RZ, 255), axis(e.ABS_RZ, 0)),
            ("-6", axis(e.ABS_HAT0X, -1), axis(e.ABS_HAT0X, 0)), ("+6", axis(e.ABS_HAT0X, 1), axis(e.ABS_HAT0X, 0)),
            ("-7", axis(e.ABS_HAT0Y, -1), axis(e.ABS_HAT0Y, 0)), ("+7", axis(e.ABS_HAT0Y, 1), axis(e.ABS_HAT0Y, 0))] + \
           [("b%d" % i, btn(c, 1), btn(c, 0)) for i, c in enumerate([e.BTN_A, e.BTN_B, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR])]
    for name, down, up in srcs:
        send(down); held = pressed(ports()); send(up); rel = pressed(ports())
        print("%-7s held=%-10s joy=%02X  rel=%s joy=%02X" % (name, "+".join(held[0]) or "-", held[1], "+".join(rel[0]) or "-", rel[1]))
    zrcp(s, "exit-emulator", 0.3); p.kill(); ui.close(); sys.exit(0)

fails = 0
for name, down, up, want in checks:
    send(down); held = pressed(ports())
    send(up); rel = pressed(ports())
    ok = sorted(held[0]) == sorted(want[0]) and held[1] == want[1] and rel[0] == [] and rel[1] == 0
    fails += not ok
    print("%s  %-34s held=%-12s joy=%02X released=%s" % ("PASS" if ok else "FAIL", name, "+".join(held[0]) or "-", held[1], rel[0] or "-"))

# SELECT -> emulator menu: in headless mode ZEsarUX reports it cannot open the menu, which proves the event fired
send(btn(e.BTN_SELECT, 1)); send(btn(e.BTN_SELECT, 0)); time.sleep(0.3)
log.flush()
menu_evt = "menu" in open("/tmp/zes_padtest.log").read().lower()
print("%s  SELECT -> EscMenu event (log says menu requested: %s)" % ("PASS" if menu_evt else "FAIL", menu_evt))
fails += not menu_evt

# ---- end-to-end: the pad alone takes the game from the menu into play, turns, fires (reads angle/ammo from RAM)
def rd(addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.3)
    h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b""
sym = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}
t1 = time.time()
while time.time() - t1 < 60 and not (sym["fe_run"] <= pc() < sym["fe_run"] + 0x600):
    time.sleep(0.5)
print("menu reached: pc=%04X" % pc())
send(btn(e.BTN_B, 1)); time.sleep(0.15); send(btn(e.BTN_B, 0)); time.sleep(2.0)       # B = SPACE = START GAME
in_game = sym["game_tick"] <= pc() < sym["game_tick"] + 0x300 or pc() >= 0x8000 and not (sym["fe_run"] <= pc() < sym["fe_run"] + 0x600)
a0 = rd(sym["angle"], 1)[0]; am0 = rd(sym["ammo"], 1)[0]
send(axis(e.ABS_RX, 30000)); time.sleep(0.6); send(axis(e.ABS_RX, 0)); time.sleep(0.3)   # right stick right = P = turn right
a1 = rd(sym["angle"], 1)[0]
send(btn(e.BTN_A, 1)); time.sleep(0.2); send(btn(e.BTN_A, 0)); time.sleep(0.5)          # A = SPACE = fire
am1 = rd(sym["ammo"], 1)[0]
ok_game = in_game and a1 != a0 and am1 == am0 - 1
fails += not ok_game
print("%s  pad end-to-end: menu->game via B (in_game=%s), turn angle %d->%d, fire ammo %d->%d" % ("PASS" if ok_game else "FAIL", in_game, a0, a1, am0, am1))

zrcp(s, "exit-emulator", 0.3)
try:
    p.wait(5)
except subprocess.TimeoutExpired:
    p.kill()
ui.close()
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
