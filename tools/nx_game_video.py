#!/usr/bin/env python3
"""nx_game_video.py - lane N2: tools/nx_walk_video.py for the edition B GAME (build/next/killemall_b.nex): the key script also
fires (M) and uses (SPACE); every grab logs health/ammo/keys/kills (5DB0h..5DB3h) next to frames/px/py/ang/ticks; outputs are
N2_ prefixed (build/night/N2_frames/f_*.png, N2_game.mp4, N2_game_log.json). Same grab/PC/speed checks as the walk video.
Palette: build/next/assets_b/palette.bin (edition B) when present."""
import argparse, json, pathlib, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_run import NexRun
from run48 import zrcp
from fe_shot import ports

FRAMES, PX, PY, ANG, TICKS = 0x5800, 0x5802, 0x5804, 0x5806, 0x5808
FFMPEG = "/usr/bin/ffmpeg"

def _pal_b():
    p = ROOT / "build/next/assets_b/palette.bin"
    if p.exists() and p.stat().st_size == 512:
        b = p.read_bytes()
        return [(((b[2*i] >> 5) & 7) * 255 // 7, ((b[2*i] >> 2) & 7) * 255 // 7, ((((b[2*i] & 3) << 1) | (b[2*i+1] & 1)) * 255 // 7)) for i in range(256)]
    return None
PAL_B = _pal_b()
def s16(v): return v - 65536 if v >= 32768 else v

def fast_rd(s, addr, n, wait=0.02):
    """read-memory in one ZRCP round trip (NexRun.rd waits 0.2 s per 2 KB chunk -> 1.2 s per screen; this takes ~0.09 s)."""
    r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else b""

def fast_screen(s):
    top = fast_rd(s, 0x4000, 6144); bot = fast_rd(s, 0x6000, 6144)
    return top + bot if len(top) == 6144 and len(bot) == 6144 else b""

def fast_vars(s):
    """frames, px, py, ang, ticks (5800h..5809h) in one read."""
    b = fast_rd(s, FRAMES, 10, 0.01)
    if len(b) != 10: return None
    w = lambda i: b[i] | (b[i + 1] << 8)
    return {"frames": w(0), "px": w(2), "py": w(4), "ang": w(6), "ticks": w(8)}

def fast_pc(s):
    import re
    m = re.search(r"PC=([0-9a-fA-F]{4})", zrcp(s, "get-registers", 0.02)); return int(m.group(1), 16) if m else -1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nex", default="build/next/killemall_b.nex")
    ap.add_argument("--grab", type=float, default=0.25, help="seconds between screen grabs")
    ap.add_argument("--script", default="O:1.0,Q:1.2,M:0.3,-:0.4,M:0.3,-:0.4,M:0.3,-:0.4,M:0.3,-:0.4,P:1.0,Q:2.0,SPACE:0.4,Q:1.5,A:0.6",
                    help="key:seconds steps; '+' combines keys, '-' = none. Default: corridor east 2.3 s into the hall (x ~16.7), turn left ~90 deg "
                         "(face north: the dais steps and the altar), climb the steps 0.6 s, turn right ~180 deg (face south), walk back down across the hall "
                         "1.3 s, turn left 0.5 s. Turns are 600 angle units = 211 deg per second; walking is 4.7 cells per second. "
                         "(The task's generic example Q:2,P:1,Q:2,O:1.5,Q:2 also works: see build/night/M_walk_eg.out.)")
    ap.add_argument("--frames-dir", default="build/night/N2_frames")
    ap.add_argument("--out", default="build/night/N2_game.mp4")
    a = ap.parse_args()
    nex = ROOT / a.nex
    fdir = ROOT / a.frames_dir
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob("f_*.png"): old.unlink()
    steps = []
    for item in a.script.split(","):
        k, secs = item.split(":")
        steps.append(([] if k == "-" else k.split("+"), float(secs)))
    log = []          # one record per grab
    bad_pcs = []
    pc_samples = 0
    def grab(r, held, tag):
        nonlocal pc_samples
        pc = fast_pc(r.s); pc_samples += 1
        if not (0x8000 <= pc < 0xC000 or 0x38 <= pc < 0x60):
            bad_pcs.append(pc)
        scr = fast_screen(r.s)
        v = fast_vars(r.s) or {"frames": r.w16(FRAMES), "px": r.w16(PX), "py": r.w16(PY), "ang": r.w16(ANG), "ticks": r.w16(TICKS)}
        rec = {"i": len(log), "t": round(time.time() - t_start, 3), "keys": "+".join(held) or "-", "tag": tag, "pc": pc, "screen_ok": len(scr) == 12288, "distinct": len(set(scr)) if scr else 0}
        rec.update(v)
        gb = r.rd(0x5DB0, 8); rec.update({"health": gb[0], "ammo": gb[1], "kkeys": gb[2], "kills": gb[3]} if len(gb) == 8 else {})
        if scr:
            rec["png"] = str((fdir / ("f_%03d.png" % len(log))).relative_to(ROOT))
            NexRun.png(scr, ROOT / rec["png"], pal=PAL_B)
            rec["scr_hash"] = hash(scr) & 0xFFFFFFFF
        log.append(rec)
        print("grab %3d t=%6.2fs keys=%-4s PC=%04X frames=%5d ticks=%5d px=%04X (%.3f) py=%04X (%.3f) ang=%4d %s" % (rec["i"], rec["t"], rec["keys"], pc, rec["frames"], rec["ticks"],
              rec["px"], rec["px"] / 256, rec["py"], rec["py"] / 256, rec["ang"], "" if scr else "SCREEN READ FAILED"), "hp=%d ammo=%d keys=%d kills=%d" % (rec.get("health", -1), rec.get("ammo", -1), rec.get("kkeys", -1), rec.get("kills", -1)))
        return rec
    with NexRun(nex) as r:
        t_start = time.time()
        ok = r.wait_pc_in(0x8000, 0xC000, timeout=20)
        print("program running (PC in 8000h..C000h): %s, PC=%04X" % (ok, r.pc()))
        f0 = r.w16(FRAMES); t = time.time(); inc = False
        while time.time() - t < 20:
            time.sleep(0.3)
            if r.w16(FRAMES) > f0: inc = True; break
        print("frames increasing: %s (%d -> %d), ticks %d, nextreg 7=%s 15h=%s turbo=%s" % (inc, f0, r.w16(FRAMES), r.w16(TICKS), r.nextreg(7), r.nextreg(0x15), r.q("get-cpu-turbo-speed")))
        if not (ok and inc):
            print("ENGINE NOT RUNNING - abort"); sys.exit(1)
        time.sleep(0.5)
        grab(r, [], "start")
        for keys, secs in steps:
            zrcp(r.s, "set-ui-io-ports " + ports(keys), 0.05)
            t_step = time.time(); next_grab = t_step
            while time.time() - t_step < secs:
                if time.time() >= next_grab:
                    grab(r, keys, "hold"); next_grab += a.grab
                time.sleep(0.02)
            zrcp(r.s, "set-ui-io-ports " + ports(), 0.05)
        time.sleep(0.5)
        grab(r, [], "end")
        final_pc = r.pc()
    # ---- results
    (ROOT / "build/night/N2_game_log.json").write_text(json.dumps(log, indent=0))
    good = [x for x in log if x["screen_ok"]]
    hashes = [x["scr_hash"] for x in good]
    changes = sum(1 for i in range(1, len(hashes)) if hashes[i] != hashes[i - 1])
    df = log[-1]["frames"] - log[0]["frames"]; dt = log[-1]["ticks"] - log[0]["ticks"]
    fps = df / dt * 50 if dt else 0.0
    print("grabs: %d (%d with a valid 12288-byte screen), %d screen changes between consecutive grabs, %d distinct screens" % (len(log), len(good), changes, len(set(hashes))))
    print("engine speed: %d frames in %d ticks (%.2f s of emulated time) = %.2f fps (%.1f ticks/frame)" % (df, dt, dt / 50, fps, dt / df if df else 0))
    print("player path (px, py in cells; ang 0..1023): start (%.3f, %.3f, %d) -> end (%.3f, %.3f, %d)" % (log[0]["px"] / 256, log[0]["py"] / 256, log[0]["ang"], log[-1]["px"] / 256, log[-1]["py"] / 256, log[-1]["ang"]))
    print("  " + " ".join("(%.2f,%.2f,%d)" % (x["px"] / 256, x["py"] / 256, x["ang"]) for x in log))
    moved = sum(1 for i in range(1, len(log)) if (log[i]["px"], log[i]["py"], log[i]["ang"]) != (log[i - 1]["px"], log[i - 1]["py"], log[i - 1]["ang"]))
    print("pose changed between %d of %d consecutive grabs; PC samples %d, PC outside 8000h..BFFFh/ISR: %d %s; final PC=%04X" % (moved, len(log) - 1, pc_samples, len(bad_pcs), ["%04X" % p for p in bad_pcs[:5]], final_pc))
    # ---- video
    out = ROOT / a.out
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "4", "-i", str(fdir / "f_%03d.png"), "-pix_fmt", "yuv420p", "-vf", "scale=512:384", str(out)]
    rc = subprocess.run(cmd, capture_output=True, text=True)
    if rc.returncode == 0 and out.exists():
        print("video: %s (%d bytes, %d frames at 4 fps = %.1f s)" % (out.relative_to(ROOT), out.stat().st_size, len(good), len(good) / 4))
    else:
        print("ffmpeg FAILED (%d): %s" % (rc.returncode, rc.stderr.strip()[:500]))
    verdict = ok and inc and len(good) >= 20 and changes >= 10 and not bad_pcs and out.exists()
    print("RESULT: %s (running %s, >=20 grabs %s, views change %s, no bad PC %s, mp4 %s)" % ("PASS" if verdict else "FAIL", ok and inc, len(good) >= 20, changes >= 10, not bad_pcs, out.exists()))
    sys.exit(0 if verdict else 1)

if __name__ == "__main__":
    main()
