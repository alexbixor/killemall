#!/usr/bin/env python3
"""nex_diag.py - M2.7 diagnostics: watch the emulated Spectrum Next boot (ZEsarUX TBBlue) for N seconds over ZRCP, logging PC,
ULA screen fill, attribute fill, Next register 0x15 (layer enable), the 7FFD/1FFD ports and a PNG every 10 s. Optional key
sequence after boot. usage: nex_diag.py [seconds] [keys...]  (keys: names from fe_shot.KEY, e.g. SPACE ENTER CAPS+1)"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
from fe_shot import ports

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10132
MMC = ROOT / "build/tbblue_test.mmc"
SECS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
KEYS = sys.argv[2:]
LOG = open(ROOT / "build/nex_diag.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def main():
    log("== nex_diag %s secs %d keys %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), SECS, KEYS))
    if not MMC.exists(): shutil.copyfile(pathlib.Path(ZES).parent / "tbblue.mmc", MMC)
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports",
           "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexdiag.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
        m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
    log("help tbblue:", " | ".join(l.strip() for l in q("help", 0.5).splitlines() if "tbblue" in l.lower() or "screen" in l.lower())[:600])
    t0 = time.time(); k = 0; keys_sent = False
    while time.time() - t0 < SECS:
        scr = rd(16384, 6912, 1.0)
        pix = sum(1 for b in scr[:6144] if b) if scr else -1; att = len(set(scr[6144:])) if scr else -1
        r15 = q("tbblue-get-register 15", 0.2) if k == 0 or k % 3 == 0 else "-"
        pg = q("get-memory-pages", 0.2).replace("\n", " ")[:120]
        io = q("get-io-ports", 0.2); m7 = re.search(r"7FFD port: (\w+)", io); m1 = re.search(r"1FFD port: (\w+)", io)
        log("t+%3.0fs PC %04X | lit bytes %d / 6144, distinct attrs %d | nreg15 %s | 7FFD %s 1FFD %s | pages %s" % (
            time.time() - t0, pc(), pix, att, r15.replace("\n", " ")[:40], m7.group(1) if m7 else "?", m1.group(1) if m1 else "?", pg))
        if k % 5 == 0 and scr: scr_to_png(scr, str(ROOT / "build" / ("nexdiag_%02d.png" % k)))
        if KEYS and not keys_sent and time.time() - t0 > 20:
            for key in KEYS:
                ks = tuple(key.split("+"))
                zrcp(s, "set-ui-io-ports " + ports(ks), 0.05); time.sleep(0.15)
                zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(0.8)
                log("sent key", key, "PC %04X" % pc())
            keys_sent = True
        k += 1; time.sleep(2.0)
    log("final regs:", q("get-registers", 0.2).replace("\n", " ")[:120])
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done")

if __name__ == "__main__":
    main()
