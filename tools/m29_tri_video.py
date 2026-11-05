#!/usr/bin/env python3
"""m29_tri_video.py - M2.9 'all three machines' video: 48K tape, 128K tape and the Next .nex (28 MHz) run side by side in three
headless ZEsarUX instances (--vo null); the RENDERED screen of each is saved with ZRCP `save-screen` (bmp, all layers) as fast as
the control port allows (~3-4 shots/s per machine) while the forward key is held for WALK seconds, then the three strips are
assembled on a common timeline with captions (steps counted from posx/posy, ticks = Spectrum time) -> build/m29_tri.mp4 plus
build/m29_tri_start.png / build/m29_tri_end.png (first/last composite). usage: m29_tri_video.py [walk_s]"""
import sys, time, pathlib, shutil, subprocess, re, random, threading, socket, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from run48 import zrcp, ZES
from fe_shot import ports

ROOT = pathlib.Path(__file__).resolve().parent.parent
WALK = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
SYMS = {m: {g.group(1): int(g.group(2), 16) for g in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / f).read_text(), re.M)}
        for m, f in (("48k", "build/kea48.sym"), ("128k", "build/kea128.sym"))}
SYMS["next"] = SYMS["128k"]
MMC_SRC = pathlib.Path(ZES).parent / "tbblue.mmc"; MMC = ROOT / "build/tbblue_tri.mmc"; NEX = ROOT / "build/killemall128.nex"

def start(mach, port):
    base = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
            "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(port), "--quickexit"]
    if mach == "next":
        shutil.copyfile(MMC_SRC, MMC)
        cmd = base + ["--machine", "TBBlue", "--disable-first-start-wizard", "--tbblue-autoconfigure-sd-already-asked", "--enable-mmc",
                      "--mmc-file", str(MMC), "--enable-divmmc-ports", "--copy-file-to-mmc", str(NEX), "killemall.nex"]
    else:
        tap = {"48k": "build/killemall48_m25.tap", "128k": "build/killemall128_m2.tap"}[mach]
        cmd = base + ["--machine", mach, str(ROOT / tap)]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_tri_%s.log" % mach, "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(160):
        try: s = socket.create_connection(("127.0.0.1", port), timeout=1); break
        except OSError: time.sleep(0.25)
    if s is None: p.kill(); raise SystemExit("no ZRCP " + mach)
    zrcp(s, "", 0.5)
    return p, s

def run(mach, out):
    S = SYMS[mach]; p, s = start(mach, 10500 + random.randint(0, 80) + {"48k": 0, "128k": 100, "next": 200}[mach])
    def q(c, w=0.3): return zrcp(s, c, w).split("command>")[0]
    def pc():
        m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.2)); return int(m.group(1), 16) if m else -1
    def rd(addr, n):
        h = "".join(ch for ch in q("read-memory %d %d" % (addr, n), 0.08) if ch in "0123456789ABCDEFabcdef")[:2 * n]
        return bytes.fromhex(h) if len(h) == 2 * n else b""
    def st():
        b = rd(S["ticks"], 8)
        return (b[0] | b[1] << 8, b[2] | b[3] << 8, b[4] | b[5] << 8, b[6] | b[7] << 8) if len(b) == 8 else None
    def shot(i):
        bmp = "/tmp/tri_%s_%03d.bmp" % (mach, i); q("save-screen " + bmp, 0.25)
        return bmp if os.path.exists(bmp) else None
    def tap(keys, hold=0.25, gap=1.2):
        zrcp(s, "set-ui-io-ports " + ports(keys), 0.05); time.sleep(hold); zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    t0 = time.time()
    if mach == "next":
        # NextZXOS boot flow proven by nex_drive.py (fresh5, 3 Nov): 18 s boot, ENTER, 8 s, SPACE, 6 s, ENTER (Browser),
        # 4 s, 16 x CAPS+6 (cursor down to killemall.nex in the SD root), ENTER -> the game's own menu; then the usual start keys.
        from m29_nextboot import boot_to_game
        boot_to_game(q, tap, pc, log=lambda m: print(m, flush=True))
        if pc() < 0x8000 and pc() != 0x38:
            q("save-screen /tmp/tri_next_stuck.bmp", 0.5); print("next: engine not running after start flow, PC=%04x; see /tmp/tri_next_stuck.bmp" % pc())
    else:
        while time.time() - t0 < 90 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
    time.sleep(1.5)
    for k in (("SPACE",), ("ENTER",), ("SPACE",)):
        tap(k); v = st()
        if v and v[1] > 0: break
    time.sleep(1.0)
    frames = []; k0 = st(); w0 = time.time()
    zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.02)
    i = 0
    while time.time() - w0 < WALK:
        b = shot(i); v = st(); i += 1
        if b and v: frames.append((time.time() - w0, b, v))
    zrcp(s, "set-ui-io-ports " + ports(), 0.02)
    b = shot(i); v = st(); frames.append((time.time() - w0, b, v))
    q("exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    out[mach] = (k0, frames)

res = {}
for m in ("48k", "128k", "next"):
    run(m, res)          # sequential: three emulators at once made the Next boot miss its key timings

def cells(v, k0): return (((v[2] - k0[2]) ** 2 + (v[3] - k0[3]) ** 2) ** 0.5) / 256.0
for m in ("48k", "128k", "next"):
    k0, fr = res[m]; v = fr[-1][2]
    mv = [e for e in fr if cells(e[2], k0) < cells(v, k0) - 1e-9]          # samples before the final position was reached
    v = fr[len(mv)][2] if len(mv) < len(fr) else v                        # first sample AT the final position
    dk = (v[0] - k0[0]) & 0xFFFF; df = (v[1] - k0[1]) & 0xFFFF
    print("%s: %d shots, walked %.2f cells = %.1f steps in %.2f s Spectrum time -> %.1f steps/s, %.1f fps" % (
        m, len(fr), cells(v, k0), cells(v, k0) / 0.15, dk / 50.0, (cells(v, k0) / 0.15) / (dk / 50.0) if dk else 0, 50.0 * df / dk if dk else 0))

fd = ROOT / "build/m29_tri_frames"; shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
SC = 2
imgs0 = {m: Image.open(res[m][1][0][1]).convert("RGB") for m in res}
w0, h0 = imgs0["48k"].size                     # ZEsarUX save-screen size incl. border (same for all three?)
sizes = {m: imgs0[m].size for m in res}; print("shot sizes:", sizes)
T = max(fr[-1][0] for _, fr in res.values()); t = 0.0; n = 0; names = []
LABEL = {"48k": "48K classic (tape)", "128k": "128K (tape, AY)", "next": "Spectrum Next (.nex, 28 MHz)"}
while t <= T + 1e-6:
    panels = []
    for m in ("48k", "128k", "next"):
        k0, fr = res[m]; e = min(fr, key=lambda e: abs(e[0] - t))
        im = Image.open(e[1]).convert("RGB"); im = im.resize((528, round(im.height * 528 / im.width)), Image.NEAREST)
        cap = Image.new("RGB", (im.width, 44), (0, 0, 0)); d = ImageDraw.Draw(cap)
        d.text((6, 4), LABEL[m], fill=(255, 255, 255))
        dk = (e[2][0] - k0[0]) & 0xFFFF; df = (e[2][1] - k0[1]) & 0xFFFF
        d.text((6, 24), "t=%.1fs  walked %.2f cells (%.0f steps)  %d frames in %d ticks = %.0f fps" % (t, cells(e[2], k0), cells(e[2], k0) / 0.15, df, dk, 50.0 * df / dk if dk else 0), fill=(255, 255, 0))
        pan = Image.new("RGB", (im.width, im.height + 44), (0, 0, 0)); pan.paste(cap, (0, 0)); pan.paste(im, (0, 44)); panels.append(pan)
    Wt = sum(p.width for p in panels) + 8 * 2; Ht = max(p.height for p in panels) + 30
    out = Image.new("RGB", (Wt, Ht), (24, 24, 24)); x = 0
    for p in panels: out.paste(p, (x, 0)); x += p.width + 8
    ImageDraw.Draw(out).text((8, Ht - 24), "M2.9b: 10 game steps/s on all three; 128K/Next camera glides between steps, so the Next now draws every frame it can" , fill=(200, 200, 200))
    nm = fd / ("f%04d.png" % n); out.save(nm); names.append(nm); n += 1; t += 0.1
NM = os.environ.get("TRI_NAME", "m29_tri"); shutil.copyfile(names[0], ROOT / ("build/%s_start.png" % NM)); shutil.copyfile(names[-1], ROOT / ("build/%s_end.png" % NM))
with open(fd / "list.txt", "w") as f:
    for nm in names: f.write("file '%s'\nduration 0.1\n" % nm.name)
    f.write("file '%s'\nduration 2.0\n" % names[-1].name)
mp4 = ROOT / ("build/%s.mp4" % os.environ.get("TRI_NAME", "m29_tri"))
r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(fd / "list.txt"), "-vf", "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-r", "25", str(mp4)], capture_output=True, text=True)
print("mp4 %s %s bytes, %d composite frames, ffmpeg rc %d %s" % (mp4, mp4.stat().st_size if mp4.exists() else 0, n, r.returncode, r.stderr.strip()[:300]))
