#!/usr/bin/env python3
"""m29b_slowmo.py - frame-exact slow-motion capture of one machine via ZRCP cpu-step mode.
Boot normally to the game (tape or .nex at full speed), hold forward (Q), then `enter-cpu-step` and run the CPU in chunks of
N opcodes; whenever the engine's `frames` counter has gone up (top of the main loop = the previous frame is complete on
screen) save the screen and record (ticks, frames, posx, posy). Stops after TICKS ticks (50 = 1 s of game time).
Output: build/m29b_slowmo_<mach>/f%03d.bmp + index.json. usage: m29b_slowmo.py 48k|128k|next [ticks] [opcodes_per_run]"""
import sys, time, pathlib, subprocess, re, random, socket, os, json, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
mach = sys.argv[1]; TICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 50; N = int(sys.argv[3]) if len(sys.argv) > 3 else {"48k": 4000, "128k": 4000, "next": 20000}[sys.argv[1]]
symf = {"48k": "build/kea48.sym", "128k": "build/kea128.sym", "next": "build/kea128.sym"}[mach]
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / symf).read_text(), re.M)}
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"; MMC = ROOT / "build/tbblue_slowmo.mmc"; NEX = ROOT / "build/killemall128.nex"
OUT = ROOT / ("build/m29b_slowmo_%s" % mach); shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir()

def zrcp(s, cmd, wait=0.05, tmo=20.0):
    """like run48.zrcp but also accepts the 'command@cpu-step>' prompt and waits up to tmo seconds for it."""
    s.sendall((cmd + "\n").encode()); time.sleep(wait)
    out = b""; s.settimeout(tmo)
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            out += c
            if out.rstrip().endswith(b">") and (b"command>" in out[-12:] or b"step>" in out[-12:]): break
    except socket.timeout:
        pass
    return out.decode(errors="replace")

port = 11000 + random.randint(0, 80) + {"48k": 0, "128k": 100, "next": 200}[mach]
base = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
        "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit"]
if mach == "next":
    shutil.copyfile(MMC_SRC, MMC)
    cmd = base + ["--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked", "--enable-mmc",
                  "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex"]
else:
    cmd = base + ["--machine", mach, str(ROOT / {"48k": "build/killemall48_m25.tap", "128k": "build/killemall128_m2.tap"}[mach])]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_slowmo_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(160):
    try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); raise SystemExit("no ZRCP")
zrcp(s, "", 0.5, 2.0)
def q(c, w=0.05, tmo=20.0): return re.sub(r"command(@cpu-step)?>\s*$", "", zrcp(s, c, w, tmo))
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.1, 2.0)); return int(m.group(1), 16) if m else -1
def rd(addr, n):
    h = "".join(ch for ch in q("read-memory %d %d" % (addr, n), 0.02, 2.0) if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
def st():
    b = rd(S["ticks"], 8)
    return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8) if len(b) == 8 else None
def tap_k(keys, hold=0.25, gap=1.2):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05, 2.0); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05, 2.0); time.sleep(gap)
t0 = time.time()
if mach == "next":
    from m29_nextboot import boot_to_game
    boot_to_game(lambda c, w=0.3: zrcp(s, c, w, 2.0).split("command>")[0], tap_k, pc, log=lambda m: print(m, flush=True))
else:
    while time.time() - t0 < 90 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
time.sleep(1.5)
for k in (("SPACE",), ("ENTER",), ("SPACE",)):
    tap_k(k); v = st()
    if v and v[1] > 0: break
print("%s: game running after %.0f s, st %s" % (mach, time.time() - t0, st()), flush=True)
zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.05, 2.0); time.sleep(0.6)        # walking before the capture starts
print("enter-cpu-step:", q("enter-cpu-step", 0.1, 5.0).strip()[:40], flush=True)
v0 = st(); last_f = v0[1]; idx = []; runs = 0; w0 = time.time(); prev = None
while True:
    zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.0, 2.0)                        # re-assert the key inside cpu-step mode
    q("run %d" % N, 0.0, 60.0); runs += 1
    v = st()
    if v[1] != last_f:
        if v[1] != last_f + 1: print("WARNING: frames jumped %d -> %d (N too large)" % (last_f, v[1]), flush=True)
        last_f = v[1]
        # frame k has just begun (frames++ is the first thing main does): the screen holds the FINISHED frame k-1, which
        # became visible a moment ago; pair it with the camera values recorded when frame k-1 started rendering.
        if prev is not None:
            scr = OUT / ("f%03d.scr" % len(idx))
            h = "".join(ch for ch in q("read-memory 16384 6912", 0.05, 15.0) if ch in "0123456789ABCDEFabcdef")[:2 * 6912]
            scr.write_bytes(bytes.fromhex(h) if len(h) == 2 * 6912 else b"")    # ULA screen: works in cpu-step mode on TBBlue too (save-screen does not)
            idx.append({"ticks": v[0] - v0[0], "frames": v[1] - v0[1] - 1, "x": prev[1], "y": prev[2], "cam_ticks": prev[0] - v0[0], "scr": scr.name})
        q("run 600", 0.0, 60.0)                                                  # past glide_in: posx/posy now hold frame k's camera position
        w = st(); prev = (w[0], w[2] / 256.0, w[3] / 256.0)
    if v[0] - v0[0] >= TICKS: break
dw = time.time() - w0
print("%s: %d runs of %d opcodes in %.0f s wall; %d frames captured over %d ticks (%.1f fps game time); pos %s -> (%.2f, %.2f)" % (
    mach, runs, N, dw, len(idx), v[0] - v0[0], 50.0 * len(idx) / max(1, v[0] - v0[0]), "(%.2f, %.2f)" % (v0[2] / 256.0, v0[3] / 256.0), v[2] / 256.0, v[3] / 256.0), flush=True)
import hashlib
hs = [hashlib.md5((OUT / e["scr"]).read_bytes()).hexdigest() for e in idx]
print("%s: distinct consecutive screens %d of %d" % (mach, sum(1 for i in range(1, len(hs)) if hs[i] != hs[i - 1]), len(hs) - 1))
(OUT / "index.json").write_text(json.dumps({"mach": mach, "ticks": TICKS, "frames": idx}, indent=0))
zrcp(s, "set-ui-io-ports " + ports(), 0.05, 2.0); q("exit-cpu-step", 0.1, 5.0); q("exit-emulator", 0.3, 2.0); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
