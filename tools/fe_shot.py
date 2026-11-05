#!/usr/bin/env python3
"""fe_shot.py - run build/fe_test.tap headless in ZEsarUX (48k) and grab PNGs of the T2 front end through ZRCP:
build/fe_menu.png (main menu, cursor moved to DETAIL and toggled to LOW so the bar + flashing cell are visible) and
build/fe_redefine.png (redefine screen after two keys were given).  Keys are injected with `set-ui-io-ports` (8 keyboard
rows + Kempston byte, see `help set-ui-io-ports`), so the exact rows/bits the code reads are exercised - no ASCII mapping.
Also reads the hex dump the test build prints after START and compares it with the option/in_keys bytes read by ZRCP.
usage: fe_shot.py [build/fe_test.tap]   env LOADWAIT (default 8 s)"""
import socket, subprocess, time, os, sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10143
ROWS = ["\x03ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\x02LKJH", "\x01\x04MNB"]
KEY = {ch: (r, b) for r, row in enumerate(ROWS) for b, ch in enumerate(row)}
KEY.update({"CAPS": (0, 0), "ENTER": (6, 0), "SPACE": (7, 0), "SYM": (7, 1)})
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/fe_test.sym").read_text(), re.M)}

def ports(keys=(), joy=0):
    rows = [0xFF] * 8
    for k in keys:
        r, b = KEY[k]; rows[r] &= ~(1 << b) & 0xFF
    return "".join("%02X" % v for v in rows) + "%02X" % joy

def main():
    tap = str(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "build/fe_test.tap").resolve())
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_feshot.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    # wait until the tape has loaded and the code runs: the menu loop halts at fe_loop+1, so PC spends its time in the
    # ISR / menu code (>= 32768) instead of the ROM loader. Poll up to LOADWAIT (default 40 s).
    t0 = time.time(); started = False
    while time.time() - t0 < float(os.environ.get("LOADWAIT", "40")):
        r = zrcp(s, "get-registers", 0.2)
        m = re.search(r"PC=([0-9a-fA-F]{4})", r)
        if m and int(m.group(1), 16) >= 0x8000:
            started = True; break
        time.sleep(0.5)
    print("program running after %.1f s: %s" % (time.time() - t0, started))
    time.sleep(1.0)
    def tap_keys(keys=(), joy=0, hold=0.12, gap=0.25):
        zrcp(s, "set-ui-io-ports " + ports(keys, joy), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def grab():
        r = zrcp(s, "read-memory 16384 6912", 1.2)
        hexs = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        return bytes.fromhex(hexs[:13824]) if len(hexs) >= 13824 else b""
    def rd(addr, n):
        r = zrcp(s, "read-memory %d %d" % (addr, n), 0.3)
        return "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * n].upper()
    print("regs:", zrcp(s, "get-registers", 0.3).strip().splitlines()[0][:100])
    print("fe_cur", rd(SYM["fe_cur"], 1), "opt bytes", rd(SYM["opt_music"], 5))
    tap_keys(["6"]); tap_keys(["6"]); tap_keys(["6"])          # cursor down x3 -> DETAIL
    tap_keys(["SPACE"])                                        # toggle -> LOW
    print("after 3x down + SPACE: fe_cur", rd(SYM["fe_cur"], 1), "opt bytes", rd(SYM["opt_music"], 5))
    scr = grab()
    if scr:
        scr_to_png(scr, str(ROOT / "build/fe_menu.png")); print("saved build/fe_menu.png")
    tap_keys(["6"]); tap_keys(["6"]); tap_keys(["6"])          # -> REDEFINE KEYS
    tap_keys(["SPACE"], hold=0.15, gap=0.5)
    tap_keys(["W"], hold=0.2, gap=0.5); tap_keys(["S"], hold=0.2, gap=0.5)
    scr = grab()
    if scr:
        scr_to_png(scr, str(ROOT / "build/fe_redefine.png")); print("saved build/fe_redefine.png")
    print("fe_tmpk", rd(SYM["fe_tmpk"], 16))
    for k in ["A", "D", "ENTER", "SPACE", "N", "M"]:
        tap_keys([k], hold=0.2, gap=0.5)
    print("in_keys after redefine", rd(SYM["in_keys"], 16))
    # joystick: Kempston up should move the cursor only when opt_joy = 1 -> set CONTROLS: KEMPSTON first (row 5)
    tap_keys(["7"]); tap_keys(["SPACE"])                       # up to CONTROLS, toggle -> KEMPSTON
    tap_keys(joy=0x08); tap_keys(joy=0x08)                     # joystick up x2 -> SOUND FX... (6 -> 5 -> 4)
    print("after KEMPSTON + joy up x2: fe_cur", rd(SYM["fe_cur"], 1), "opt_joy", rd(SYM["opt_joy"], 1))
    for _ in range(3):
        tap_keys(joy=0x08)                                     # 3 -> 0 = START GAME
    print("fe_cur before START", rd(SYM["fe_cur"], 1))
    tap_keys(joy=0x10, hold=0.15, gap=0.8)                     # fire = START
    scr = grab()
    if scr:
        scr_to_png(scr, str(ROOT / "build/fe_started.png")); print("saved build/fe_started.png")
    opt = rd(SYM["opt_music"], 5); keys = rd(SYM["in_keys"], 16)
    print("memory: opt", opt, "in_keys", keys)
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    (ROOT / "build/fe_shot_scr.bin").write_bytes(scr)

if __name__ == "__main__":
    main()
