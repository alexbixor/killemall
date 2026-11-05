#!/usr/bin/env python3
"""m30_bench_run.py - run build/m30_bench.nex on the headless ZEsarUX Spectrum Next (TBBlue, real NextZXOS boot via
m29_nextboot), wait for each of the four 100-frame tests, read the results (50 Hz ticks), dump the LoRes screen after
each test, render it with the RRRGGGBB palette (build/m30_bench_tN.png, 4x), grab ZEsarUX's own picture of the final
scene (build/m30_bench_scene_zes.png) and compare the T4 scene dump pixel by pixel with a Python model of the same
fixed-point drawing (oracle). Writes build/m30_bench_results.json. usage: m30_bench_run.py [timeout_s]"""
import sys, time, pathlib, re, random, subprocess, socket, os, json, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
from fe_shot import ports
import m29_nextboot as nb
from PIL import Image
import m30_bench_gen as G
ROOT = pathlib.Path(__file__).resolve().parent.parent
B = ROOT / "build"
LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 240.0
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (B / "m30_bench.sym").read_text(), re.M)}
CODE = (B / "m30_bench.bin").read_bytes()
port = 10400 + random.randint(0, 80)
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"; MMC = B / "tbblue_bench.mmc"; shutil.copyfile(MMC_SRC, MMC)
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
       "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit",
       "--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked", "--enable-mmc", "--mmc-file", str(MMC),
       "--enable-divmmc-ports", "--copy-file-to-mmc", str(B / "m30_bench.nex"), "killemall.nex"] + os.environ.get("ZES_EXTRA", "").split()
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_m30bench.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(80):
    try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
    except OSError: time.sleep(0.25)
if s is None: p.kill(); sys.exit("no ZRCP")
zrcp(s, "", 0.5)
def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
def pc():
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.2)); return int(m.group(1), 16) if m else -1
def rd(addr, n):
    out = b""
    while n > 0:
        k = min(n, 2048)
        r = zrcp(s, "read-memory %d %d" % (addr, k), 0.25)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * k]
        if len(h) != 2 * k: return b""
        out += bytes.fromhex(h); addr += k; n -= k
    return out
def tapk(keys, hold=0.2, gap=0.5):
    zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
def running():
    return rd(0x8000, 8) == CODE[:8] and 0x8000 <= pc() < 0xA000
orig = nb.classify
def cl(bmp):
    if running(): return "game"
    return orig(bmp)
nb.classify = cl
t0 = time.time(); log = []
ok = nb.boot_to_game(q, tapk, pc, log=lambda m: log.append(m))
print("\n".join(log)); print("boot_to_game ->", ok, "after %.1f s" % (time.time() - t0))
if not ok: zrcp(s, "exit-emulator", 0.3); p.kill(); sys.exit("benchmark did not start")
print("cpu turbo:", q("get-cpu-turbo-speed", 0.3).strip(), "| nextreg 7:", q("tbblue-get-register 7", 0.3).strip())

def w16(a): b = rd(a, 2); return b[0] | (b[1] << 8)
def screen():
    top = rd(0x4000, 6144); bot = rd(0x6000, 6144)
    return top + bot if len(top) == 6144 and len(bot) == 6144 else b""
def pal(c): return (((c >> 5) & 7) * 255 // 7, ((c >> 2) & 7) * 255 // 7, (c & 3) * 85)
def to_png(scr, path, scale=4):
    im = Image.new("RGB", (128, 96)); px = im.load()
    for y in range(96):
        for x in range(128): px[x, y] = pal(scr[y * 128 + x])
    im.resize((128 * scale, 96 * scale), Image.NEAREST).save(path); return im
res = {}; shots = {}
t1 = time.time(); last = None
while time.time() - t1 < LIMIT:
    vals = [w16(S["res_t%d" % i]) for i in range(1, 5)]; done = rd(S["bench_done"], 1)[0]; fr = w16(S["frames"]); tk = w16(S["ticks"])
    cal = [w16(S["res_t%d" % i]) for i in (0, 5, 6)]
    state = (tuple(vals), done)
    if state != last:
        print("  %6.1fs ticks %5d frames %4d calib %s results %s done %d" % (time.time() - t1, tk, fr, cal, vals, done)); last = state
    for i in range(1, 5):
        if vals[i - 1] and i not in shots:
            time.sleep(0.4)                                      # the program pauses 3 s after each test: screen is static
            scr = screen()
            if scr: shots[i] = scr; to_png(scr, B / ("m30_bench_t%d.png" % i)); print("  saved m30_bench_t%d.png" % i)
    if done: break
    time.sleep(0.5)
bmp = "/tmp/m30bench.bmp"
if os.path.exists(bmp): os.remove(bmp)
q("save-screen " + bmp, 1.0)
if os.path.exists(bmp): Image.open(bmp).convert("RGB").save(B / "m30_bench_scene_zes.png"); print("  saved m30_bench_scene_zes.png (ZEsarUX render)")
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()

# ---- oracle: Python model of the same fixed-point drawing, compared with the T4 dump
bank0 = (B / "m30_bench_bank0.bin").read_bytes()
def tex(addr): return bank0[addr - 0xC000]
def model_floor(scr, lo):
    for (sp, X0, Y0, DX, DY, page) in G.floor_rows(lo):
        r = (sp - 128 - 0x4000) // 128 if sp - 128 < 0x6000 else 48 + (sp - 128 - 0x6000) // 128
        x, y = X0, Y0; col = 127
        for _ in range(64 if not lo else 64):
            x = (x + DX) & 0xFFFF; y = (y + DY) & 0xFFFF
            t = tex((page << 8) | ((x & 0xF0) | ((y >> 8) & 0x0F)))
            if lo:
                scr[r * 128 + col] = t; scr[r * 128 + col - 1] = t; col -= 2
            else:
                scr[r * 128 + col] = t; col -= 1
                x = (x + DX) & 0xFFFF; y = (y + DY) & 0xFFFF
                scr[r * 128 + col] = tex((page << 8) | ((x & 0xF0) | ((y >> 8) & 0x0F))); col -= 1
            if lo and col < 0: break
    return scr
def model_cols(scr, recs):
    for (col, start, count, page, hl, dvi, ix) in recs:
        v = hl
        for r in range(start, start + count):
            v = (v + dvi) & 0xFFFF
            scr[r * 128 + col] = tex((page << 8) | (v >> 8))
    return scr
def diff(a, b): return sum(1 for i in range(len(a)) if a[i] != b[i])
report = {"calibration_ticks": {"t0_cpu_loop_expect_33": cal[0], "t5_fill_screen_ram_expect_14": cal[1], "t6_fill_plain_ram_expect_14": cal[2]}, "ticks_per_100_frames": {"t1_walls_full": None, "t2_floor_hi": None, "t3_floor_lo": None, "t4_scene": None}, "fps": {}, "oracle": {}}
names = ["t1_walls_full", "t2_floor_hi", "t3_floor_lo", "t4_scene"]
for i, n in enumerate(names):
    v = last[0][i] if last else 0
    report["ticks_per_100_frames"][n] = v
    report["fps"][n] = round(100.0 / (v / 50.0), 1) if v else None
if 1 in shots: report["oracle"]["t1"] = diff(shots[1], model_cols(bytearray(96 * 128), G.full_columns()))
if 2 in shots: report["oracle"]["t2"] = diff(shots[2], model_floor(bytearray(96 * 128), False))
if 3 in shots: report["oracle"]["t3"] = diff(shots[3], model_floor(bytearray(96 * 128), True))
if 4 in shots:
    m = model_cols(model_floor(bytearray(96 * 128), False), G.scene_columns()); report["oracle"]["t4"] = diff(shots[4], m)
    to_png(m, B / "m30_bench_t4_model.png")
(B / "m30_bench_results.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report))
