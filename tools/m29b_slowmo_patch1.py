#!/usr/bin/env python3
"""one-off: make m29b_slowmo.py frame-exact (4 Nov 2026). (1) a new frame is detected when `frames` changes; the screen then
holds the FINISHED previous frame, so pair that image with the camera values recorded for the previous frame; (2) after the
detection run 600 more opcodes so glide_in has written the camera position into posx before it is read; (3) chunk size per
machine: 4000 opcodes at 3.5 MHz (~0.4 tick), 20000 at 28 MHz."""
import pathlib
p = pathlib.Path(__file__).resolve().parent / "m29b_slowmo.py"; s = p.read_text()
old = '''v0 = st(); last_f = v0[1]; idx = []; runs = 0; w0 = time.time()
while True:
    zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.0, 2.0)                        # re-assert the key inside cpu-step mode
    q("run %d" % N, 0.0, 60.0); runs += 1
    v = st()
    if v[1] != last_f:
        if v[1] != last_f + 1: print("WARNING: frames jumped %d -> %d (N too large)" % (last_f, v[1]), flush=True)
        last_f = v[1]; scr = OUT / ("f%03d.scr" % len(idx))
        h = "".join(ch for ch in q("read-memory 16384 6912", 0.05, 15.0) if ch in "0123456789ABCDEFabcdef")[:2 * 6912]
        scr.write_bytes(bytes.fromhex(h) if len(h) == 2 * 6912 else b"")        # ULA screen: works in cpu-step mode on TBBlue too (save-screen does not)
        idx.append({"ticks": v[0] - v0[0], "frames": v[1] - v0[1], "x": v[2] / 256.0, "y": v[3] / 256.0, "scr": scr.name})
    if v[0] - v0[0] >= TICKS: break
'''
new = '''v0 = st(); last_f = v0[1]; idx = []; runs = 0; w0 = time.time(); prev = None
while True:
    zrcp(s, "set-ui-io-ports " + ports(("Q",)), 0.0, 2.0)                        # re-assert the key inside cpu-step mode
    q("run %d" % N, 0.0, 60.0); runs += 1
    v = st()
    if v[1] != last_f:
        if v[1] != last_f + 1: print("WARNING: frames jumped %d -> %d (N too large)" % (last_f, v[1]), flush=True)
        last_f = v[1]
        # frame k has just begun (frames++ is the first thing main does): the screen holds the FINISHED frame k-1, which
        # became visible a moment ago; pair it with the camera values recorded when frame k-1 started rendering.
        if prev is not None:
            scr = OUT / ("f%03d.scr" % len(idx))
            h = "".join(ch for ch in q("read-memory 16384 6912", 0.05, 15.0) if ch in "0123456789ABCDEFabcdef")[:2 * 6912]
            scr.write_bytes(bytes.fromhex(h) if len(h) == 2 * 6912 else b"")    # ULA screen: works in cpu-step mode on TBBlue too (save-screen does not)
            idx.append({"ticks": v[0] - v0[0], "frames": v[1] - v0[1] - 1, "x": prev[1], "y": prev[2], "cam_ticks": prev[0] - v0[0], "scr": scr.name})
        q("run 600", 0.0, 60.0)                                                  # past glide_in: posx/posy now hold frame k's camera position
        w = st(); prev = (w[0], w[2] / 256.0, w[3] / 256.0)
    if v[0] - v0[0] >= TICKS: break
'''
assert old in s, "anchor"
s = s.replace(old, new)
s = s.replace('N = int(sys.argv[3]) if len(sys.argv) > 3 else 20000', 'N = int(sys.argv[3]) if len(sys.argv) > 3 else {"48k": 4000, "128k": 4000, "next": 20000}[sys.argv[1]]')
p.write_text(s); print("m29b_slowmo.py patched")
