#!/usr/bin/env python3
"""fe_zrcp_help.py - start ZEsarUX headless (no tape) and list the ZRCP commands relevant to key injection."""
import socket, subprocess, time, os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
PORT = 10141
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_fehelp.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); print("no ZRCP"); sys.exit(1)
zrcp(s, "", 0.5)
h = zrcp(s, "help", 1.0)
for line in h.splitlines():
    l = line.lower()
    if "key" in l or "joy" in l or "screen" in l or "smart" in l:
        print(line.strip())
for c in ("send-keys-ascii", "send-keys-event", "send-keys-string", "set-joystick", "smartload"):
    print("====", c); print(zrcp(s, "help " + c, 0.4).split("command>")[0].strip())
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
