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
    ap.add_argument("--prefix", default="N2", help="lane N3F: prefix of the log json (build/night/<prefix>_game_log.json)")
    ap.add_argument("--level", type=int, default=None, help="lane N3 (N3_BRIEF task 4): poke g_level = K and g_lvreq = 1 before the script; "
                    "main_loop (src/next/main_b.asm) honours the request before the next game step: load_level_b + restart_level, then clears it")
    ap.add_argument("--syms", default="build/next/main_b.sym", help="the .sym of the .nex (g_level, g_lvreq read from it, never hard-coded)")
    ap.add_argument("--pose", default=None, help="lane N3F: X,Y,ANG (cells, angle 0..1023) poked into px/py/ang (+ g_moved = 1) after the level request, "
                    "before the script: a camera inside the level (level 08's start room is closed by the red door at (17,24))")
    ap.add_argument("--watch-cell", default=None, help="lane N3F: X,Y of a LEVEL cell whose code is logged at every grab (a door that opens: 8 -> 0")
    ap.add_argument("--ticks", action="store_true", help="lane N3F: the script durations are emulated TICKS (50 Hz) instead of wall-clock seconds, so a "
                    "turn of 22 ticks = 264 angle units lands exactly however slow the ZRCP grabs are; grabs happen when they fit in the step")
    ap.add_argument("--god", action="store_true", help="lane N3F (Alex 6 Nov, QUESTIONS #4b): showcase clips only - the tool pokes g_health = 100 and "
                    "g_ammo = 99 at every grab and every ~10 ticks of a --ticks hold, so the camera survives the level 08 boss long enough to be filmed. "
                    "Nothing in the engine changes (same .nex); the enemies still hit (the drops show between pokes) and every poke is logged. "
                    "Never for the oracles (nx_test_game_b.py does not know this flag).")
    a = ap.parse_args()
    nex = ROOT / a.nex
    fdir = ROOT / a.frames_dir
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob("f_*.png"): old.unlink()
    steps = []
    for item in a.script.split(","):
        k, secs = item.split(":")
        # lane N3F: a '!' suffix (e.g. O!:0.43) holds the keys for exactly `secs` without grabbing in between (a grab costs ~0.6 s,
        # so a grabbed hold always lasts at least that long: turns of 90 deg = 256 units at 600 units/s need 0.43 s precisely)
        precise = k.endswith("!"); k = k.rstrip("!")
        steps.append(([] if k == "-" else k.split("+"), float(secs), precise))
    syms = {}
    for line in (ROOT / a.syms).read_text().splitlines():
        parts = line.replace("\t", " ").split()
        if len(parts) == 3 and parts[1].upper() == "EQU":
            syms[parts[0]] = int(parts[2].rstrip("Hh"), 16)
    G_LEVEL, G_LVREQ, G_MOVED, LEVEL_ADDR = syms["g_level"], syms["g_lvreq"], syms["g_moved"], syms["LEVEL"]
    THINGS_B, NTHINGS_B = syms["THINGS_B"], syms["NTHINGS_B"]
    G_HEALTH, G_AMMO = syms["g_health"], syms["g_ammo"]              # lane N3F --god (from the .sym, never hard-coded)
    watch = tuple(int(v) for v in a.watch_cell.split(",")) if a.watch_cell else None
    def poke(s, addr, data):
        # lane N2 pitfall: ZEsarUX write-memory parses bare values as DECIMAL; the H suffix makes them hex (never NexRun.wr)
        zrcp(s, "write-memory %d %s" % (addr, " ".join("%02XH" % b for b in data)), 0.1)
    god_pokes = [0]
    def god(s):
        # lane N3F --god: health 100 and ammo 99 (both bytes are adjacent: g_health 5DB0h, g_ammo 5DB1h in main_b_vars.inc)
        if a.god:
            poke(s, G_HEALTH, [100, 99] if G_AMMO == G_HEALTH + 1 else [100]); god_pokes[0] += 1
            if G_AMMO != G_HEALTH + 1: poke(s, G_AMMO, [99])
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
        gb = r.rd(0x5DB0, 8); rec.update({"health": gb[0], "ammo": gb[1], "kkeys": gb[2], "kills": gb[3], "level": gb[4]} if len(gb) == 8 else {})
        god(r.s)                                                      # lane N3F --god: AFTER the read, so the log shows the real drop
        if watch: rec["cell"] = r.byte(LEVEL_ADDR + 8 + watch[1] * 32 + watch[0])
        tb = fast_rd(r.s, THINGS_B, NTHINGS_B * 8, 0.03)             # lane N3F: living enemies (type, x, y, state) for the clip claims
        rec["enemies"] = [(tb[i], round((tb[i + 1] | tb[i + 2] << 8) / 256, 2), round((tb[i + 3] | tb[i + 4] << 8) / 256, 2), tb[i + 5], tb[i + 6]) for i in range(0, len(tb), 8) if 0 < tb[i] < 7] if len(tb) == NTHINGS_B * 8 else []   # + hp (pistol hits left)
        if scr:
            rec["png"] = str((fdir / ("f_%03d.png" % len(log))).relative_to(ROOT))
            NexRun.png(scr, ROOT / rec["png"], pal=PAL_B)
            rec["scr_hash"] = hash(scr) & 0xFFFFFFFF
        log.append(rec)
        print("grab %3d t=%6.2fs keys=%-4s PC=%04X frames=%5d ticks=%5d px=%04X (%.3f) py=%04X (%.3f) ang=%4d %s" % (rec["i"], rec["t"], rec["keys"], pc, rec["frames"], rec["ticks"],
              rec["px"], rec["px"] / 256, rec["py"], rec["py"] / 256, rec["ang"], "" if scr else "SCREEN READ FAILED"), "hp=%d ammo=%d keys=%d kills=%d level=%d" % (rec.get("health", -1), rec.get("ammo", -1), rec.get("kkeys", -1), rec.get("kills", -1), rec.get("level", -1)))
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
        if a.level is not None:
            poke(r.s, G_LEVEL, [a.level]); poke(r.s, G_LVREQ, [1])
            t = time.time(); cleared = False
            while time.time() - t < 5:
                time.sleep(0.1)
                if r.byte(G_LVREQ) == 0: cleared = True; break
            v = fast_vars(r.s) or {"px": r.w16(PX), "py": r.w16(PY), "ang": r.w16(ANG)}
            print("level request: g_level=%d poked at %04Xh, g_lvreq (%04Xh) cleared by main_loop: %s; now g_level=%d pose (%.3f, %.3f) ang %d" % (
                a.level, G_LEVEL, G_LVREQ, cleared, r.byte(G_LEVEL), v["px"] / 256, v["py"] / 256, v["ang"]))
            if not cleared:
                print("LEVEL REQUEST NOT HONOURED - abort"); sys.exit(1)
        if a.pose:
            x, y, ang = (float(v) for v in a.pose.split(","))
            import struct
            poke(r.s, PX, struct.pack("<HHH", int(round(x * 256)) & 0xFFFF, int(round(y * 256)) & 0xFFFF, int(ang) & 1023)); poke(r.s, G_MOVED, [1])
            time.sleep(0.3); v = fast_vars(r.s) or {"px": r.w16(PX), "py": r.w16(PY), "ang": r.w16(ANG)}
            print("pose poked: (%.2f, %.2f) angle %d -> now (%.3f, %.3f) ang %d" % (x, y, ang, v["px"] / 256, v["py"] / 256, v["ang"]))
        time.sleep(0.5)
        grab(r, [], "start")
        for keys, secs, *extra in steps:
            precise = bool(extra and extra[0])
            if keys and (keys[0].startswith("ANG=") or keys[0].startswith("AIM=")):
                # lane N3F: "ANG=768:0" pokes the heading (and g_moved = 1) - the ZRCP latency makes key-timed turns land +-100
                # angle units off; the snap keeps the following walk on its intended line (clip scripts only, not the oracles).
                # "AIM=22.5;2.5:0" turns towards a map point from the CURRENT position (the walk then passes over a pickup).
                import struct, math
                if keys[0].startswith("AIM="):
                    tx, ty = (float(v) for v in keys[0][4:].split(";"))
                    v = fast_vars(r.s) or {"px": r.w16(PX), "py": r.w16(PY)}
                    ang_v = int(round(math.atan2(ty * 256 - v["py"], tx * 256 - v["px"]) / (2 * math.pi) * 1024)) & 1023
                else:
                    ang_v = int(keys[0][4:]) & 1023
                poke(r.s, ANG, struct.pack("<H", ang_v)); poke(r.s, G_MOVED, [1]); time.sleep(0.2)
                grab(r, [], "snap"); continue
            zrcp(r.s, "set-ui-io-ports " + ports(keys), 0.05)
            t_step = time.time(); next_grab = t_step
            if a.ticks:
                # lane N3F: the step lasts `secs` EMULATED ticks (50 Hz: turn 12 angle units, walk 0.094 cell per tick), read from
                # the program's tick counter; a grab (~0.6 s wall clock = ~30 ticks) is only taken while it cannot overshoot the step
                v0 = fast_vars(r.s); t0 = v0["ticks"] if v0 else r.w16(TICKS); want = int(secs)
                last_god = 0
                while True:
                    v = fast_vars(r.s); el = ((v["ticks"] if v else r.w16(TICKS)) - t0) & 0xFFFF
                    if el >= want: break
                    if a.god and el - last_god >= 10: god(r.s); last_god = el        # lane N3F --god: every ~10 ticks of the hold
                    if want - el > 40 and time.time() >= next_grab:
                        grab(r, keys, "hold"); next_grab = time.time() + a.grab
                    time.sleep(0.01)
            else:
                while time.time() - t_step < secs:
                    if not precise and time.time() >= next_grab:
                        grab(r, keys, "hold"); next_grab += a.grab
                    time.sleep(0.02)
            zrcp(r.s, "set-ui-io-ports " + ports(), 0.05)
            if a.ticks: grab(r, keys, "step-end")
        time.sleep(0.5)
        grab(r, [], "end")
        final_pc = r.pc()
    # ---- results
    (ROOT / ("build/night/%s_game_log.json" % a.prefix)).write_text(json.dumps(log, indent=0))
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
    # lane N3F: the game variables over the clip (oracle D reads these, not the script)
    def series(key):
        out = []
        for x in log:
            v = x.get(key, -1)
            if not out or out[-1][1] != v: out.append((x["i"], v))
        return out
    print("game variables (grab index, value) at every change: health %s ; ammo %s ; kills %s ; keys %s ; level %s%s" % (
        series("health"), series("ammo"), series("kills"), series("kkeys"), series("level"), (" ; cell(%d,%d) %s" % (watch[0], watch[1], series("cell"))) if watch else ""))
    if a.god:
        print("GOD MODE (showcase clip, not an oracle): the tool poked g_health=100/g_ammo=99 %d times; the health values above are read BEFORE each poke, "
              "so every value < 100 is a real hit taken since the previous poke" % god_pokes[0])
    for x in log:
        print("enemies at grab %d (type, x, y, state 0 idle 1 chase 2 attack 3 dead, hp in pistol hits): %s" % (x["i"], x.get("enemies")))
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
