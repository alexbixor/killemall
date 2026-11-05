#!/usr/bin/env python3
"""m29_next_flow.py - find the NextZXOS key flow that starts killemall.nex in headless ZEsarUX TBBlue, saving a screen after every
stage: boot wait -> SPACE x3 (welcome pages: SPACE = Start NextZXOS) -> ENTER (Browser) -> CAPS+6 x N -> ENTER. Prints PC after
each stage; PNGs build/m29_nf_<stage>.png. usage: m29_next_flow.py [boot_s] [downs]"""
import sys, time, pathlib, shutil, subprocess, re, random, socket, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image
from run48 import zrcp, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOT = float(sys.argv[1]) if len(sys.argv) > 1 else 22.0; DOWNS = int(sys.argv[2]) if len(sys.argv) > 2 else 16
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"; MMC = ROOT / "build/tbblue_nf.mmc"; NEX = ROOT / "build/killemall128.nex"
shutil.copyfile(MMC_SRC, MMC)
port = 10700 + random.randint(0, 80)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
       "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit",
       "--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked", "--enable-mmc",
       "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex"]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_nf.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(160):
    try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def shot(name):
    bmp = "/tmp/nf_%s.bmp" % name; q("save-screen " + bmp, 0.6)
    if os.path.exists(bmp):
        Image.open(bmp).convert("RGB").save(ROOT / "build" / ("m29_nf_%s.png" % name))
    print("  [%s] PC %04x -> build/m29_nf_%s.png" % (name, pc(), name), flush=True)
def tap(keys, hold=0.2, gap=0.5):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
from m29_nextboot import boot_to_game
t0 = time.time()
ok = boot_to_game(q, tap, pc, log=lambda m: print(m, flush=True))
print("boot_to_game ->", ok, "after %.0f s" % (time.time() - t0)); shot("4_game_menu")
for k in (("SPACE",), ("ENTER",), ("SPACE",)):
    tap(k, 0.25, 1.5); shot("5_start_" + k[0])
    if 0x8000 <= pc() < 0xC000: break
time.sleep(2); shot("6_game")
print("elapsed %.0f s, final PC %04x" % (time.time() - t0, pc()))
q("exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
