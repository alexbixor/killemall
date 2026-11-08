#!/bin/bash
# Independent check of the M1.1 claims + copy to the Deck.
# 1) frame-tearing proof: grab the live screen window from ZEsarUX many times at random moments while the game runs; every grab must be a complete frame
#    (never a blank/half-cleared window). Uses the existing framechk helper if present, else a simple non-zero-column count.
# 2) copy the tap to the Deck's zxspectrum folder (alex idle: pgrep guard) and verify md5.
set -u
cd /home/ubuntu/work/killemall
echo "== $(date -u +%H:%M:%SZ)"
echo "-- geo48 on M1.1 (fresh run):"
bash tools/geo48.sh > build/geo48_verify.out 2>&1; grep -c 'mismatches (>2 rows): 0 of 64' build/geo48_verify.out | sed 's/^/views with 0 wrong columns: /'; grep -v ': 0 of 64' build/geo48_verify.out | grep -i mismatch | head -3
echo "-- random-moment screen grabs from the live emulator (tearing check):"
.venv/bin/python - <<'PY' > build/m11_tear.out 2>&1
import socket, subprocess, time, random, os, re, sys
TAP="build/killemall48_m11.tap"; import glob
ZES=(glob.glob("tools/zesarux/zesarux") or glob.glob("tools/zesarux/*/zesarux") or ["tools/zesarux/zesarux"])[0]; PORT=10000+random.randint(0,999)
p=subprocess.Popen([os.path.abspath(ZES),"--noconfigfile","--vo","null","--ao","null","--machine","48k","--nosplash","--nowelcomemessage","--disable-all-first-aid","--enable-remoteprotocol","--remoteprotocol-port",str(PORT),"--quickexit",os.path.abspath(TAP)], cwd=os.path.dirname(os.path.abspath(ZES)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
try:
    s=None
    for _ in range(60):
        try: s=socket.create_connection(("127.0.0.1",PORT),timeout=2); break
        except OSError: time.sleep(0.5)
    if s is None: print("no ZRCP"); sys.exit(1)
    s.settimeout(5); f=s.makefile("rwb",buffering=0)
    def cmd(c):
        f.write((c+"\n").encode()); out=b""
        while not out.rstrip().endswith(b"command>"):
            chunk=s.recv(65536)
            if not chunk: break
            out+=chunk
        return out.decode("latin1")
    cmd("")  # banner
    time.sleep(12)  # let the loader run (autostart) and the engine start
    SCRWIN=16424
    def grab():
        rows=[]
        for y in range(96):            # window rows y=8..103 -> screen address per row
            sy=y+8; addr=16384+((sy&0xC0)<<5)+((sy&7)<<8)+((sy&0x38)<<2)+8
            r=cmd(f"read-memory {addr} 16")
            m=re.search(r"\n([0-9A-Fa-f]{32})",r) or re.search(r"([0-9A-Fa-f]{32})",r)
            rows.append(bytes.fromhex(m.group(1)) if m else b"\x00"*16)
        return rows
    results=[]
    for i in range(24):
        time.sleep(random.uniform(0.05,0.35))
        rows=grab()
        cols=[sum(1 for y in range(96) if rows[y][c]) for c in range(16)]
        empty_cols=sum(1 for c in cols if c==0)
        nz=sum(cols)
        results.append((nz,empty_cols))
    print("grabs:",len(results))
    print("nonzero-bytes per grab (min/max):",min(r[0] for r in results),max(r[0] for r in results))
    print("grabs with any fully-blank byte column:",sum(1 for r in results if r[1]>0))
    print("grabs with <40% window bytes set (half-drawn/cleared):",sum(1 for r in results if r[0]<0.40*1536))
    print("detail:",results)
finally:
    p.kill()
PY
cat build/m11_tear.out | cut -c1-200
echo "-- deck copy:"
if ssh -o ConnectTimeout=8 -o BatchMode=yes ${DECK:?set DECK=user@host} 'pgrep -f "[r]eaper SteamLaunch" >/dev/null && echo BUSY || echo IDLE' | grep -q IDLE; then
  scp -o ConnectTimeout=8 -o BatchMode=yes build/killemall48_m11.tap ${DECK:?set DECK=user@host}:Emulation/roms/zxspectrum/ && echo "scp ok"
  echo "local  $(md5sum build/killemall48_m11.tap | cut -c1-32)"
  ssh -o ConnectTimeout=8 -o BatchMode=yes ${DECK:?set DECK=user@host} 'echo "remote $(md5sum ~/Emulation/roms/zxspectrum/killemall48_m11.tap | cut -c1-32)"; ls ~/Emulation/roms/zxspectrum/'
else
  echo "Deck busy (game running) - copy skipped"
fi
echo "== done $(date -u +%H:%M:%SZ)"
