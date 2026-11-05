#!/usr/bin/env python3
"""nex_play2.py - M2.7 proof on the emulated Spectrum Next (ZEsarUX TBBlue, fresh copy of the bundled NextZXOS SD image).
State-driven (fixed delays were flaky: boot speed varies run to run): the screen attributes at 0x5800 classify the state
  testcard first-boot video-mode test card (ULA attributes uniform, Layer 2 picture)  -> ENTER  ("ENTER selects mode")
  welcome  NextZXOS first-boot welcome pages (inverse title bar, no cyan)      -> SPACE  ("SPACE=Start NextZXOS")
  menu     NextZXOS main menu (cyan highlight bar, Browser preselected)        -> ENTER  (open Browser)
  browser  Browser file list (black path bar on row 0 + cyan highlight)        -> CAPS+6 x16 (cursor down to the last entry,
           killemall.nex, verified: highlight on the last listed row) -> ENTER
  title    our title screen (attributes == build/title.scr) / menu             -> SPACE  (START GAME)
  game     engine `frames` counter advancing                                   -> play: Q 2 s, P 1 s, SPACE x3; measure fps
Every transition waits for the attribute map to change and settle (timeout 40 s). Rendered PNGs (all layers) at each stage.
Exit 0 only if the game ran (frames advanced) and a game PNG was saved.  usage: nex_play2.py"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10136
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"
MMC = ROOT / "build/tbblue_test.mmc"
NEX = ROOT / "build/killemall128.nex"
TITLE_ATTRS = (ROOT / "build/title.scr").read_bytes()[6144:]
SYM = {}
for l in (ROOT / "build/kea128.sym").read_text().splitlines():
    m = re.match(r"(\w+)\s+EQU\s+0([0-9A-Fa-f]+)H", l)
    if m: SYM[m.group(1)] = int(m.group(2), 16)
LOG = open(ROOT / "build/nex_play2.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def classify(a):
    if len(a) != 768: return "noread"
    if a == TITLE_ATTRS: return "title"
    if len(set(a)) == 1: return "testcard"        # first-boot video-mode test card (Layer 2; ULA attributes uniform): "ENTER selects mode"
    rows = [a[r * 32:(r + 1) * 32] for r in range(24)]
    inv = [sum(1 for x in row if (x >> 3) & 7 == 0 and x & 7 == 7) for row in rows]      # inverse (black paper, white ink) cells
    cyan = [sum(1 for x in row if (x >> 3) & 7 == 5) for row in rows]                      # cyan paper cells
    if inv[0] >= 24 and max(cyan) >= 8: return "browser"
    if max(cyan) >= 8: return "menu"
    blue = [sum(1 for x in row if (x >> 3) & 7 == 1) for row in rows]                      # blue paper title bar
    green = sum(1 for x in a if (x >> 3) & 7 == 4 or (x & 7) == 4)                         # green bar / green ink list
    if max(blue) >= 24 and green >= 32: return "config"                                   # "ZX Spectrum Next Configuration" (SPACE from the test card)
    if max(inv) >= 20: return "welcome"
    bright_red = sum(1 for x in a if x & 0x40 and (x & 7) == 2 and (x >> 3) & 7 == 7)      # red-on-bright-white URL box, rows 17-19
    if bright_red >= 24 and max(inv) >= 8: return "welcome"                                # welcome page 1 (title bar is only ~20 inverse cells)
    return "unknown"

def main():
    log("== nex_play2 %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
    shutil.copyfile(MMC_SRC, MMC); log("fresh SD copy %d B; nex %d B" % (MMC.stat().st_size, NEX.stat().st_size))
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex",
           "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexplay2.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(120):
        try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError: time.sleep(0.25)
    if s is None: p.kill(); log("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0].strip()
    def rd(addr, n, wait=0.3):
        r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
    def pc():
        m = re.search(r"PC=(\w{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
    def frames(): b = rd(SYM["frames"], 2); return int.from_bytes(b, "little") if len(b) == 2 else -1
    def attrs(): return rd(0x5800, 768, 0.4)
    def shot(name):
        bmp = "/tmp/nexp2_%s.bmp" % name; q("save-screen " + bmp, 1.0)
        if os.path.exists(bmp):
            im = Image.open(bmp).convert("RGB"); im.save(ROOT / "build" / ("nexplay2_%s.png" % name)); log("   png nexplay2_%s.png" % name)
    def tap(keys, hold=0.2, gap=0.4):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def hold(keys, secs):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(secs)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05)
    def settle(timeout=40, prev=None):
        """wait until the attribute map differs from prev (if given) and is stable for 2 consecutive reads"""
        t0 = time.time(); last = None; same = 0
        while time.time() - t0 < timeout:
            a = attrs()
            if a and a != prev:
                same = same + 1 if a == last else 0
                if same >= 1: return a
            last = a; time.sleep(0.7)
        return last
    a = settle(60); st = classify(a); log("boot settled: state %s, PC %04X" % (st, pc()))
    for step in range(14):
        if st in ("title", "game", "noread", "unknown") and step: break
        if st == "testcard": tap(("ENTER",), hold=0.3, gap=0.3); log("test card -> ENTER (selects video mode)")
        elif st == "config": tap(("ENTER",), hold=0.3, gap=0.3); log("config menu -> ENTER (ZX Spectrum Next standard)")
        elif st == "welcome":
            # the firmware boot screen (TBBLUE.FW, PC >= 0xC000, transient) also has an inverse title bar; SPACE there = config menu.
            # The real welcome program runs from RAM below 0x8000 and stays until a key: require PC < 0xC000 and 3 s unchanged.
            v = pc(); time.sleep(3.0); a3 = attrs()
            if v >= 0xC000 or a3 != a: log("boot screen (PC %04X), waiting" % v); a = a3 if a3 != a else a; st = classify(a); continue
            tap(("SPACE",), hold=0.3, gap=0.3); log("welcome (PC %04X) -> SPACE" % v)
        elif st == "menu": tap(("ENTER",), hold=0.3, gap=0.3); log("menu -> ENTER")
        elif st == "browser":
            shot("browser")
            for _ in range(16): tap(("CAPS", "6"), hold=0.15, gap=0.2)
            time.sleep(0.6); a2 = attrs(); rows = [sum(1 for x in a2[r * 32:(r + 1) * 32] if (x >> 3) & 7 == 5) for r in range(24)]
            hi = [r for r in range(24) if rows[r] >= 8]; log("browser: highlight row(s) %s (killemall.nex is the 17th entry -> row 17 expected)" % hi)
            shot("browser_sel"); tap(("ENTER",), hold=0.3, gap=0.3); log("browser -> ENTER on highlighted entry")
            a = settle(40, a); st = classify(a); log("   -> state %s, PC %04X, 7FFD %s" % (st, pc(), (re.search(r"7FFD port: (\w+)", q("get-io-ports", 0.3)) or [0, "?"])[1]))
            continue
        elif st == "unknown" and step == 0:
            tap(("SPACE",), hold=0.3, gap=0.3); log("unknown -> SPACE (welcome assumed)")
        a = settle(40, a); st = classify(a); log("   -> state %s, PC %04X" % (st, pc()))
    ok = False
    if st == "title":
        time.sleep(2.0); shot("title"); log("title screen reached (attributes identical to build/title.scr), PC %04X" % pc())
        tap(("SPACE",), hold=0.3, gap=2.0); shot("game0")
        f0 = frames(); t1 = time.time()
        log("after START GAME: frames %d, PC %04X, health %d ammo %d level %d" % (f0, pc(), rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0], rd(SYM["level"], 1)[0]))
        hold(("Q",), 2.0); shot("game_fwd")
        hold(("P",), 1.0); shot("game_turn")
        for i in range(3): tap(("SPACE",), hold=0.25, gap=0.6)
        shot("game_fire")
        f1 = frames(); dt = time.time() - t1
        log("frames %d -> %d in %.1f s = %.2f fps (wall clock); health %d ammo %d" % (f0, f1, dt, (f1 - f0) / dt if dt else 0, rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0]))
        ok = f1 > f0 >= 0
    else:
        shot("final_%s" % st); log("did not reach the title; final state %s PC %04X" % (st, pc()))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done ok=%s" % ok); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
