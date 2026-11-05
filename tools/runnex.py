#!/usr/bin/env python3
"""runnex.py - M2.7 (3 Nov 2026): boot the .nex in ZEsarUX's Spectrum Next (TBBlue) machine over ZRCP and prove it runs.
Uses a COPY of tools/zesarux/tbblue.mmc (NextZXOS SD image, 64 MB) so the pristine image is never written; the .nex is copied
into the image root with --copy-file-to-mmc and started through NextZXOS's own autoexec (we write autoexec.bas? no: simplest
reliable path = type the command in the NextZXOS Browser is not scriptable, so this script pokes the keyboard: at the NextZXOS
"Browser" the F key filter is not needed; we use the BASIC editor path: ESC to BASIC, type .nexload killemall128.nex, ENTER).
Evidence logged: PC in the engine range, frames counter advancing, 7FFD value, title/menu/game PNGs, fps over 4 s.
usage: runnex.py [build/killemall128.nex]"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
from fe_shot import ports
from test48 import SYM

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10131
NEX = str(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "build/killemall128.nex").resolve())
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"
MMC = ROOT / "build/tbblue_test.mmc"
LOG = open(ROOT / "build/runnex.out", "a")

def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def main():
    log("== runnex %s %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), NEX))
    if not MMC.exists() or MMC.stat().st_size != MMC_SRC.stat().st_size:
        shutil.copyfile(MMC_SRC, MMC); log("copied pristine tbblue.mmc -> %s (%d B)" % (MMC, MMC.stat().st_size))
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", NEX, "killemall.nex",
           "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    log("cmd:", " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_runnex.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(120):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); log("no ZRCP"); log(open("/tmp/zes_runnex.log").read()[-2000:]); sys.exit(1)
    zrcp(s, "", 0.5)
    def regs(): return zrcp(s, "get-registers", 0.2).split("command>")[0].strip().replace("\n", " ")
    def pc():
        m = re.search(r"PC=([0-9a-fA-F]{4})", regs()); return int(m.group(1), 16) if m else -1
    def rd(addr, n, wait=0.3):
        r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
    def grab_png(name):
        scr = rd(16384, 6912, 1.5)
        if len(scr) == 6912: scr_to_png(scr, str(ROOT / "build" / name)); log("png", name)
        return scr
    def tap_keys(keys=(), joy=0, hold=0.12, gap=0.25):
        zrcp(s, "set-ui-io-ports " + ports(keys, joy), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def type_text(text):
        for ch in text:
            if ch == " ": tap_keys(("SPACE",))
            elif ch == ".": tap_keys(("SYM", "M"))
            elif ch.isdigit(): tap_keys((ch,))
            elif ch.isalpha(): tap_keys((ch.upper(),))
            else: log("cannot type", repr(ch))
    log("machine:", zrcp(s, "get-current-machine", 0.3).split("command>")[0].strip())
    # NextZXOS boot takes several seconds (emulated); wait for the Browser / BASIC prompt by watching the screen settle
    t0 = time.time(); last = None; stable = 0
    while time.time() - t0 < 60 and stable < 4:
        scr = rd(16384, 6912, 1.0); stable = stable + 1 if scr == last else 0; last = scr; time.sleep(1.0)
    log("boot screen settled after %.0f s (stable %d), PC %04X" % (time.time() - t0, stable, pc()))
    grab_png("nex_boot.png")
    # NextZXOS boot menu -> ESC/EDIT? The default boot opens the Browser. ESC drops to NextBASIC. Type the loader command.
    tap_keys(("CAPS", "1"), hold=0.2, gap=1.0)          # EDIT = CAPS SHIFT + 1: Browser -> NextBASIC
    grab_png("nex_after_edit.png")
    type_text(".nexload killemall.nex"); tap_keys(("ENTER",), hold=0.2, gap=3.0)
    grab_png("nex_after_cmd.png")
    t0 = time.time(); started = False
    while time.time() - t0 < 40:
        v = pc()
        if 0x8000 <= v < 0xC000: started = True; break
        time.sleep(0.5)
    log("engine running after %.1f s: %s | %s" % (time.time() - t0, started, regs()[:80]))
    time.sleep(1.5); grab_png("nex_title.png")
    for k in (("SPACE",), ("ENTER",), ("SPACE",)):
        tap_keys(keys=k, hold=0.25, gap=1.2)
        fr = int.from_bytes(rd(SYM["frames"], 2), "little") if started else 0
        log("after %s: frames %d | %s" % (k[0], fr, regs()[:40]))
        if fr: break
    time.sleep(1.0); grab_png("nex_game.png")
    if started:
        f0 = int.from_bytes(rd(SYM["frames"], 2), "little"); t1 = time.time(); time.sleep(4.0)
        f1 = int.from_bytes(rd(SYM["frames"], 2), "little"); dt = time.time() - t1
        log("fps: frames %d -> %d in %.2f s = %.2f fps" % (f0, f1, dt, (f1 - f0) / dt))
        log("level_data byte0 %s health %s level %s" % (rd(SYM["level_data"], 1).hex(), rd(SYM["health"], 1).hex(), rd(SYM["level"], 1).hex()))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done started=%s" % started)
    sys.exit(0 if started else 1)

if __name__ == "__main__":
    main()
