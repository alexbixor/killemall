#!/usr/bin/env python3
"""test_game_sprites.py (T1, milestone A) - Python Z80-core test of the z-buffer + scaled masked sprite draw.
Loads build/kea48.tap, runs init_game + render at a viewpoint, then:
  1. zbuf[64] is written by render (non-zero where a wall was hit) and equals the per-column wall height (hcol) seen in the band draw;
  2. renders once with things removed (walls only) and once with one thing placed at a given distance; diffs the back buffer BUF:
     every changed pixel lies inside the sprite's column span and only in columns where zbuf < sprite hv;
  3. measures T-states of draw_things for one sprite at near / mid / far.
usage: test_game_sprites.py   (exit 0 on success; prints the numbers)
"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import load_code, run_until, SYM, ROOT

TRAP = 0x5EF0
# M2.5C geometry: 24 byte columns x 96 B at 0x6100; ray columns are 3 px (byte-rounded 3,3,2,4,4,2,3,3 per 24-px group)
BUF0, BUFCOLS, BUFSTR = 0x6100, 24, 96
PXRAY = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 7, 7, 7]      # pixel 0..23 of a group -> ray 0..7
RAYS_OF = ([0, 1, 2], [3, 4], [5, 6, 7])                                                # byte column (bc % 3) -> rays of the group
ADJ = [0, 0, 0, 1, 1, 2, 2, 2]
SLOTM = [0xE0, 0x1C, 0x03, 0xF0, 0x0F, 0xC0, 0x38, 0x07]
def bytecol_of(c): return 3 * (c >> 3) + ADJ[c & 7]
def rays_of(bc): return [8 * (bc // 3) + r for r in RAYS_OF[bc % 3]]

def machine():
    start, code = load_code()
    m = z80.Z80Machine()
    m.set_memory_block(start, code)
    m.set_memory_block(TRAP, bytes([0xC3, 0xF0, 0x5E]))
    return m

def call(m, *labels):
    prog = b"".join(bytes([0xCD]) + SYM[l].to_bytes(2, "little") for l in labels) + bytes([0xC3, 0xF0, 0x5E])
    m.set_memory_block(0x5EC0, prog)
    m.pc = 0x5EC0; m.sp = 65008
    return run_until(m, TRAP)

def set_player(m, px, py, ang):
    ix, fx = int(px), int((px - int(px)) * 256); iy, fy = int(py), int((py - int(py)) * 256)
    m.set_memory_block(SYM["posx"], bytes([fx, ix])); m.set_memory_block(SYM["posy"], bytes([fy, iy]))
    m.set_memory_block(SYM["angle"], bytes([ang & 255]))

def clear_things(m):
    m.set_memory_block(SYM["things"], bytes(16 * 8))

def set_thing(m, i, typ, x, y):
    ix, fx = int(x), int((x - int(x)) * 256); iy, fy = int(y), int((y - int(y)) * 256)
    m.set_memory_block(SYM["things"] + 8 * i, bytes([typ, fx, ix, fy, iy, 0, 30, 0]))

def buf(m):
    return bytes(m.memory[BUF0:BUF0 + BUFCOLS * BUFSTR])

def changed_columns(a, b):
    """-> set of ray columns (0..63) and set of (col,row) where BUF differs."""
    cols, pix = set(), []
    for bc in range(BUFCOLS):
        for r in range(96):
            d = a[bc * BUFSTR + r] ^ b[bc * BUFSTR + r]
            if d:
                for bit in range(8):
                    if d & (0x80 >> bit):
                        c = 8 * (bc // 3) + PXRAY[(bc % 3) * 8 + bit]
                        cols.add(c); pix.append((c, r))
    return cols, pix

def main():
    fails = 0
    m = machine()
    call(m, "init_game", "render")
    zb = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
    print("zbuf start view:", list(zb[:8]), "...", list(zb[28:36]), "... nonzero", sum(1 for v in zb if v))
    if sum(1 for v in zb if v) != 64:
        print("FAIL: zbuf has empty columns at the start view (all rays hit walls there)"); fails += 1
    # walls-only reference at a viewpoint looking east down the corridor (y = 7.5, x = 3.5 -> wall at x = 7 is 3.5 cells away)
    for name, dist in (("near", 0.6), ("mid", 1.5), ("far", 3.0)):
        set_player(m, 3.5, 7.5, 0); clear_things(m)
        call(m, "render")
        ref = buf(m); zb = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
        set_thing(m, 0, 21, 3.5 + dist, 7.5)              # barrel straight ahead
        t_walls = call(m, "render")
        t_dt = call(m, "draw_things")                      # measured alone (buffer already has walls + sprite: idempotent OR/AND)
        call(m, "render")
        out = buf(m)
        cols, pix = changed_columns(ref, out)
        vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6]); nvis = m.memory[SYM["nvis"]]
        hv, c0, nc = vis[0], vis[1] - 256 if vis[1] > 127 else vis[1], vis[2]
        span = set(range(max(c0, 0), min(c0 + nc, 64)))      # M2.5: masked blit, only the sprite's own ray columns change
        bad_span = cols - span
        bad_depth = {c for c in cols if zb[c] >= hv}
        print("%s d=%.1f: nvis %d hv %d c0 %d nc %d | changed cols %s | pixels %d | draw_things T %d (%.0f%% of start frame)"
              % (name, dist, nvis, hv, c0, nc, (min(cols), max(cols)) if cols else None, len(pix), t_dt, 100.0 * t_dt / 292797))
        if nvis != 1 or not cols: print("FAIL: sprite not visible"); fails += 1
        if bad_span: print("FAIL: pixels outside the column span", sorted(bad_span)); fails += 1
        if bad_depth: print("FAIL: pixels in columns where the wall is nearer", sorted(bad_depth)); fails += 1
    # occlusion: barrel behind the wall at x = 7 (x = 8.5) must draw nothing
    set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m)
    set_thing(m, 0, 21, 8.5, 7.5); call(m, "render"); cols, pix = changed_columns(ref, buf(m))
    print("occluded barrel behind wall: changed pixels", len(pix), "(must be 0)")
    if pix: fails += 1
    # 2 sprites visible frame cost
    clear_things(m); set_thing(m, 0, 21, 5.0, 7.5); set_thing(m, 1, 16, 5.5, 8.3)
    t2 = call(m, "render"); print("frame with 2 sprites T %d -> %.1f fps" % (t2, 3_500_000 / t2))
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
