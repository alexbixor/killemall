#!/bin/bash
# deck_probe_m28e.sh - READ-ONLY, runs ON the Deck ('bash -s'). Two questions:
#  (1) Who is the Moonlight client right now (which device Alex plays from)?
#  (2) Is the Steam virtual pad js0 (event7) QUIET? The launcher maps its left-stick X axis to Z/X (--joystickkeybt -0 122 / +0 120).
#      If the axis jitters around rest, ZEsarUX may keep "releasing" z/x and cancel any real Z/X key press (hypothesis).
#      Reads the current absolute axis values (EVIOCGABS) and counts events for 15 s. No key codes are logged except Z/X/Q/A/O/P.
set -u
echo "deck time $(date -u +%H:%MZ)"
echo "--- Sunshine peers (who is connected)"
ss -tunp 2>/dev/null | grep -E ":4798[4-9]|:4799[0-9]|:4800[0-9]|:4801[0-9]" | awk '{print $1, $5, $6}' | sort -u | head -8
echo "--- tailscale status (peer names for the addresses above)"
tailscale status 2>/dev/null | grep -v -E "offline|^$" | awk '{print $1, $2, $5}' | head -12
echo "--- ACLs on the input nodes (can alex read them without sudo?)"
getfacl -p /dev/input/event7 /dev/input/event8 2>/dev/null | grep -E "^# file|^user:alex" 
echo "--- js0 absolute axis state now + 15 s of events (read-only). Needs read access; falls back to sudo -n."
cat > /tmp/hal_js0_probe.py <<'EOF'
import fcntl, struct, os, select, time, sys
dev = "/dev/input/event7"
try:
    fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
except PermissionError:
    sys.exit("NOPERM")
names = {0:"ABS_X(left X -> Z/X)",1:"ABS_Y(left Y)",2:"ABS_Z(LT)",3:"ABS_RX(right X)",4:"ABS_RY(right Y)",5:"ABS_RZ(RT)",16:"HAT0X",17:"HAT0Y"}
for code,name in names.items():
    buf = bytearray(24)
    try:
        fcntl.ioctl(fd, 0x80184540 + code, buf)
        v,mn,mx,fuzz,flat,res = struct.unpack("6i", buf)
        print("  %-22s value=%6d  range %d..%d fuzz=%d flat=%d" % (name, v, mn, mx, fuzz, flat))
    except OSError as e:
        print("  %-22s ioctl failed: %s" % (name, e))
# keys currently down (EVIOCGKEY)
kbuf = bytearray(96)
fcntl.ioctl(fd, 0x80604518, kbuf)
down = [i for i in range(768) if kbuf[i//8] >> (i%8) & 1]
print("  buttons down now:", down if down else "none")
print("  listening 15 s for events ...")
t0 = time.time(); counts = {}; vals = {}
while time.time() - t0 < 15:
    r,_,_ = select.select([fd], [], [], 0.5)
    if not r: continue
    data = os.read(fd, 24*64)
    for i in range(0, len(data) - 23, 24):
        sec,usec,typ,code,val = struct.unpack("llHHi", data[i:i+24])
        if typ == 0: continue
        k = (typ, code); counts[k] = counts.get(k, 0) + 1
        vals.setdefault(k, []).append(val)
if not counts:
    print("  no events in 15 s: the pad is quiet (axes/buttons untouched)")
for (typ,code),n in sorted(counts.items()):
    v = vals[(typ,code)]
    print("  type %d code %d (%s): %d events, values min %d max %d" % (typ, code, names.get(code, "?") if typ == 3 else "key", n, min(v), max(v)))
EOF
out=$(python3 /tmp/hal_js0_probe.py 2>&1)
if [ "$out" = "NOPERM" ]; then echo "(alex cannot read event7 directly; using sudo -n, read-only)"; sudo -n python3 /tmp/hal_js0_probe.py 2>&1; else echo "$out"; fi
rm -f /tmp/hal_js0_probe.py
echo "--- Steam: controller settings that matter in Desktop mode"
grep -h -i -E "\"(SteamController_|DesktopConfig|GamepadDesktop|ControllerDesktop)[^\"]*\"" ~/.steam/steam/config/config.vdf 2>/dev/null | head -10 | cut -c1-120
echo "--- sunshine.conf input-related keys"
grep -v "^#" ~/.config/sunshine/sunshine.conf 2>/dev/null | grep -i -E "key|controller|gamepad|mouse|input|scancode" | cut -c1-120
date -u +%H:%MZ
