#!/usr/bin/env python3
"""m28_xmode_diag2.py - X11 mode: the menu did not accept SPACE. Read fe_prev / fe_cur / in_break / opt_joy / fe_keys result
in the menu with nothing pressed, and the raw io ports. Compares --vo xwindows (Xvfb) against --vo null in one run.
Appends to build/m28_hostkey.out."""
import os, re, sys, time, pathlib, socket, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from t6_zes import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
TAP = str(ROOT / "build/killemall48_m25.tap")
out = open(ROOT / "build/m28_hostkey.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); out.write(s + "\n"); out.flush()
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M)}

def run(vo, disp, port):
    log("== m28_xmode_diag2 vo=%s %s" % (vo, time.strftime("%H:%M:%SZ", time.gmtime())))
    env = dict(os.environ)
    xvfb = None
    if vo == "xwindows":
        xvfb = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if os.path.exists("/tmp/.X11-unix/X" + disp[1:]): break
            time.sleep(0.1)
        env["DISPLAY"] = disp
    cmd = [ZES, "--noconfigfile", "--vo", vo, "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--quickexit", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), TAP]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_xdiag2_%s.log" % vo, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
    s = None
    for _ in range(80):
        try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
        except OSError: time.sleep(0.25)
    if s is None: p.kill(); xvfb and xvfb.kill(); log("no ZRCP"); return
    zrcp(s, "", 0.5)
    def pc():
        m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
    def rd(a, n):
        r = zrcp(s, "read-memory %d %d" % (a, n), 0.3); h = "".join(c for c in r if c in "0123456789ABCDEFabcdef")[:2 * n]
        return bytes.fromhex(h) if len(h) == 2 * n else b"\0" * n
    t0 = time.time()
    while time.time() - t0 < 90 and not (SYM["fe_run"] <= pc() < SYM["fe_run"] + 0x600): time.sleep(0.5)
    log("menu after %.1f s" % (time.time() - t0))
    for _ in range(3):
        io = zrcp(s, "get-ui-io-ports", 0.2); m = re.search(r"\b([0-9A-Fa-f]{18})\b", io)
        log("  idle: io-ports %s  fe_prev %02X fe_cur %d in_break %d opt_joy %d  pc %04X" % (
            m.group(1) if m else io.strip()[:40], rd(SYM["fe_prev"], 1)[0], rd(SYM["fe_cur"], 1)[0], rd(SYM["in_break"], 1)[0], rd(SYM["opt_joy"], 1)[0], pc()))
        time.sleep(0.4)
    # what does the Spectrum itself read on the keyboard rows? (in_keys row FE..7F via a tiny ZRCP read of port state is not
    # available, so use the menu: hold SPACE via ZRCP and watch fe_prev)
    zrcp(s, "set-ui-io-ports " + ports(["SPACE"]), 0.05); time.sleep(0.3)
    log("  SPACE held (ZRCP): fe_prev %02X in_break %d frames %d" % (rd(SYM["fe_prev"], 1)[0], rd(SYM["in_break"], 1)[0], rd(SYM["frames"], 2)[0]))
    zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(1.5)
    log("  after release: frames %d pc %04X" % (rd(SYM["frames"], 2)[0] | rd(SYM["frames"], 2)[1] << 8, pc()))
    try: zrcp(s, "exit-emulator", 0.3)
    except Exception: pass
    try: p.wait(5)
    except subprocess.TimeoutExpired: p.kill()
    if xvfb: xvfb.kill()
    txt = open("/tmp/zes_xdiag2_%s.log" % vo).read()
    odd = [l for l in txt.splitlines() if re.search(r"error|warn|cannot|fail|joystick|keyboard", l, re.I) and "kidding" not in l]
    log("  log oddities: %d %s" % (len(odd), " | ".join(x[:80] for x in odd[:4])))

run("null", "", 10180)
run("xwindows", ":79", 10181)
log("== done")
