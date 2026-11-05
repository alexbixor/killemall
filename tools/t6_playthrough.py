#!/usr/bin/env python3
"""t6_playthrough.py - feedback-controlled play-through of a Kill'em all 48K tape in headless ZEsarUX (ZRCP port 10170).
Menu -> START -> loop (~5-6 Hz): read pos/angle/state/things/vis list, Dijkstra path (turn-penalised) on the 32x32 map to the
exit (locked doors need the key -> the key thing becomes the target first), turn/walk with O/P/Q, fight chasing enemies
with M (fire) using the game's own vis list for the crosshair test, grab a 256x192 PNG per iteration + pos log line.
Stops ~2.5 s after the level id changes (LEVEL CLEARED -> level 2 loads). If the exit is not reached by play within
PLAY_LIMIT s the run falls back to a teleport in front of the exit (reported honestly as such).
usage: t6_playthrough.py [tap] [out.mp4] [frames_dir] [label]
  derived outputs next to out.mp4: <stem>_pos.txt, <stem>_report.md, <stem with 'through' dropped>_NN_<event>.png (3x nearest)
Only the emulator this script starts is ever touched; it is closed at the end (checked with pgrep by the caller)."""
import sys, time, pathlib, os, subprocess, math, heapq, re, shutil, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes, load_sym, ports
import numpy as np
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10170
PLAY_LIMIT = float(os.environ.get("PLAY_LIMIT", "150"))   # s of feedback play before the teleport fallback
HARD_LIMIT = PLAY_LIMIT + 45

tap = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/killemall48_m2.tap")
mp4 = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "build/m2_playthrough.mp4"))
fd = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/kea_play")
label = sys.argv[4] if len(sys.argv) > 4 else ""
stem = mp4.stem
shots_prefix = re.sub(r"through$", "", stem)             # m2_playthrough -> m2_play
poslog_path = mp4.with_name(stem + "_pos.txt")
report_path = mp4.with_name(stem + "_report.md")
SYM = load_sym(os.environ.get("SYM", str(ROOT / "build/kea48.sym")))
fd.mkdir(parents=True, exist_ok=True)
for f in fd.glob("f*.png"): f.unlink()

PAL = np.array([(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215),
                (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)], np.uint8)
_ys = np.arange(192); _base = ((_ys & 0xC0) << 5) | ((_ys & 7) << 8) | ((_ys & 0x38) << 2)
_IDX = _base[:, None] + np.arange(32)[None, :]; _AIDX = (_ys // 8)[:, None] * 32 + np.arange(32)[None, :]
def scr_png(scr, path):
    s = np.frombuffer(scr, np.uint8)
    bits = np.unpackbits(s[:6144][_IDX], axis=1)                     # 192 x 256
    a = np.repeat(s[6144:][_AIDX], 8, axis=1)
    col = np.where(bits == 1, a & 7, (a >> 3) & 7) + ((a >> 6) & 1) * 8
    Image.fromarray(PAL[col]).save(path)

class Fast(Zes):
    """Zes with no fixed sleeps: each command returns as soon as the 'command>' prompt arrives (~40 ms per read-memory,
    independent of size). ZEsarUX does NOT pipeline queued commands (measured: a 5-command batch times out), so batch()
    is just a sequential loop kept for call-site clarity."""
    def cmd(self, c, wait=0.0):
        self.s.sendall((c + "\n").encode()); out = b""; self.s.settimeout(4.0)
        while not out.rstrip().endswith(b"command>"):
            ch = self.s.recv(65536)
            if not ch: break
            out += ch
        return out.decode(errors="replace").split("command>")[0]
    def batch(self, cmds):
        return [self.cmd(c) for c in cmds]
    @staticmethod
    def hexbytes(r, n):
        h = "".join(ch for ch in r if ch in "0123456789ABCDEFabcdef")[:2 * n]
        return bytes.fromhex(h) if len(h) == 2 * n else b""
    def rd(self, addr, n):
        return self.hexbytes(self.cmd("read-memory %d %d" % (addr, n)), n)
    def wr(self, addr, data):
        self.cmd("write-memory %d %s" % (addr, " ".join(str(x) for x in data)))
    def setkeys(self, keys):
        self.cmd("set-ui-io-ports " + ports(keys))

# ---------------------------------------------------------------- map / path helpers
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]                          # E S W N  (angle 0, 64, 128, 192)
def passable(c, keys):
    return c == 0 or c == 8 or (c == 9 and keys & 1) or (c == 10 and keys & 2)
def plan(cells, keys, start, goal, heading):
    """turn-penalised Dijkstra over (x, y, dir); goal cell may be any code (exit/door/key cell). -> list of cells or None"""
    sx, sy = start; best = {}; pq = []
    for d in range(4):
        c0 = 0 if d == heading else 2
        heapq.heappush(pq, (c0, sx, sy, d, None)); best[(sx, sy, d)] = (c0, None)
    done = {}
    while pq:
        cost, x, y, d, prev = heapq.heappop(pq)
        if (x, y, d) in done: continue
        done[(x, y, d)] = prev
        if (x, y) == goal:
            path = [(x, y)]; k = (x, y, d)
            while done[k] is not None:
                k = done[k]; path.append((k[0], k[1]))
            return path[::-1]
        for nd in range(4):
            nx, ny = x + DIRS[nd][0], y + DIRS[nd][1]
            if not (0 <= nx < 32 and 0 <= ny < 32): continue
            if (nx, ny) != goal and not passable(cells[ny * 32 + nx], keys): continue
            nc = cost + 1 + (0 if nd == d else 3)
            if (nx, ny, nd) not in done and (best.get((nx, ny, nd), (1e9,))[0] > nc):
                best[(nx, ny, nd)] = (nc, (x, y, d)); heapq.heappush(pq, (nc, nx, ny, nd, (x, y, d)))
    return None
def waypoint(path):
    """end of the first straight run of the path (cell), or the last cell"""
    if len(path) < 2: return path[-1]
    dx, dy = path[1][0] - path[0][0], path[1][1] - path[0][1]; i = 1
    while i + 1 < len(path) and (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]) == (dx, dy): i += 1
    return path[i]
def ang_to(x, y, tx, ty):
    return int(round(math.atan2(ty - y, tx - x) * 128 / math.pi)) & 255
def sdelta(target, a):
    d = (target - a) & 255
    return d - 256 if d > 127 else d
def things_of(buf):
    out = []
    for i in range(16):
        r = buf[i * 8:i * 8 + 8]
        if r[0]: out.append(dict(idx=i, type=r[0], x=(r[1] | r[2] << 8) / 256.0, y=(r[3] | r[4] << 8) / 256.0, state=r[5], hp=r[6]))
    return out
def los(cells, x, y, tx, ty, n=16):
    """no wall cell on the segment (sampled like the game's los_check, finer)"""
    for i in range(1, n):
        sx, sy = x + (tx - x) * i / n, y + (ty - y) * i / n
        if cells[int(sy) * 32 + int(sx)] != 0: return False
    return True

# ---------------------------------------------------------------- run
t_start = time.time()
z = Fast(tap, port=PORT, log="/tmp/zes_play.log")
menu_t = z.wait_running(90, lo=SYM["fe_run"]); print("menu after %.1f s" % menu_t, flush=True); time.sleep(0.5)
n = [0]; poslog = open(poslog_path, "w"); events = []; keyshot = {}
poslog.write("# frame t_wall x y angle health kills   (x/y cells, angle 0..255: 0 east 64 south)\n")
cur_keys = []; last_sent = None
def send(keys):
    global last_sent
    keys = sorted(set(keys))
    if keys != last_sent:
        z.setkeys(keys); last_sent = keys
def frame(scr, p, hk):
    """save one frame + pos log line. p = 5 bytes posx..angle, hk = health..level"""
    scr_png(scr, fd / ("f%04d.png" % n[0]))
    x = (p[0] | p[1] << 8) / 256.0; y = (p[2] | p[3] << 8) / 256.0
    poslog.write("%d %.2f %.3f %.3f %d %d %d\n" % (n[0], time.time() - t_start, x, y, p[4], hk[0], hk[3])); n[0] += 1
def event(name, note=""):
    if name not in keyshot: keyshot[name] = n[0] - 1
    events.append((n[0] - 1, round(time.time() - t_start, 1), name, note)); print("  [%5.1fs f%04d] %s %s" % (time.time() - t_start, n[0] - 1, name, note), flush=True)

# title/menu: ~1.5 s of frames, then START (SPACE)
for _ in range(8):
    r = z.batch(["read-memory 16384 6912", "read-memory %d 5" % SYM["posx"], "read-memory %d 5" % SYM["health"]])
    scr, p, hk = z.hexbytes(r[0], 6912), z.hexbytes(r[1], 5), z.hexbytes(r[2], 5)
    if scr and p and hk: frame(scr, p, hk)
    time.sleep(0.1)
event("menu")
z.setkeys(["SPACE"]); time.sleep(0.15); z.setkeys([]); time.sleep(0.8)
ld = z.rd(SYM["level_data"], 9 + 1024); level0 = ld[0]; cells = bytearray(ld[9:9 + 1024])
exits = [(i % 32, i // 32) for i, c in enumerate(cells) if c == 12]; exit_cell = exits[0] if exits else None
print("level id %d, start (%d,%d) angle %d, %d things, exit %s" % (ld[0], ld[5], ld[6], ld[7], ld[8], exit_cell), flush=True)
event("start", "level id %d" % ld[0])

t_play0 = time.time(); last_pos = None; last_move_t = time.time(); stuck_n = 0; mode = "play"; fallback = False
deaths = 0; door_prev = 0; doors_max = 0; keys_prev = 0; kills_prev = 0; health_prev = 100; cleared_t = None; level_changed_t = None
iter_t = []; shots_fired = 0; ammo_prev = 50; target_desc = ""; exit_t = None; prev_cells_sig = None
while True:
    t_it = time.time(); tw = t_it - t_start
    if tw > HARD_LIMIT: event("hard-limit"); break
    r = z.batch(["read-memory %d 5" % SYM["posx"], "read-memory %d 75" % SYM["health"], "read-memory %d 346" % SYM["things"],
                 "read-memory 16384 6912", "read-memory %d 2" % SYM["level_data"]])
    p, hk, tv, scr, ldh = (z.hexbytes(r[0], 5), z.hexbytes(r[1], 75), z.hexbytes(r[2], 346), z.hexbytes(r[3], 6912), z.hexbytes(r[4], 2))
    if not (p and hk and tv and scr and ldh): continue
    frame(scr, p, hk)
    x = (p[0] | p[1] << 8) / 256.0; y = (p[2] | p[3] << 8) / 256.0; ang = p[4]
    health, ammo, kkeys, kills, level = hk[0], hk[1], hk[2], hk[3], hk[4]; zbuf = hk[11:75]
    things = things_of(tv[:128]); nvis = tv[0xF71A - 0xF621]; vis = tv[0xF71B - 0xF621:0xF71B - 0xF621 + 96]
    # ---- events
    if kills != kills_prev: event("kill", "kills=%d health=%d at (%.1f,%.1f)" % (kills, health, x, y)); kills_prev = kills
    if kkeys != keys_prev: event("key", "keys=%d" % kkeys); keys_prev = kkeys
    if ammo < ammo_prev: shots_fired += ammo_prev - ammo
    ammo_prev = ammo
    if health < health_prev: event("hurt", "health %d -> %d" % (health_prev, health))
    if health == 0 and health_prev > 0: deaths += 1; event("died", "deaths=%d" % deaths)
    health_prev = health
    dn = z.hexbytes(z.cmd("read-memory %d 1" % SYM["door_n"]), 1)[0] if n[0] % 3 == 0 else door_prev
    if dn > door_prev: event("door", "doors opened=%d at (%.1f,%.1f)" % (dn, x, y)); doors_max = max(doors_max, dn)
    door_prev = dn                                                        # (door_n drops back to 0 when the next level loads)
    if ldh[0] != level0 or level != 0:
        if level_changed_t is None: level_changed_t = time.time(); event("level-change", "level=%d level_data id=%d" % (level, ldh[0]))
        if time.time() - level_changed_t > 2.5: break
        send([]); time.sleep(0.05); continue
    # "LEVEL CLEARED" shows for 2 s before level++: detect via the exit cell directly ahead becoming the message state (msg_timer)
    if exit_t is None and exit_cell and abs(x - exit_cell[0] - 0.5) < 1.2 and abs(y - exit_cell[1] - 0.5) < 1.2:
        mt = z.hexbytes(z.cmd("read-memory %d 1" % SYM["msg_timer"]), 1)[0]
        if mt > 90: exit_t = time.time(); event("exit", "LEVEL CLEARED message (msg_timer=%d), %s" % (mt, "by teleport" if fallback else "by play"))
    if exit_t is not None: send([]); time.sleep(0.05); continue
    # ---- fallback: teleport in front of the exit
    if mode == "play" and time.time() - t_play0 > PLAY_LIMIT and exit_cell:
        mode = "fallback"; fallback = True; send([])
        ex, ey = exit_cell
        for ddx, ddy, a_ in ((-1, 0, 0), (1, 0, 128), (0, -1, 64), (0, 1, 192)):
            nx, ny = ex + ddx, ey + ddy
            if 0 <= nx < 32 and 0 <= ny < 32 and cells[ny * 32 + nx] == 0: break
        z.wr(SYM["posx"], [0x80, nx]); z.wr(SYM["posy"], [0x80, ny]); z.wr(SYM["angle"], [a_])
        event("teleport", "play limit %.0f s reached -> teleported to (%d.5,%d.5) facing %d (scripted, NOT play)" % (PLAY_LIMIT, nx, ny, a_))
        time.sleep(0.3); send(["Q"]); continue
    if mode == "fallback": send(["Q"]); continue
    # ---- live map (doors opened by bump become 0): refresh cells every ~10 iterations
    if n[0] % 10 == 0:
        c2 = z.rd(SYM["level_data"] + 9, 1024)
        if len(c2) == 1024: cells = bytearray(c2)
    # ---- combat: chasing/attacking enemies near us
    enemies = [t for t in things if t["type"] in (1, 2) and t["state"] != 3]
    near = []
    for t in enemies:
        d = math.hypot(t["x"] - x, t["y"] - y)
        if d < 4.5 and (t["state"] in (1, 2) or d < 2.5) and los(cells, x, y, t["x"], t["y"]): near.append((d, t))
    near.sort(key=lambda e: e[0])
    aim_ok = False
    for i in range(nvis):
        hv, c0, nc, idx = vis[i * 6], vis[i * 6 + 1], vis[i * 6 + 2], vis[i * 6 + 5]
        c0 = c0 - 256 if c0 > 127 else c0
        if c0 <= 33 and c0 + nc >= 31 and zbuf[32] < hv and idx < 16:
            tt = tv[idx * 8:idx * 8 + 8]
            if tt[0] in (1, 2) and tt[5] != 3: aim_ok = True
    keys_now = []
    if near:
        d, t = near[0]
        want = ang_to(x, y, t["x"], t["y"]); dl = sdelta(want, ang)
        tol = max(4, int(math.degrees(math.atan2(0.45, max(d, 0.3))) * 256 / 360))
        if abs(dl) > tol: keys_now.append("P" if dl > 0 else "O")
        if aim_ok or abs(dl) <= tol: keys_now.append("SPACE")
        if d < 0.45: keys_now.append("A")                               # too close: sprites nearer than 0.19 cell are not drawn
        target_desc = "enemy#%d d=%.1f" % (t["idx"], d)
        send(keys_now)
        if abs(dl) > tol and abs(dl) <= 24: time.sleep(0.06); send([k for k in keys_now if k not in ("P", "O")])   # tap
        iter_t.append(time.time() - t_it); continue
    # ---- navigation
    cx, cy = int(x), int(y); heading = int(((ang + 32) & 255) // 64)
    goal = exit_cell; path = plan(cells, kkeys, (cx, cy), goal, heading) if goal else None
    if path is None:                                                     # locked door in the way -> fetch a key thing
        for t in things:
            if t["type"] in (18, 19):
                p2 = plan(cells, kkeys, (cx, cy), (int(t["x"]), int(t["y"])), heading)
                if p2: path = p2; goal = (int(t["x"]), int(t["y"])); break
    if path is None:
        event("no-path", "from (%d,%d)" % (cx, cy)); send([]); time.sleep(0.2); iter_t.append(time.time() - t_it)
        if time.time() - t_play0 > 20: t_play0 -= PLAY_LIMIT                   # force the fallback
        continue
    wp = waypoint(path); wx, wy = wp[0] + 0.5, wp[1] + 0.5
    if (cx, cy) == goal and goal != exit_cell:
        send([]); iter_t.append(time.time() - t_it); continue                   # standing on the key cell: pickup happens
    if len(path) >= 2 and math.hypot(wx - x, wy - y) < 0.3 and len(path) > 2:   # reached the corner: aim at the next run
        wp = waypoint(path[1:] if path[1] == wp else path); wx, wy = wp[0] + 0.5, wp[1] + 0.5
    want = ang_to(x, y, wx, wy); dl = sdelta(want, ang)
    target_desc = "wp (%d,%d) goal %s" % (wp[0], wp[1], goal)
    if abs(dl) > 24: keys_now = ["P" if dl > 0 else "O"]
    elif abs(dl) > 4: keys_now = ["Q", "P" if dl > 0 else "O"]
    else: keys_now = ["Q"]
    # stuck detection: no motion for 2.5 s while trying to walk
    pos_now = (round(x, 2), round(y, 2))
    if pos_now != last_pos: last_pos = pos_now; last_move_t = time.time()
    elif "Q" in keys_now and time.time() - last_move_t > 2.5:
        stuck_n += 1; event("stuck", "at (%.2f,%.2f) ang %d -> back up" % (x, y, ang)); send(["A"]); time.sleep(0.4); send([]); last_move_t = time.time(); continue
    send(keys_now)
    if 4 < abs(dl) <= 24: time.sleep(0.06); send([k for k in keys_now if k not in ("P", "O")])   # short turn tap, keep walking
    iter_t.append(time.time() - t_it)

send([]); t_end = time.time()
final = z.rd(SYM["health"], 5); fh, fa, fk, fkills, flevel = final[0], final[1], final[2], final[3], final[4]
fp = z.rd(SYM["posx"], 5); fx = (fp[0] | fp[1] << 8) / 256.0; fy = (fp[2] | fp[3] << 8) / 256.0
z.close(); print("emulator closed", flush=True)
poslog.close()
frames = n[0]; dur = t_end - t_start; fps = frames / dur
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "%.3f" % fps, "-i", str(fd / "f%04d.png"),
                "-vf", "scale=768:576:flags=neighbor,format=yuv420p", "-c:v", "libx264", "-crf", "18", str(mp4)], check=False)
# key frames (3x nearest)
shot_order = [("menu", "menu"), ("kill", "fight"), ("door", "door"), ("key", "key"), ("exit", "exit"), ("level-change", "level2"), ("teleport", "teleport")]
shots = []; k = 1
for ev, lab in shot_order:
    if ev in keyshot and k <= 5:
        src = fd / ("f%04d.png" % keyshot[ev]); dst = mp4.with_name("%s_%02d_%s.png" % (shots_prefix, k, lab))
        if src.exists(): Image.open(src).resize((768, 576), Image.NEAREST).save(dst); shots.append((dst, keyshot[ev])); k += 1
exit_how = "not reached" if exit_t is None else ("by TELEPORT (scripted fallback)" if fallback else "by play")
pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames,duration,width,height",
                     "-of", "json", str(mp4)], capture_output=True, text=True)
try: probe = json.loads(pr.stdout)["streams"][0]
except Exception: probe = {}
rep = ["# %s - play-through report%s" % (stem, (" (" + label + ")") if label else ""), "",
       "Tape: `%s`  ZEsarUX 13.0 headless, ZRCP port %d, scripted feedback loop (tools/t6_playthrough.py)." % (tap, PORT), "",
       "| metric | value |", "|---|---|",
       "| wall duration recorded | %.1f s (menu reached after %.1f s) |" % (dur, menu_t),
       "| frames captured | %d (%.2f fps capture rate; MP4 encoded at that rate = real time) |" % (frames, fps),
       "| MP4 | `%s` %d bytes, %sx%s, %s frames, %s s |" % (mp4, mp4.stat().st_size if mp4.exists() else 0, probe.get("width"), probe.get("height"), probe.get("nb_frames"), probe.get("duration")),
       "| exit reached | %s%s |" % (exit_how, (" at t=%.1f s (%.1f s after START)" % (exit_t - t_start, exit_t - t_play0)) if exit_t else ""),
       "| level change seen | %s |" % ("yes (level byte %d, level_data id changed)" % flevel if level_changed_t else "no"),
       "| kills | %d (shots fired %d, ammo left %d) |" % (fkills, shots_fired, fa),
       "| final health | %d (deaths: %d) |" % (fh, deaths),
       "| doors opened by bump | %d |" % doors_max, "| keys held at end | %d (b0 red, b1 blue) |" % fk,
       "| final position | (%.2f, %.2f) |" % (fx, fy), "| stuck recoveries | %d |" % stuck_n,
       "| loop iteration | mean %.0f ms (%d iterations) |" % (1000 * sum(iter_t) / max(1, len(iter_t)), len(iter_t)), "",
       "## Events (frame, wall s)", ""] + ["- f%04d %6.1fs %s %s" % e for e in events] + ["", "## Key frames", ""] + \
      ["- `%s` (frame %d)" % (d, f) for d, f in shots] + ["", "Position log: `%s` (frame, wall s, x, y, angle, health, kills)." % poslog_path]
report_path.write_text("\n".join(rep) + "\n")
print("\n".join(rep[:16])); print("frames %d -> %s" % (frames, mp4))
