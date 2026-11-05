#!/usr/bin/env python3
"""run128.py - Kill'em all 128K real run in ZEsarUX (--machine 128k) over ZRCP (lane T4).
Flow: autoload build/killemall128_m2.tap -> wait for PC >= 32768 (engine running = menu) -> PNG kea128_title.png /
kea128_menu.png -> 60-frame AY register trace (get-io-ports, the emulator's own AY state) -> press M (START) ->
PNG kea128_game.png -> AY trace in game -> fps from `frames` over 4 s -> 24 random-moment grabs (tearing).
Everything is appended to build/run128.out; the caller reads that file (keep tool output small)."""
import socket, subprocess, time, os, sys, pathlib, re, random, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, scr_to_png, ZES
from fe_shot import ports
ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 10150 + random.randint(0, 40)
TAP = str(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "build/killemall128_m2.tap"))
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea128.sym").read_text(), re.M)}
LOG = open(ROOT / "build/run128.out", "a")
def log(*a):
    print(*a, file=LOG, flush=True)

def main():
    log("== run128 %s %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), TAP))
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--joystickemulated", "Kempston", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", TAP]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_run128.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(80):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); log("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    def regs():
        return zrcp(s, "get-registers", 0.2).split("command>")[0].strip().replace("\n", " ")
    def pages():
        return zrcp(s, "get-memory-pages", 0.2).split("command>")[0].strip()
    def io():
        r = zrcp(s, "get-io-ports", 0.2).split("command>")[0]
        m7 = re.search(r"7FFD port: (\w+)", r)
        ay = re.findall(r"\n\s*([0-9A-F]{2}):\s+([0-9A-F]{2})", r)
        return (m7.group(1) if m7 else "?"), {int(k, 16): int(v, 16) for k, v in ay}
    def rd(addr, n, wait=0.3):
        r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
        h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
        return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""
    def grab_png(name):
        scr = rd(16384, 6912, 1.5)
        if len(scr) == 6912: scr_to_png(scr, str(ROOT / "build" / name)); log("png", name)
        return scr
    def tap_keys(keys=(), joy=0, hold=0.15, gap=0.4):
        zrcp(s, "set-ui-io-ports " + ports(keys, joy), 0.05); time.sleep(hold)
        zrcp(s, "set-ui-io-ports " + ports(), 0.05); time.sleep(gap)
    def ay_trace(tag, n=60, dt=0.02):
        tr = []
        for _ in range(n):
            b, ay = io(); tr.append([ay.get(i, -1) for i in range(14)]); time.sleep(dt)
        vols = set((t[8], t[9], t[10]) for t in tr); tones = set(tuple(t[0:6]) for t in tr)
        mix = set(t[7] for t in tr)
        log("AY %s: %d polls, distinct (vA,vB,vC) %d, distinct tone sets %d, mixers %s, 7FFD %s" % (tag, n, len(vols), len(tones), sorted(mix), b))
        log("AY %s first %s" % (tag, tr[0])); log("AY %s last  %s" % (tag, tr[-1]))
        return tr
    # --- wait for the engine
    t0 = time.time(); started = False
    while time.time() - t0 < 90:
        m = re.search(r"PC=([0-9a-fA-F]{4})", regs())
        if m and int(m.group(1), 16) >= 0x8000 and int(m.group(1), 16) < 0xC000:
            started = True; break
        time.sleep(0.5)
    log("engine running after %.1f s: %s | %s | pages %s | 7FFD %s BANKM %s" % (time.time() - t0, started, regs()[:70], pages(), io()[0], rd(23388, 1).hex()))
    time.sleep(1.5)
    grab_png("kea128_title.png")
    menu_tr = ay_trace("menu")
    log("bank1 table @49152 (mapped bank 0 now, should NOT be the table):", rd(49152, 8).hex())
    # --- START: menu item 0 is START, fire (Kempston) selects
    for k in (("SPACE",), ("ENTER",), ("SPACE",)):          # fe_keys: SPACE / ENTER / fire = select (START is item 0)
        tap_keys(keys=k, hold=0.25, gap=1.2)
        fr = int.from_bytes(rd(SYM["frames"], 2), "little")
        log("after %s: frames %d | %s | pages %s" % (k[0], fr, regs()[:40], pages()))
        if fr: break
    time.sleep(1.0)
    grab_png("kea128_game.png")
    game_tr = ay_trace("game")
    # --- fps from frames over 4 s
    f0 = int.from_bytes(rd(SYM["frames"], 2), "little"); t1 = time.time(); time.sleep(4.0)
    f1 = int.from_bytes(rd(SYM["frames"], 2), "little"); dt = time.time() - t1
    log("fps: frames %d -> %d in %.2f s = %.2f fps (wall clock; emulator at real speed)" % (f0, f1, dt, (f1 - f0) / dt))
    # --- tearing: 24 random-moment grabs of the 192x96 window (M2.5C: byte columns 4..27)
    res = []
    for i in range(24):
        time.sleep(random.uniform(0.05, 0.35))
        rows = []
        for y in range(8, 104):
            addr = 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + 4
            rows.append(rd(addr, 24, 0.02) or b"\0" * 24)
        cols = [sum(1 for r in rows if r[c]) for c in range(24)]
        res.append((sum(cols), sum(1 for c in cols if c == 0)))
    log("tear: grabs %d, nonzero bytes min/max %d/%d, grabs with a blank column %d, grabs <40%% set %d" % (
        len(res), min(r[0] for r in res), max(r[0] for r in res), sum(1 for r in res if r[1]), sum(1 for r in res if r[0] < 0.4 * 2304)))
    log("level_data byte0 %s health %s level %s | %s" % (rd(SYM["level_data"], 1).hex(), rd(SYM["health"], 1).hex(), rd(SYM["level"], 1).hex(), regs()[:60]))
    json.dump({"menu": menu_tr, "game": game_tr}, open(ROOT / "build/run128_ay.json", "w"))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    log("== done")

if __name__ == "__main__":
    main()
