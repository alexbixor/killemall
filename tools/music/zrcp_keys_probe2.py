#!/usr/bin/env python3
"""zrcp_keys_probe2.py - T3: try set-ui-io-ports / send-keys-string to press G in headless ZEsarUX (snd_test128.tap)."""
import socket, subprocess, time, os, sys, pathlib
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10124
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

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

def mem(s, addr, n):
    r = zrcp(s, "read-memory %d %d" % (addr, n), 0.3)
    h = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    return bytes.fromhex(h[:2 * n]) if len(h) >= 2 * n else b""

tap = str(ROOT / "build/snd_test128.tap")
cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", "128k", "--nosplash", "--nowelcomemessage",
       "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_keys2.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
zrcp(s, "", 0.5)
print(zrcp(s, "help set-ui-io-ports", 0.3).split("command>")[0].strip()[:500])
print(zrcp(s, "help get-ui-io-ports", 0.3).split("command>")[0].strip()[:300])
print(zrcp(s, "help send-keys-string", 0.3).split("command>")[0].strip()[:300])
time.sleep(20)
print("ports idle:", zrcp(s, "get-ui-io-ports", 0.3).split("command>")[0].strip()[:200])
print("cell0 before:", mem(s, 22528, 1).hex())
# row for A S D F G is port 0xFDFE = row 1; G = bit 4 -> value 0xEF (active low)
r = zrcp(s, "set-ui-io-ports FF EF FF FF FF FF FF FF", 0.05)
print("set reply:", r.split("command>")[0].strip()[:100])
print("ports pressed:", zrcp(s, "get-ui-io-ports", 0.05).split("command>")[0].strip()[:200])
time.sleep(0.3)
zrcp(s, "set-ui-io-ports FF FF FF FF FF FF FF FF", 0.05)
time.sleep(1.0)
print("cell0 after set-ui-io-ports G:", mem(s, 22528, 1).hex())
zrcp(s, "send-keys-string g", 0.1); time.sleep(1.0)
print("cell0 after send-keys-string g:", mem(s, 22528, 1).hex())
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
