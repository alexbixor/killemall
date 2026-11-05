#!/usr/bin/env python3
"""fe_zrcp_probe2.py - probe ZRCP key injection: get-ui-io-ports format, set-ui-io-ports, send-keys-string with spaces."""
import socket, subprocess, time, os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run48 import zrcp, ZES
PORT = 10142
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "48k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit"]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_feprobe2.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
if s is None:
    p.kill(); print("no ZRCP"); sys.exit(1)
zrcp(s, "", 0.5)
def show(c, w=0.4):
    print("====", c); print(zrcp(s, c, w).split("command>")[0].strip())
show("help get-ui-io-ports"); show("help set-ui-io-ports"); show("get-ui-io-ports")
show("help set-joystick"); show("help read-memory"); show("help write-memory"); show("help get-cpu-core-name")
# which commands exist containing 'joy'
h = zrcp(s, "help", 1.0)
print("==== joy/key related:"); print("\n".join(l for l in h.splitlines() if "joy" in l.lower()))
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
