#!/usr/bin/env python3
"""m_mouse_hw.py (lane M, 5 Nov 2026) - oracle C: the real emulated-mouse path. ZEsarUX 128K with --enablekempstonmouse,
--vo xwindows under Xvfb (recipe: tools/m28_xmode_diag.py), the 128K tape with mouse look (build/killemall128_m.tap):
 1 menu: Q (up, wraps to the last item = MOUSE: OFF), SPACE (-> ON), screenshot M_menu_main.png, A (down, wraps to START), SPACE.
 2 in game: xdotool mousemove_relative in known steps right then left; after each step read mouse_last (the X counter the game
   saw) and angle over ZRCP: angle must follow the counter by +counts/4 (MSHIFT 6) to the right, -counts/4 to the left;
   prints the emulator's sensitivity (counts per pixel) it measured.
 3 opt_mouse := 0 (ZRCP write, the menu value), same moves: angle must not change at all.
 4 opt_mouse := 1, left click -> ammo 50 -> 49 (fire via the latch), right button held -> in_bits b5 (use/open via the latch).
 5 BREAK -> pause menu (8 rows incl. MOUSE) screenshot M_menu_pause.png; RESUME.
usage: timeout 500 .venv/bin/python tools/m_mouse_hw.py > build/night/M_hw.out 2>&1 ; exit 0 = every check passed."""
# Pitfall (M_hw_diag.out): in --vo xwindows mode ZRCP set-ui-io-ports keys reach the game ~2 s late while XTEST keys are
# immediate, so every key AFTER the game started goes through xdotool (shift = CAPS SHIFT); the main menu keeps ZRCP.
import os, re, sys, time, pathlib, socket, subprocess, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/killemall128_m.tap")); DISP = ":81"; PORT = 10181
SENS = int(os.environ.get("MSENS_EMU", "1"))                 # ZEsarUX --kempstonmouse-sens
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea128.sym").read_text(), re.M)}
fails = []
def log(*a): print(" ".join(str(x) for x in a), flush=True)
def check(ok, msg):
    log(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)
subprocess.run(["pkill", "-f", "Xvfb %s" % DISP], capture_output=True)
xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "4000x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists("/tmp/.X11-unix/X" + DISP[1:]): break
    time.sleep(0.1)
env = dict(os.environ, DISPLAY=DISP)
def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--quickexit", "--enablekempstonmouse", "--kempstonmouse-sens", str(SENS), "--zoom", "3",
       "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), TAP]
log("== m_mouse_hw %s  tape %s  emulator sens %d" % (time.strftime("%H:%M:%SZ", time.gmtime()), os.path.basename(TAP), SENS))
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_mhw.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); xvfb.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(addr, n=1):
    h = "".join(c for c in q("read-memory %d %d" % (addr, n), 0.15) if c in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
def rd8(name): return rd(SYM[name])[0]
def rd16(name): b = rd(SYM[name], 2); return b[0] | (b[1] << 8)
def wr8(name, v): q("write-memory %d %d" % (SYM[name], v), 0.1)
def tapk(keys, hold=0.25, gap=1.0):
    q("set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); q("set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
def xkey(keys, hold=0.3, gap=0.8):                      # XTEST route (in game / pause menu): keys = xdotool keysyms
    for k in keys: xdo("keydown", k)
    time.sleep(hold)
    for k in reversed(keys): xdo("keyup", k)
    time.sleep(gap)
def poll_until(pred, limit=2.5):
    t = time.time(); v = None
    while time.time() - t < limit:
        v = rd8("in_bits")
        if pred(v): return v, time.time() - t
        time.sleep(0.05)
    return v, limit
def shot(name):
    bmp = "/tmp/m_shot.bmp"
    if os.path.exists(bmp): os.remove(bmp)
    q("save-screen " + bmp, 0.4)
    if os.path.exists(bmp):
        from PIL import Image
        Image.open(bmp).convert("RGB").resize((768, 576), Image.NEAREST).save(str(ROOT / "build/night" / name)); return True
    return False
def done():
    try: q("exit-emulator", 0.3); s.close()
    except Exception: pass
    try: p.wait(5)
    except subprocess.TimeoutExpired: p.kill()
    xvfb.kill()
try:
    t0 = time.time()
    while time.time() - t0 < 120 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
    log("menu after %.1f s (PC %04X)" % (time.time() - t0, pc()))
    a = rd16("ticks"); time.sleep(2.0); b = rd16("ticks"); log("emulation speed in the menu: %.1f Hz (50 = real time)" % (((b - a) & 0xFFFF) / 2.0))
    ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]
    wid = ids[-1] if ids else ""
    geo = xdo("getwindowgeometry", wid).stdout.replace("\n", " ")
    xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "384", "288"); time.sleep(0.3)
    log("X window %s %s focused=%s" % (wid, geo, xdo("getwindowfocus").stdout.strip()))
    # 1 menu: MOUSE item = last of FE_N = 7 items (index 6): up from START wraps to it
    check(rd8("fe_count") == 7 and rd8("opt_mouse") == 0, "main menu fe_count %d (7 items), opt_mouse %d (default OFF)" % (rd8("fe_count"), rd8("opt_mouse")))
    tapk(("Q",)); check(rd8("fe_cur") == 6, "Q (up) from START wraps to item 6 = MOUSE (fe_cur %d)" % rd8("fe_cur"))
    tapk(("SPACE",)); check(rd8("opt_mouse") == 1, "SPACE toggles MOUSE: OFF -> ON (opt_mouse %d)" % rd8("opt_mouse"))
    check(shot("M_menu_main.png"), "screenshot build/night/M_menu_main.png (cursor on MOUSE: ON)")
    tapk(("A",)); check(rd8("fe_cur") == 0, "A (down) from MOUSE wraps to item 0 = START (fe_cur %d)" % rd8("fe_cur"))
    tapk(("SPACE",), 0.3, 2.0)
    f0 = rd16("frames"); time.sleep(1.0); f1 = rd16("frames")
    check(f1 > f0, "game started: frames %d -> %d" % (f0, f1))
    time.sleep(1.0)
    # 2 mouse moves: right then left, in known pixel steps; the pointer is re-centred before each step
    def move(dx):
        xdo("mousemove", "--window", wid, "384", "288"); time.sleep(0.15)
        a0, l0 = rd8("angle"), rd8("mouse_last")
        xdo("mousemove_relative", "--", str(dx), "0"); time.sleep(0.35)
        a1, l1 = rd8("angle"), rd8("mouse_last")
        loc = xdo("getmouselocation").stdout.strip()
        return a0, a1, (l1 - l0 + 128) % 256 - 128, loc
    log("step  pixels  counter_delta  angle_before -> after  (angle_delta)  expected = counts/4   pointer")
    tot_px = tot_cnt = 0; ok_dir = True; ok_mag = True
    for dx in (40, 80, 120, 200, -40, -80, -120, -200):
        a0, a1, dc, loc = move(dx)
        da = (a1 - a0 + 128) % 256 - 128
        exp = int(dc / 4) if dc >= 0 else -int(-dc / 4)         # whole units (the fraction carries over)
        log("      %5d  %6d         %3d -> %3d  (%+4d)  exp %+4d (+-1)   %s" % (dx, dc, a0, a1, da, exp, loc.split()[0] if loc else "?"))
        if dx > 0 and not (dc > 0 and da > 0): ok_dir = False
        if dx < 0 and not (dc < 0 and da < 0): ok_dir = False
        if abs(da - exp) > 1: ok_mag = False
        tot_px += abs(dx); tot_cnt += abs(dc)
    sens = tot_cnt / tot_px if tot_px else 0
    log("emulator sensitivity measured: %d counts for %d pixels = %.3f counts/pixel (--kempstonmouse-sens %d)" % (tot_cnt, tot_px, sens, SENS))
    check(ok_dir, "direction: right moves grow the counter and turn right (angle +), left moves turn left (angle -)")
    check(ok_mag, "magnitude: angle delta = counter delta / 4 (+-1 for the kept fraction) on every step")
    # 3 MOUSE OFF: nothing moves
    wr8("opt_mouse", 0); time.sleep(0.3)
    a0 = rd8("angle"); l0 = rd8("mouse_last")
    for dx in (200, -200, 150):
        xdo("mousemove", "--window", wid, "384", "288"); time.sleep(0.1); xdo("mousemove_relative", "--", str(dx), "0"); time.sleep(0.3)
    a1 = rd8("angle"); l1 = rd8("mouse_last")
    check(a0 == a1 and l0 == l1, "MOUSE: OFF (opt_mouse 0): 550 px of movement -> angle %d -> %d, mouse_last %d -> %d (unchanged)" % (a0, a1, l0, l1))
    wr8("opt_mouse", 1); time.sleep(0.5)          # back ON: the first frame re-bases on the moved counter (one jump, as after a menu)
    # 4 buttons
    am0 = rd8("ammo"); fc0 = rd8("fire_cool")
    xdo("mousedown", "1"); time.sleep(0.25); xdo("mouseup", "1"); time.sleep(0.6)
    am1 = rd8("ammo")
    check(am1 == am0 - 1, "left click -> fire: ammo %d -> %d (fire_cool before %d)" % (am0, am1, fc0))
    xdo("mousedown", "3"); v, lat = poll_until(lambda b: b & 0x20)
    check(bool(v & 0x20), "right button held -> in_bits b5 (use/open) seen by game_tick after %.2f s: in_bits %02X" % (lat, v))
    xdo("mouseup", "3"); v, lat = poll_until(lambda b: not (b & 0x30))
    check(not (v & 0x30), "released -> in_bits %02X after %.2f s (no fire/use bits left over)" % (v, lat))
    # 5 pause menu
    xkey(("shift", "space"), 0.6, 1.5)                   # BREAK = CAPS+SPACE
    check(rd8("fe_count") == 8 and rd8("fe_mode") == 1, "pause menu: fe_count %d (8 rows: RESUME..MOUSE, QUIT), fe_mode %d" % (rd8("fe_count"), rd8("fe_mode")))
    for _ in range(6): xkey(("a",), 0.25, 0.5)
    check(rd8("fe_cur") == 6, "6 x down -> item 6 = MOUSE (fe_cur %d)" % rd8("fe_cur"))
    check(shot("M_menu_pause.png"), "screenshot build/night/M_menu_pause.png (pause menu, 8 rows, cursor on MOUSE: ON)")
    for _ in range(6): xkey(("q",), 0.25, 0.5)
    check(rd8("fe_cur") == 0, "6 x up -> RESUME (fe_cur %d)" % rd8("fe_cur"))
    xkey(("space",), 0.3, 1.5)
    f0 = rd16("frames"); time.sleep(1.0); f1 = rd16("frames")
    check(f1 > f0, "RESUME: game running again (frames %d -> %d), angle %d" % (f0, f1, rd8("angle")))
    # 6 probe for the video recipe: does pointer motion OUTSIDE the emulator window still count? (window is ~1056 px wide)
    xdo("mousemove", "100", "288"); time.sleep(0.3); l0 = rd8("mouse_last"); row = []
    for x in range(500, 3901, 400):
        xdo("mousemove", str(x), "288"); time.sleep(0.3); l1 = rd8("mouse_last"); row.append("x%d:%+d" % (x, (l1 - l0 + 128) % 256 - 128)); l0 = l1
    log("probe: counter delta per 400 px pointer step (window 0..1056): %s" % " ".join(row))
finally:
    done()
log("RESULT", "PASS %d checks" % (len(fails) == 0 and 18 or 0) if not fails else "FAIL %d: %s" % (len(fails), "; ".join(fails)))
sys.exit(1 if fails else 0)
