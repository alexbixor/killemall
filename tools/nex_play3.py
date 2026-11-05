#!/usr/bin/env python3
"""nex_play3.py - M2.7 proof on the emulated Spectrum Next (ZEsarUX TBBlue, fresh copy of the bundled NextZXOS SD image).
Lesson from nex_play2: NextZXOS draws its menus on the SHADOW screen (bank 7 paged at 0xC000), so reading 0x5800 sees a stale
picture. This version classifies the RENDERED frame (save-screen, all layers) by sampling the centre pixel of each 8x8 cell:
  testcard  >40 distinct colours (first-boot video-mode test card)                     -> ENTER
  config    blue title bar + green list ("ZX Spectrum Next Configuration")              -> ENTER (first entry = Next standard)
  welcome   grey paper, a black bar of >=20 cells, no cyan bar ("SPACE=Start NextZXOS")  -> SPACE   (acted on only after 3 s stable)
  menu      grey paper + a cyan bar row, row 0 not black (NextZXOS main menu)           -> ENTER (Browser is preselected)
  browser   row 0 black path bar + cyan bar                                              -> CAPS+6 x16 (down to killemall.nex) -> ENTER
  title     engine running: attributes at 0x5800 == title.scr                           -> SPACE (START GAME) -> play, measure fps
Exit 0 only if the engine's frames counter advanced.  usage: nex_play3.py"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10137
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"
MMC = ROOT / "build/tbblue_test.mmc"
NEX = ROOT / "build/killemall128.nex"
TITLE_ATTRS = (ROOT / "build/title.scr").read_bytes()[6144:]
SYM = {}
for l in (ROOT / "build/kea128.sym").read_text().splitlines():
    m = re.match(r"(\w+)\s+EQU\s+0([0-9A-Fa-f]+)H", l)
    if m: SYM[m.group(1)] = int(m.group(2), 16)
LOG = open(ROOT / "build/nex_play3.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

GREY = (182, 182, 182); BLACK = (0, 0, 0)
def is_cyan(c): return c[2] > 150 and c[1] > 150 and c[0] < 80
def is_blue(c): return c[2] > 150 and c[1] < 80 and c[0] < 80
def is_green(c): return c[1] > 150 and c[0] < 80 and c[2] < 80
def classify_img(im):
    """im: rendered 704x608 frame. ULA area 512x384 at (96,112), cells 16x16."""
    cells = [[im.getpixel((96 + cx * 16 + 8, 112 + r * 16 + 8)) for cx in range(32)] for r in range(24)]
    flat = [c for row in cells for c in row]
    if len(set(flat)) > 40: return "testcard"
    black = [sum(1 for c in row if c == BLACK) for row in cells]
    cyan = [sum(1 for c in row if is_cyan(c)) for row in cells]
    blue = [sum(1 for c in row if is_blue(c)) for row in cells]
    green = sum(1 for c in flat if is_green(c)); grey = sum(1 for c in flat if c == GREY)
    if max(blue) >= 20 and green >= 20: return "config"
    if black[0] >= 24 and max(cyan) >= 6: return "browser"
    if max(cyan) >= 6 and grey > 300: return "menu"
    if grey > 300 and max(black) >= 20: return "welcome"
    if sum(black) > 700: return "black"
    return "unknown"

def main():
    log("== nex_play3 %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
    shutil.copyfile(MMC_SRC, MMC); log("fresh SD copy %d B; nex %d B" % (MMC.stat().st_size, NEX.stat().st_size))
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex",
           "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexplay3.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
    def grab(name=None):
        bmp = "/tmp/nexp3.bmp"
        if os.path.exists(bmp): os.remove(bmp)
        q("save-screen " + bmp, 0.8)
        if not os.path.exists(bmp): return None
        im = Image.open(bmp).convert("RGB")
        if name: im.save(ROOT / "build" / ("nexplay3_%s.png" % name)); log("   png nexplay3_%s.png" % name)
        return im
    def state():
        im = grab()
        if im is None: return "noshot", None
        if rd(0x5800, 512, 0.4) == TITLE_ATTRS[:512] and 0x6C00 <= pc() < 0xFE00: return "title", im
        return classify_img(im), im
    def tap(keys, hold=0.2, gap=0.4):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def hold(keys, secs):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(secs)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05)
    time.sleep(10)
    t_start = time.time(); st = "boot"; n = 0; last = None; stable = 0; reached_title = False
    while time.time() - t_start < 240 and n < 60:
        st, im = state(); n += 1
        stable = stable + 1 if st == last else 0; last = st
        log("t+%3.0fs state %-9s PC %04X stable %d" % (time.time() - t_start, st, pc(), stable))
        if st == "testcard": tap(("ENTER",), hold=0.3, gap=1.0); stable = 0; continue
        if st == "config": grab("config"); tap(("ENTER",), hold=0.3, gap=1.0); stable = 0; continue
        if st == "welcome":
            if stable < 2: time.sleep(1.0); continue                     # 3 samples (~3 s) unchanged before acting
            grab("welcome"); tap(("SPACE",), hold=0.3, gap=1.0); stable = 0; continue
        if st == "menu": grab("menu"); tap(("ENTER",), hold=0.3, gap=1.5); stable = 0; continue
        if st == "browser":
            grab("browser")
            for _ in range(16): tap(("CAPS", "6"), hold=0.15, gap=0.2)
            time.sleep(0.6); im2 = grab("browser_sel")
            cells = [[im2.getpixel((96 + cx * 16 + 8, 112 + r * 16 + 8)) for cx in range(32)] for r in range(24)]
            hi = [r for r in range(24) if sum(1 for c in cells[r] if is_cyan(c)) >= 6]
            log("browser: cyan highlight row(s) %s (killemall.nex = 17th entry -> row 17 expected)" % hi)
            tap(("ENTER",), hold=0.3, gap=1.0); stable = 0
            t0 = time.time()
            while time.time() - t0 < 30 and not (rd(0x5800, 512, 0.4) == TITLE_ATTRS[:512]): time.sleep(0.7)
            log("after ENTER: %.1f s, PC %04X, 7FFD %s, nreg03 %s" % (time.time() - t0, pc(),
                (re.search(r"7FFD port: (\w+)", q("get-io-ports", 0.3)) or [0, "?"])[1], q("tbblue-get-register 3", 0.2)[:3]))
            continue
        if st == "title": reached_title = True; break
        time.sleep(1.5)
    ok = False
    if reached_title:
        time.sleep(1.5); grab("title"); log("TITLE reached: attribute rows 0..15 == title.scr (menu owns rows 16..23), PC %04X, 7FFD %s" % (pc(), (re.search(r"7FFD port: (\w+)", q("get-io-ports", 0.3)) or [0, "?"])[1]))
        tap(("SPACE",), hold=0.3, gap=2.5); grab("game0")
        f0 = frames(); t1 = time.time()
        log("after START GAME: frames %d, PC %04X, health %d ammo %d level %d" % (f0, pc(), rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0], rd(SYM["level"], 1)[0]))
        hold(("Q",), 2.0); grab("game_fwd")
        hold(("P",), 1.0); grab("game_turn")
        for i in range(3): tap(("SPACE",), hold=0.25, gap=0.6)
        grab("game_fire")
        f1 = frames(); dt = time.time() - t1
        log("frames %d -> %d in %.1f s = %.2f fps (wall clock incl. screenshot pauses); health %d ammo %d" % (
            f0, f1, dt, (f1 - f0) / dt if dt else 0, rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0]))
        def ticks(): b = rd(SYM["ticks"], 2); return int.from_bytes(b, "little") if len(b) == 2 else -1
        fa, ta = frames(), ticks(); time.sleep(4.0); fb, tb = frames(), ticks()
        log("clean sample 4.0 s: frames %d -> %d = %.2f fps; ticks (50 Hz interrupts) %d -> %d = %.1f/s; nreg07 (turbo) %s; nreg03 %s" % (
            fa, fb, (fb - fa) / 4.0, ta, tb, ((tb - ta) & 0xFFFF) / 4.0, q("tbblue-get-register 7", 0.2)[:3], q("tbblue-get-register 3", 0.2)[:3]))
        ok = f1 > f0 >= 0
    else:
        grab("final_%s" % st); log("did not reach the title; final state %s PC %04X" % (st, pc()))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done ok=%s" % ok); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
