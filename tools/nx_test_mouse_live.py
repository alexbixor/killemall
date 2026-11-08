#!/usr/bin/env python3
"""nx_test_mouse_live.py (lane N5) - oracles C (live), E (fps ON vs OFF) and F (clip) for build/next/killemall_b_n5.nex: ZEsarUX
TBBlue --vo xwindows under Xvfb with --enablekempstonmouse (the flag NexRun(mouse=True) adds; this script builds the same command
line because the oracle needs --vo xwindows for the X pointer), pointer and keys driven by xdotool (XTEST keys are immediate in
xwindows mode, lane M's M_hw_diag.out). Writes build/night/N5_live.out, N5_timing.out (fps part), N5_mouse.mp4 (save-screen BMPs
-> PNG -> ffmpeg). Invoked by tools/nx_test_mouse.py live."""
import os, re, sys, time, pathlib, socket, subprocess
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run48 import zrcp, ZES
import nx_build
ROOT = HERE.parent; NIGHT = ROOT / "build/night"
DISP, PORT = ":85", 10185      # unique display/port for this oracle (":82"/10182 collided with a concurrent run at 14:29Z)
LEVEL = 0xB800

def main(argv):
    nex = str(ROOT / "build/next/killemall_b_n5.nex")
    S = nx_build.read_syms(ROOT / "build/next/main_b_n5.sym")
    out = []; fails = []
    def log(s): print(s, flush=True); out.append(s)
    def check(ok, msg):
        log(("ok   " if ok else "FAIL ") + msg)
        if not ok: fails.append(msg)
    subprocess.run(["pkill", "-f", "Xvfb %s" % DISP], capture_output=True); time.sleep(0.8)
    try: os.remove("/tmp/.X11-unix/X" + DISP[1:])            # a stale socket file makes the wait below pass before Xvfb is ready
    except OSError: pass
    xvfb = subprocess.Popen(["Xvfb", DISP, "-screen", "0", "2000x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = dict(os.environ, DISPLAY=DISP)
    for _ in range(80):
        if subprocess.run(["xdotool", "getdisplaygeometry"], env=env, capture_output=True).returncode == 0: break
        time.sleep(0.1)
    def xdo(*a): return subprocess.run(["xdotool"] + list(a), env=env, capture_output=True, text=True, timeout=10)
    cmd = [ZES, "--noconfigfile", "--vo", "xwindows", "--ao", "null", "--nosplash", "--nowelcomemessage", "--disable-all-first-aid",
           "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", "--machine", "TBBlue", "--disable-first-start-wizard",
           "--tbblue-autoconfigure-sd-already-asked", "--allowturbotbbluerom", "--tbblue-max-turbo-everywhere", "8", "--tbblue-max-turbo-rom", "8",
           "--enablekempstonmouse", "--zoom", "2", "--snap", nex]
    log("== nx_test_mouse live %s  %s  (ZEsarUX --vo xwindows --enablekempstonmouse, Xvfb %s)" % (time.strftime("%H:%M:%SZ", time.gmtime()), os.path.relpath(nex, ROOT), DISP))
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_n5_live.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES), env=env)
    s = None
    for _ in range(120):
        try: s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError: time.sleep(0.25)
    if s is None: p.kill(); xvfb.kill(); sys.exit("no ZRCP")
    zrcp(s, "", 0.5)
    sock = [s]
    def reconnect():
        """ZRCP drops the socket now and then (N4_video.py saw it too); the emulator keeps running, so reconnect"""
        try: sock[0].close()
        except Exception: pass
        for _ in range(40):
            try:
                sock[0] = socket.create_connection(("127.0.0.1", PORT), timeout=1); zrcp(sock[0], "", 0.5); return True
            except OSError: time.sleep(0.25)
        return False
    def q(c, w=0.25):
        for _ in range(3):
            try: return zrcp(sock[0], c, w).split("command>")[0]
            except (BrokenPipeError, ConnectionError, OSError):
                if not reconnect(): raise
        return ""
    def pc():
        m = re.search(r"PC=([0-9a-fA-F]{4})", q("get-registers", 0.15)); return int(m.group(1), 16) if m else -1
    def rd(addr, n=1):
        for _ in range(4):                                  # ZRCP answers late now and then: retry instead of returning zeros
            h = "".join(c for c in q("read-memory %d %d" % (addr, n), 0.15) if c in "0123456789ABCDEFabcdef")[:2 * n]
            if len(h) == 2 * n: return bytes.fromhex(h)
            q("", 0.5)                                       # resync the answer stream (a late answer would be read as the next one)
            time.sleep(0.1)
        return b"\0" * n
    def rd8(name): return rd(S[name])[0]
    def rd16(name): b = rd(S[name], 2); return b[0] | (b[1] << 8)
    def wr(addr, data): q("write-memory %d %s" % (addr, " ".join("%02XH" % b for b in data)), 0.08)
    def wr8(name, v): wr(S[name], [v])
    frames_dir = NIGHT / "N5_video_frames"; frames_dir.mkdir(exist_ok=True)
    for f in frames_dir.glob("*.png"): f.unlink()
    nshot = [0]
    def shot():
        bmp = "/tmp/n5_shot.bmp"
        if os.path.exists(bmp): os.remove(bmp)
        q("save-screen " + bmp, 0.3)
        if os.path.exists(bmp):
            from PIL import Image
            Image.open(bmp).convert("RGB").save(str(frames_dir / ("f%04d.png" % nshot[0]))); nshot[0] += 1; return True
        return False
    def band_m():
        """the 4x5 M at HUD columns 94..97 rows 89..93: 1 when every glyph pixel is bone 223"""
        rows = [rd(0x6000 + (r - 48) * 128 + 94, 4) for r in range(89, 94)]
        glyph = [0x9, 0xF, 0xF, 0x9, 0x9]
        want = [bytes(223 if (g >> (3 - i)) & 1 else rows[k][i] for i in range(4)) for k, g in enumerate(glyph)]
        return all(rows[k] == want[k] for k in range(5)) and any(223 in r for r in rows)
    try:
        t0 = time.time()
        while time.time() - t0 < 60 and not (0x8000 <= pc() < 0xC000): time.sleep(0.5)
        f0 = rd16("frames"); time.sleep(1.0); f1 = rd16("frames")
        check(f1 > f0, "game running (PC %04X after %.1f s): frames %d -> %d in 1 s" % (pc(), time.time() - t0, f0, f1))
        ids = [w for w in xdo("search", "--onlyvisible", "--name", ".").stdout.split() if w.isdigit()]
        wid = ids[-1] if ids else ""
        geo = xdo("getwindowgeometry", wid).stdout.replace("\n", " ")
        xdo("windowfocus", "--sync", wid); xdo("mousemove", "--window", wid, "300", "250"); time.sleep(0.4)
        log("X window %s %s" % (wid, geo))
        check(rd8("opt_mouse_b") == 0 and rd8("horizon_row") == 48, "defaults: opt_mouse_b %d (OFF), horizon_row %d, vl_pad %d" % (rd8("opt_mouse_b"), rd8("horizon_row"), rd(S["horizon_row"] - 1)[0]))
        wr(S["THINGS_B"], [0] * (S["NTHINGS_B"] * 8))        # no enemies: a death (restart_level) would reset ang/pose mid-oracle (run 4 of this script)
        log("things removed (THINGS_B %04Xh x %d cleared) so no enemy attack can restart the level during the run" % (S["THINGS_B"], S["NTHINGS_B"]))
        # C1 OFF: pointer moves change nothing
        a0 = rd16("ang"); l0 = rd8("mouse_last"); h0 = rd8("horizon_row")
        for dx, dy in ((200, 0), (-200, 0), (0, 150), (0, -150)):
            xdo("mousemove", "--window", wid, "300", "250"); time.sleep(0.1); xdo("mousemove_relative", "--", str(dx), str(dy)); time.sleep(0.3)
        check(rd16("ang") == a0 and rd8("mouse_last") == l0 and rd8("horizon_row") == h0, "OFF: 700 px of pointer motion -> ang %d -> %d, mouse_last %d -> %d, horizon %d -> %d (unchanged; the ref oracle A3 counts 0 port reads on this path)" % (a0, rd16("ang"), l0, rd8("mouse_last"), h0, rd8("horizon_row")))
        shot()
        # C2 I toggles ON (XTEST key), indicator drawn
        xdo("keydown", "i"); time.sleep(0.3); xdo("keyup", "i"); time.sleep(0.5)
        check(rd8("opt_mouse_b") == 1, "I pressed -> opt_mouse_b %d (ON), mouse_dbnc %d" % (rd8("opt_mouse_b"), rd8("mouse_dbnc")))
        check(band_m(), "HUD indicator: 4x5 'M' (bone 223) at columns 94..97 rows 89..93 drawn")
        shot()
        # C3 ON: right -> ang +counts, left -> ang -counts (MSHIFT_B 8: 1 unit per count)
        def state():
            """ang, mouse_last, mouse_ylast, horizon_row read until two consecutive reads agree (the emulator runs between ZRCP
            reads: run 2 of this oracle caught ang stale and mouse_last fresh across one frame boundary)"""
            prev = None
            for _ in range(20):
                cur = (rd16("ang"), rd8("mouse_last"), rd8("mouse_ylast"), rd8("horizon_row"))
                if cur == prev: return cur
                prev = cur; time.sleep(0.12)
            return prev
        def move(dx, dy=0):
            xdo("mousemove", "--window", wid, "300", "250"); time.sleep(0.3)
            a0, l0, y0, h0 = state()
            xdo("mousemove_relative", "--", str(dx), str(dy)); time.sleep(0.4); shot()
            a1, l1, y1, h1 = state()
            return a0, a1, (l1 - l0 + 128) % 256 - 128, (y1 - y0 + 128) % 256 - 128, h0, h1
        log("step  px   counter_dx  ang before -> after (delta)  expected = counter_dx")
        ok_dir = ok_mag = True; tot_px = tot_cnt = 0
        for dx in (40, 80, 120, -40, -80, -120):
            a0, a1, dc, dyc, h0, h1 = move(dx)
            da = (a1 - a0 + 512) % 1024 - 512
            log("     %4d  %5d        %4d -> %4d (%+4d)   exp %+4d" % (dx, dc, a0, a1, da, dc))
            if dx > 0 and not (dc > 0 and da > 0): ok_dir = False
            if dx < 0 and not (dc < 0 and da < 0): ok_dir = False
            if da != dc: ok_mag = False
            tot_px += abs(dx); tot_cnt += abs(dc)
        log("emulator sensitivity: %d counts / %d px = %.3f counts per pixel" % (tot_cnt, tot_px, tot_cnt / float(tot_px) if tot_px else 0))
        check(ok_dir, "direction: pointer right -> X counter up -> ang up; left -> down")
        check(ok_mag, "magnitude: ang delta == counter delta on every step (1 unit per count, 1024 counts per turn)")
        # C4 vertical: pointer up / down -> horizon_row ; document the direction
        rows = []; ok_v = True
        for dy in (-40, 40, -40, 40):
            xdo("mousemove", "--window", wid, "300", "250"); time.sleep(0.3)
            wr8("horizon_row", 48); time.sleep(0.2)                 # re-centre the horizon so the 16..80 clamp does not hide a step
            a0, a1, dc, dyc, h0, h1 = move(0, dy)
            rows.append("pointer %+d px: Y counter %+d, horizon %d -> %d" % (dy, dyc, h0, h1))
            if dyc == 0 or h1 == h0: ok_v = False
            if (dyc > 0) != (h1 > h0): ok_v = False
            if h1 - h0 != dyc // 2: ok_v = False
        log("vertical: " + " ; ".join(rows))
        check(ok_v, "vertical look follows the Y counter (horizon_row += dy/2 rows exactly, clamped 16..80); pointer UP = Y counter %s" % ("UP (horizon down the screen = look up)" if "pointer -40 px: Y counter +" in rows[0] else "DOWN"))
        check(rd16("ang") == rd16("ang"), "frames keep rendering: frames %d" % rd16("frames"))
        # C5 left click -> fire: ammo - 1
        am0 = rd8("g_ammo")
        xdo("mousedown", "1"); time.sleep(0.15); xdo("mouseup", "1")
        t = time.time(); wf = 0
        while time.time() - t < 1.5 and rd8("g_ammo") == am0:
            wf = max(wf, rd8("g_wframe")); time.sleep(0.05)
        shot()
        check(rd8("g_ammo") == am0 - 1, "left click -> KEY_FIRE latch -> fire_action: ammo %d -> %d (weapon frame seen %d)" % (am0, rd8("g_ammo"), max(wf, rd8("g_wframe"))))
        # C6 right click in front of the door: cell (15, 3) of level 01, player at (14.5, 3.5) facing east
        cell = LEVEL + 8 + 3 * 32 + 15
        wr(0x5802, [0x80, 0x0E, 0x80, 0x03, 0, 0]); wr8("g_moved", 1); time.sleep(0.4)
        c0 = rd(cell)[0]; shot()
        xdo("mousedown", "3"); time.sleep(0.15); xdo("mouseup", "3")
        t = time.time()
        while time.time() - t < 1.5 and rd(cell)[0] == c0: time.sleep(0.05)
        c1 = rd(cell)[0]; shot(); time.sleep(0.3); shot()
        check(c0 == 8 and c1 == 0, "right click -> KEY_USE latch -> use_action: door cell (15,3) code %d -> %d (8 = unlocked door, 0 = open), g_door_n %d" % (c0, c1, rd8("g_door_n")))
        # C7 I toggles OFF (debounce passed), indicator cleared, pointer no longer turns
        xdo("keydown", "i"); time.sleep(0.3); xdo("keyup", "i"); time.sleep(0.5)
        check(rd8("opt_mouse_b") == 0, "I pressed again -> opt_mouse_b %d (OFF)" % rd8("opt_mouse_b"))
        check(not band_m(), "HUD indicator cleared")
        a0 = rd16("ang"); xdo("mousemove", "--window", wid, "300", "250"); time.sleep(0.1); xdo("mousemove_relative", "--", "150", "0"); time.sleep(0.4)
        check(rd16("ang") == a0, "OFF again: 150 px -> ang %d -> %d" % (a0, rd16("ang")))
        shot()
        # E: fps ON vs OFF (same pose, pointer still)
        wr(0x5802, [0x80, 0x03, 0x80, 0x07, 0, 0]); wr8("g_moved", 1); time.sleep(0.5)
        def fps(secs=3.0):
            f0, t0_ = rd16("frames"), rd16("ticks"); time.sleep(secs); f1, t1_ = rd16("frames"), rd16("ticks")
            dt = (t1_ - t0_) & 0xFFFF
            return 50.0 * ((f1 - f0) & 0xFFFF) / dt if dt else 0.0, dt
        fo, dto = fps(); wr8("opt_mouse_b", 1); time.sleep(0.3); fn, dtn = fps(); wr8("opt_mouse_b", 0)
        log("E fps at the start pose: OFF %.2f fps (%d ticks window) ; ON %.2f fps (%d ticks) ; delta %+.2f" % (fo, dto, fn, dtn, fn - fo))
        check(abs(fn - fo) <= 1.0, "fps ON vs OFF within 1.0 fps (--vo xwindows emulation runs at ~12 fps with ~0.5 fps jitter; the exact cost is oracle A's T-state count: ~900 T = 0.06%% of a frame)")
        (NIGHT / "N5_timing_live.out").write_text("fps start pose: OFF %.2f fps over %d ticks ; ON %.2f fps over %d ticks ; delta %+.2f fps\n" % (fo, dto, fn, dtn, fn - fo))
    finally:
        try: q("exit-emulator", 0.3); sock[0].close()
        except Exception: pass
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill()
        subprocess.run(["pkill", "-x", "zesarux"], capture_output=True)
        xvfb.kill()
    n = nshot[0]
    if n:
        fr = max(1, round(n / 8.0))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fr), "-i", str(frames_dir / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(NIGHT / "N5_mouse.mp4")], check=False)
        mp4 = NIGHT / "N5_mouse.mp4"
        log("F clip: %d frames at %d fps = %.1f s -> %s (%d bytes)" % (n, fr, n / float(fr), mp4, mp4.stat().st_size if mp4.exists() else 0))
    log("RESULT " + ("PASS %d checks" % (len(out)) if not fails else "FAIL %d: %s" % (len(fails), "; ".join(fails))))
    (NIGHT / "N5_live.out").write_text("\n".join(out) + "\n")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
