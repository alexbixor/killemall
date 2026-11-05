#!/usr/bin/env python3
"""nex_probe.py - M2.7 diagnostics 2: boot ZEsarUX TBBlue with the test SD image, then after N seconds: ZRCP help for save-screen,
save the RENDERED screen (what a user sees: ULA + Layer 2 + tilemap) to a file, dump ROM bytes at 0, 0x38, 0x66, memory
0x4000..0x7FFF non-zero ranges, Next registers 03 05 12 15 69 6B 6E 6F, machine/paging text; optional keys, then repeat.
usage: nex_probe.py seconds [keys...]"""
import socket, subprocess, time, os, sys, pathlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
from fe_shot import ports

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10133
MMC = ROOT / "build/tbblue_test.mmc"
SECS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
KEYS = sys.argv[2:]
LOG = open(ROOT / "build/nex_probe.out", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()

def main():
    log("== nex_probe %s secs %d keys %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), SECS, KEYS))
    if not MMC.exists(): shutil.copyfile(pathlib.Path(ZES).parent / "tbblue.mmc", MMC)
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "TBBlue", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked",
           "--enable-mmc", "--mmc-file", str(MMC), "--enable-divmmc-ports",
           "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nexprobe.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
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
    log("help save-screen:", q("help save-screen", 0.4).replace("\n", " | ")[:400])
    log("help tbblue-get-register:", q("help tbblue-get-register", 0.4).replace("\n", " | ")[:300])
    def snapshot(tag):
        log("--", tag, "regs:", q("get-registers", 0.2).replace("\n", " ")[:150])
        log("   machine:", q("get-current-machine", 0.2), "| paging:", q("get-paging-state", 0.2).replace("\n", " ")[:200])
        log("   ROM 0000:", rd(0, 16).hex(), "0038:", rd(0x38, 8).hex(), "0066:", rd(0x66, 8).hex())
        m = rd(0x4000, 0x4000, 2.0)
        if m:
            nz = [i for i in range(0, 0x4000, 256) if any(m[i:i + 256])]
            log("   0x4000..0x7FFF non-zero 256-B pages: %d -> %s" % (len(nz), ["%04X" % (0x4000 + i) for i in nz][:40]))
        for r in (0x03, 0x05, 0x07, 0x12, 0x15, 0x69, 0x6B, 0x6E, 0x6F, 0x50, 0x51, 0x52, 0x53):
            log("   nreg %02X = %s" % (r, q("tbblue-get-register %d" % r, 0.15).replace("\n", " ")[:30]))
        out = "/tmp/nex_%s.bmp" % tag
        log("   save-screen ->", q("save-screen " + out, 1.0).replace("\n", " ")[:200])
        for ext in (".bmp", ".pbm", ".png", ""):
            f = pathlib.Path(out if ext == ".bmp" else out[:-4] + ext)
            if f.exists(): log("   file", f, f.stat().st_size, "B")
        scr = rd(16384, 6912, 1.5)
        if len(scr) == 6912: scr_to_png(scr, str(ROOT / "build" / ("nexprobe_%s.png" % tag)))
    time.sleep(SECS); snapshot("t%d" % SECS)
    for key in KEYS:
        ks = tuple(key.split("+"))
        zrcp(s, "set-ui-io-ports " + ports(ks), 0.05); time.sleep(0.2)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(2.0)
        log("sent key", key); snapshot("key_" + key.replace("+", "_"))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done")

if __name__ == "__main__":
    main()
