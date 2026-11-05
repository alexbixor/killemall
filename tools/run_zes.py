#!/usr/bin/env python3
"""run_zes.py — headless ZEsarUX run with screenshot via the ZRCP remote protocol (works for 48k/128k .tap and Next .nex).

usage: run_zes.py <file.tap|.nex> <machine 48k|128k|TBBlue> <seconds> <out.png> [--mp4 out.mp4 --fps 10]
Starts zesarux with --vo null (no window needed), --ao null, ZRCP on a free port, loads the file (smartload), waits,
then asks ZRCP for a screen capture ("get-screen" via save-screen / 'send-keys-...' not needed).  Screenshot path: we use
the ZRCP command `save-screen` if present, else `get-screen-image`?  -> probed at runtime: the script prints available
commands if the capture command is unknown.
"""
import socket, subprocess, sys, time, os, argparse, re, pathlib
ZES = os.path.expanduser("~/work/killemall/tools/zesarux/zesarux")

def zrcp(sock, cmd, wait=0.3):
    sock.sendall((cmd + "\n").encode()); time.sleep(wait)
    out = b""
    sock.settimeout(2.0)
    try:
        while True:
            chunk = sock.recv(65536)
            if not chunk: break
            out += chunk
            if out.rstrip().endswith(b"command>"): break
    except socket.timeout:
        pass
    return out.decode(errors="replace")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("machine"); ap.add_argument("seconds", type=float); ap.add_argument("out")
    ap.add_argument("--mp4"); ap.add_argument("--fps", type=int, default=10); ap.add_argument("--port", type=int, default=10100)
    a = ap.parse_args()
    f = str(pathlib.Path(a.file).resolve()); out = str(pathlib.Path(a.out).resolve())
    cmd = [ZES, "--noconfigfile", "--vo", "null", "--ao", "null", "--machine", a.machine, "--nosplash", "--nowelcomemessage",
           "--disable-all-first-aid", "--enable-remoteprotocol", "--remoteprotocol-port", str(a.port), "--quickexit", f]
    log = open("/tmp/zes_run.log", "w")
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(ZES))
    s = None
    for _ in range(60):
        try:
            s = socket.create_connection(("127.0.0.1", a.port), timeout=1); break
        except OSError:
            time.sleep(0.25)
    if s is None:
        p.kill(); print("ZRCP not reachable; log tail:"); print(open("/tmp/zes_run.log").read()[-600:]); sys.exit(1)
    banner = zrcp(s, "", 0.5)
    frames = []
    t0 = time.time(); i = 0
    tmpdir = pathlib.Path("/tmp/zes_frames"); tmpdir.mkdir(exist_ok=True)
    for old in tmpdir.glob("*.pbm"): old.unlink()
    while time.time() - t0 < a.seconds:
        if a.mp4:
            fn = tmpdir / f"f{i:05d}.pbm"
            r = zrcp(s, f"save-screen {fn}", 0.05); i += 1
            frames.append(fn)
            time.sleep(max(0, 1.0 / a.fps - 0.05))
        else:
            time.sleep(0.25)
    r = zrcp(s, f"save-screen {out}.pbm", 0.5)
    if "rror" in r or not os.path.exists(out + ".pbm"):
        print("save-screen reply:", r.strip()[:300]); hl = zrcp(s, "help", 1.0)
        print("commands:", ", ".join(re.findall(r"^(\S+)", hl, re.M))[:1500])
    zrcp(s, "exit-emulator", 0.3); s.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
    if os.path.exists(out + ".pbm"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out + ".pbm", "-vf", "scale=iw*3:ih*3:flags=neighbor", out], check=False)
        os.unlink(out + ".pbm"); print("saved", out)
    if a.mp4 and frames:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(a.fps), "-pattern_type", "glob", "-i", str(tmpdir / "f*.pbm"),
                        "-vf", "scale=iw*3:ih*3:flags=neighbor,format=yuv420p", "-c:v", "libx264", "-crf", "20", a.mp4], check=False)
        print("mp4", a.mp4, "frames", len(frames))

if __name__ == "__main__":
    main()
