#!/usr/bin/env python3
"""snd_emu128.py - T3: 128K emulator smoke test with the real AY: boot build/snd_test128.tap in ZEsarUX (128k), read the
AY shadow registers + player state over ZRCP, press G (game track) and 0 (SFX 10) via set-ui-io-ports (ZRCP keyboard
matrix: 9 unseparated hex bytes, rows FEFE FDFE FBFE F7FE EFFE DFFE BFFE 7FFE + joystick), and show that the ISR runs,
the music advances, the track switches and the SFX pre-empts channel C. Output: build/snd_emu_128k.out."""
import socket, subprocess, time, os, sys, pathlib, re
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10122
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/snd_test128.sym").read_text(), re.M)}
IDLE = "FFFFFFFFFFFFFFFF00"

def zrcp(s, cmd, wait=0.3):
    s.sendall((cmd + "\n").encode()); time.sleep(wait)
    out = b""; s.settimeout(2.0)
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            out += c
            if out.rstrip().endswith(b"command>"): break
    except socket.timeout:
        pass
    return out.decode(errors="replace")

def mem(s, addr, n, wait=0.3):
    r = zrcp(s, "read-memory %d %d" % (addr, n), wait)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""

def press(s, row, bit, hold=0.25):
    rows = [0xFF] * 8; rows[row] &= ~(1 << bit)
    zrcp(s, "set-ui-io-ports " + "".join("%02X" % r for r in rows) + "00", 0.02)
    time.sleep(hold)
    zrcp(s, "set-ui-io-ports " + IDLE, 0.02)

def main():
    tap = str(ROOT / "build/snd_test128.tap")
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_snd128.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    time.sleep(float(os.environ.get("LOADWAIT", "20")))
    def state(tag):
        regs = mem(s, SYM["ay_regs"], 12); mo = mem(s, SYM["mus_on"], 1); opos = mem(s, SYM["mus_opos"], 2); sp = mem(s, SYM["sfx_ptr"], 2)
        cell0 = mem(s, 22528, 1)
        print("%-16s ay_regs %s  mus_on %s  opos %04x  sfx_ptr %04x  cell0 %s" % (tag, regs.hex(" "), mo.hex(), int.from_bytes(opos, "little"), int.from_bytes(sp, "little"), cell0.hex()))
        return regs
    r0 = state("menu t0")
    time.sleep(2.0)
    r1 = state("menu t2")
    press(s, 1, 4)                                   # G (row FDFE bit 4) -> game track
    time.sleep(1.0)
    r2 = state("after G (game)")
    time.sleep(1.0)
    r3 = state("game +1s")
    game_started = int.from_bytes(mem(s, SYM["mus_opos"], 2), "little") >= SYM["game_order"] and mem(s, 22528, 1) == b"\x0a"
    print("game track running after G:", game_started)
    # SFX 10 (player death, 31 frames = 620 ms): press 0 (row EFFE bit 0), then poll the C registers quickly
    press(s, 4, 0, hold=0.08)
    seen = []
    for i in range(10):
        regs = mem(s, SYM["ay_regs"], 12, wait=0.02)
        if len(regs) == 12:
            seen.append(regs)
            print("  poll %d: C period %4d  R6 %2d  R7 %02x  R10 %2d" % (i, regs[4] | (regs[5] << 8), regs[6], regs[7], regs[10]))
    attr = mem(s, 22528, 16)
    print("attr row 0 (cell 11 = SFX 10 marker 70):", attr.hex(" "))
    sfx_seen = any(((r[5] << 8) | r[4]) >= 250 and ((r[5] << 8) | r[4]) <= 1200 and r[10] >= 8 for r in seen)
    print("SFX 10 visible on channel C during the polls:", sfx_seen)
    time.sleep(1.0)
    state("after sfx")
    print("music registers change over time:", (r0 != r1) and (r2 != r3))
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()

if __name__ == "__main__":
    main()
