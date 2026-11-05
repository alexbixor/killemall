#!/usr/bin/env python3
"""run48.py - run a .tap headless in ZEsarUX (48k), optionally send keys, dump the screen as PNG + ASCII."""
import socket, subprocess, time, os, sys, pathlib
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10120
PAL = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215)]

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

def scr_to_png(scr, out):
    from PIL import Image
    img = Image.new("RGB", (256, 192)); px = img.load()
    for y in range(192):
        base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        for bx in range(32):
            b = scr[base + bx]; attr = scr[6144 + (y // 8) * 32 + bx]
            ink = PAL[attr & 7]; paper = PAL[(attr >> 3) & 7]
            if attr & 64:        # BRIGHT lifts the colours; black stays black (the ULA has no bright black)
                ink = tuple(min(255, c + 40) for c in ink) if any(ink) else ink
                paper = tuple(min(255, c + 40) for c in paper) if any(paper) else paper
            for bit in range(8):
                px[bx * 8 + bit, y] = ink if (b >> (7 - bit)) & 1 else paper
    img.resize((768, 576), Image.NEAREST).save(out)

def ascii_dump(scr, y0=0, y1=112, step=4):
    for y in range(y0, y1, step):
        base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        row = ""
        for bx in range(32):
            b = scr[base + bx]
            row += "".join("#" if (b >> (7 - bit)) & 1 else "." for bit in range(0, 8, 2))
        print("%3d %s" % (y, row))

def main():
    tap = str(pathlib.Path(sys.argv[1]).resolve()); out = str(pathlib.Path(sys.argv[2]).resolve())
    keys = sys.argv[3] if len(sys.argv) > 3 else ""
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_run48.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    time.sleep(float(os.environ.get("LOADWAIT", "8")))
    for k in keys.split(","):
        if k:
            zrcp(s, "send-keys-ascii %s" % k, 0.1); time.sleep(0.6)
    time.sleep(1.0)
    r = zrcp(s, "get-registers", 0.3)
    print("regs:", r.strip().splitlines()[0][:120] if r.strip() else r)
    r = zrcp(s, "read-memory 16384 6912", 1.5)
    hexs = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    scr = bytes.fromhex(hexs[:13824]) if len(hexs) >= 13824 else b""
    print("scr bytes", len(scr))
    if scr:
        scr_to_png(scr, out); ascii_dump(scr); print("saved", out)
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()

if __name__ == "__main__":
    main()
