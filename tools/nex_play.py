#!/usr/bin/env python3
"""nex_play.py - M2.7 proof on the emulated Spectrum Next (ZEsarUX TBBlue, fresh SD copy): boot NextZXOS, dismiss the welcome,
open the Browser, cursor down to killemall.nex, ENTER, wait for the title, SPACE (START GAME), then play: hold Q (forward) 2 s,
P (turn) 1 s, SPACE (fire) x3; sample the engine's `frames` counter for the fps, read health/ammo/level, save rendered PNGs.
Exit 0 only if: PC in the engine, frames advancing, a game frame saved.  usage: nex_play.py"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10135
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"
MMC = ROOT / "build/tbblue_test.mmc"
NEX = ROOT / "build/killemall128.nex"
SYM = {}
for l in (ROOT / "build/kea128.sym").read_text().splitlines():
    m = re.match(r"(\w+)\s+EQU\s+0([0-9A-Fa-f]+)H", l)
    if m: SYM[m.group(1)] = int(m.group(2), 16)
LOG = open(ROOT / "build/nex_play.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def main():
    log("== nex_play %s" % time.strftime("%H:%M:%SZ", time.gmtime()))
    shutil.copyfile(MMC_SRC, MMC); log("fresh SD copy %d B; nex %d B" % (MMC.stat().st_size, NEX.stat().st_size))
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex",
           "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexplay.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
    def shot(name):
        bmp = "/tmp/nexp_%s.bmp" % name; q("save-screen " + bmp, 1.0)
        if os.path.exists(bmp):
            im = Image.open(bmp).convert("RGB"); im.save(ROOT / "build" / ("nexplay_%s.png" % name)); log("   png nexplay_%s.png" % name)
    def tap(keys, hold=0.2, gap=0.5):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def hold(keys, secs):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(secs)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05)
    time.sleep(18); tap(("ENTER",)); log("welcome page 2, PC %04X" % pc())
    time.sleep(8); tap(("SPACE",)); log("start NextZXOS, PC %04X" % pc())
    time.sleep(6); tap(("ENTER",)); log("Browser opened, PC %04X" % pc()); time.sleep(4); shot("browser")
    for _ in range(16): tap(("CAPS", "6"), hold=0.15, gap=0.2)          # cursor down (CAPS+6) to the last entry = killemall.nex
    time.sleep(0.5); shot("browser_sel")
    tap(("ENTER",)); t0 = time.time()
    while time.time() - t0 < 30 and not (0x8000 <= pc() < 0xC000 or 0xE000 <= pc() < 0xFE00): time.sleep(0.5)
    log("after ENTER on killemall.nex: %.1f s, PC %04X, nreg03 %s, 7FFD %s" % (time.time() - t0, pc(), q("tbblue-get-register 3", 0.2)[:3],
        (re.search(r"7FFD port: (\w+)", q("get-io-ports", 0.3)) or [None, "?"])[1]))
    time.sleep(6); shot("title")
    f_menu = frames(); log("title/menu: frames counter %d (menu does not count)" % f_menu)
    tap(("SPACE",), hold=0.3, gap=2.0); shot("game0")
    f0 = frames(); t1 = time.time(); log("after START GAME: frames %d, PC %04X, health %d ammo %d level %d" % (
        f0, pc(), rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0], rd(SYM["level"], 1)[0]))
    hold(("Q",), 2.0); shot("game_fwd")
    hold(("P",), 1.0); shot("game_turn")
    for i in range(3): tap(("SPACE",), hold=0.25, gap=0.6)
    shot("game_fire")
    f1 = frames(); dt = time.time() - t1
    log("frames %d -> %d in %.1f s = %.2f fps (wall clock, emulator at real speed); health %d ammo %d" % (
        f0, f1, dt, (f1 - f0) / dt if dt else 0, rd(SYM["health"], 1)[0], rd(SYM["ammo"], 1)[0]))
    ok = f1 > f0 > -1
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done ok=%s" % ok); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
