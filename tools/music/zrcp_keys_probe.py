#!/usr/bin/env python3
"""zrcp_keys_probe.py - T3: what key-injection commands does this ZEsarUX ZRCP offer, and does send-keys-ascii hold the
key long enough for a once-per-frame poller? Uses the running snd_test128.tap (G key -> cell 0 turns red 0A)."""
import socket, subprocess, time, os, sys, pathlib
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10123
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
p = subprocess.Popen(cmd, stdout=open("/tmp/zes_keys.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
s = None
for _ in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
    except OSError:
        time.sleep(0.25)
zrcp(s, "", 0.5)
h = zrcp(s, "help", 1.0).split("command>")[0]
print("key-ish commands:", [l.strip() for l in h.splitlines() if "key" in l.lower()][:12])
print(zrcp(s, "help send-keys-ascii", 0.3).split("command>")[0].strip()[:400])
print(zrcp(s, "help send-keys-event", 0.3).split("command>")[0].strip()[:400])
time.sleep(20)
print("cell0 before:", mem(s, 22528, 1).hex())
zrcp(s, "send-keys-ascii g", 0.1); time.sleep(1.0)
print("cell0 after send-keys-ascii g:", mem(s, 22528, 1).hex())
zrcp(s, "send-keys-ascii G", 0.1); time.sleep(1.0)
print("cell0 after send-keys-ascii G:", mem(s, 22528, 1).hex())
r = zrcp(s, "send-keys-event 34 1", 0.1); time.sleep(0.3); zrcp(s, "send-keys-event 34 0", 0.1); time.sleep(1.0)
print("send-keys-event reply:", r.split("command>")[0].strip()[:200])
print("cell0 after send-keys-event:", mem(s, 22528, 1).hex())
zrcp(s, "exit-emulator", 0.3); s.close()
try: p.wait(timeout=5)
except subprocess.TimeoutExpired: p.kill()
