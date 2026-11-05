#!/usr/bin/env python3
"""zrcp_probe.py - list ZRCP commands related to screen/memory capture and test read-memory of the 48K screen."""
import socket, subprocess, time, os, re, sys
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10111

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

f = "/tmp/kea_smoke/fill48.tap"
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", f]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_probe.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); print("no ZRCP"); sys.exit(1)
zrcp(s, "", 0.5)
hl = zrcp(s, "help", 1.5)
names = re.findall(r"^(\S+)", hl, re.M)
print("ncmds", len(names))
print([n for n in names if re.search(r"screen|image|read-memory|dump|save|video|window|pause|speed|frame|load|smart|reset|key", n)])
time.sleep(5)  # let the tape load
r = zrcp(s, "get-registers", 0.3); print("regs:", r.strip()[:200])
r = zrcp(s, "read-memory 16384 32", 0.3); print("mem16384:", r.strip()[:120])
r = zrcp(s, "read-memory 22528 32", 0.3); print("attr22528:", r.strip()[:120])
for c in ["help save-screen", "help get-screen", "help save-screen-image", "help view-screen"]:
    r = zrcp(s, c, 0.3); print(c, "->", r.strip()[:160].replace("\n", " | "))
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
