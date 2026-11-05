#!/usr/bin/env python3
"""snd_emu.py - T3: boot build/snd_test48.tap (48k) / build/snd_test128.tap (128k) headless in ZEsarUX via ZRCP, press keys,
grab the attribute row 0 (progress cells) + registers to prove the tapes autostart and run. Output: build/snd_emu_<m>.out."""
import socket, subprocess, time, os, sys, pathlib
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")
PORT = 10121

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

def main():
    machine = sys.argv[1]; tap = str(pathlib.Path(sys.argv[2]).resolve()); keys = sys.argv[3] if len(sys.argv) > 3 else ""
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", machine, "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT), "--quickexit", tap]
    p = subprocess.Popen(cmd, stdout=open("/tmp/zes_snd.log", "w"), stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("no ZRCP"); sys.exit(1)
    zrcp(s, "", 0.5)
    time.sleep(float(os.environ.get("LOADWAIT", "10")))
    r = zrcp(s, "get-registers", 0.3)
    print("regs after load:", r.strip().splitlines()[0][:100] if r.strip() else r)
    for k in keys.split(","):
        if k:
            zrcp(s, "send-keys-ascii %s" % k, 0.1); time.sleep(0.7)
    time.sleep(1.5)
    r = zrcp(s, "get-registers", 0.3)
    print("regs:", r.strip().splitlines()[0][:100] if r.strip() else r)
    r = zrcp(s, "read-memory 22528 32", 0.5)
    hexs = "".join(ch for ch in r.split("command>")[0] if ch in "0123456789ABCDEFabcdef")
    print("attr row 0:", hexs[:64])
    if machine == "128k":
        r = zrcp(s, "get-audio-buffer-info", 0.3)
        print("audio:", r.split("command>")[0].strip()[:200])
    # read the ticks counter twice to prove the ISR runs
    r1 = zrcp(s, "read-memory %d 2" % int(sys.argv[4]), 0.3) if len(sys.argv) > 4 else ""
    time.sleep(1.0)
    r2 = zrcp(s, "read-memory %d 2" % int(sys.argv[4]), 0.3) if len(sys.argv) > 4 else ""
    print("ticks:", r1.split("command>")[0].strip(), "->", r2.split("command>")[0].strip())
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()

if __name__ == "__main__":
    main()
