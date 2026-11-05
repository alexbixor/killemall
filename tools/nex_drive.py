#!/usr/bin/env python3
"""nex_drive.py - M2.7: drive the emulated Spectrum Next (ZEsarUX TBBlue, test SD copy) with a timed key script and save the
RENDERED screen (save-screen bmp -> png, all layers) after every step.  Steps: "<secs>:<key>" (wait, then tap the key; key names
from fe_shot.KEY, '+' combines, 'shot' = only screenshot, 'text=..' types letters/digits/space/dot).  Logs PC, SP, 7FFD, nreg 03/15.
usage: nex_drive.py tag 20:ENTER 15:shot 5:SPACE ...      -> build/nexd_<tag>_<n>_<key>.png, build/nex_drive.out"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10134
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"
MMC = ROOT / "build/tbblue_test.mmc"
NEX = ROOT / "build/killemall128.nex"
TAG = sys.argv[1]; STEPS = sys.argv[2:]
LOG = open(ROOT / "build/nex_drive.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def main():
    log("== nex_drive %s tag %s steps %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), TAG, STEPS))
    if "fresh" in TAG or not MMC.exists(): shutil.copyfile(MMC_SRC, MMC); log("fresh SD copy")
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex",
           "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexdrive.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
    def state(tag):
        r = q("get-registers", 0.2).replace("\n", " ")
        m = re.search(r"PC=(\w{4}) SP=(\w{4})", r)
        io = q("get-io-ports", 0.3); m7 = re.search(r"7FFD port: (\w+)", io)
        log("   [%s] PC %s SP %s | 7FFD %s | nreg03 %s nreg15 %s | pages %s" % (tag, m.group(1) if m else "?", m.group(2) if m else "?",
            m7.group(1) if m7 else "?", q("tbblue-get-register 3", 0.15)[:3], q("tbblue-get-register 21", 0.15)[:3],
            q("get-memory-pages", 0.2).replace("\n", " ")[:60]))
    def shot(name):
        bmp = "/tmp/nexd_%s.bmp" % name; q("save-screen " + bmp, 1.0)
        if os.path.exists(bmp):
            im = Image.open(bmp).convert("RGB"); png = ROOT / "build" / ("nexd_%s_%s.png" % (TAG, name)); im.save(png)
            log("   png", png.name, im.size, len(im.getcolors(1 << 20) or []), "colours")
    def tap(keys, hold=0.15, gap=0.3):
        zrcp(s, "set-ui-io-ports " + ports(tuple(keys)), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    for i, st in enumerate(STEPS):
        secs, key = st.split(":", 1); time.sleep(float(secs))
        if key == "shot": pass
        elif key.startswith("text="):
            for ch in key[5:]:
                if ch == " ": tap(("SPACE",))
                elif ch == ".": tap(("SYM", "M"))
                elif ch == "/": tap(("SYM", "V"))
                elif ch == '"': tap(("SYM", "P"))
                else: tap((ch.upper(),))
        else: tap(key.split("+"), hold=0.2, gap=0.5)
        log("step %d: waited %s then %s" % (i, secs, key)); state("%d_%s" % (i, key[:12])); shot("%d_%s" % (i, re.sub(r"[^A-Za-z0-9]", "", key)[:12]))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done")

if __name__ == "__main__":
    main()
