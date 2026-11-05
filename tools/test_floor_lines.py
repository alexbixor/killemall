#!/usr/bin/env python3
"""test_floor_lines.py - M2.3 floor distance lines (src/common/floor.asm), Python Z80 core, no emulator.
 (a) for every phase 0..15 the set of BUF floor words that are (0x00, 0xFF) (1-px line) in an open byte column equals the oracle
     tools/m23_floor_model.py (same D4 table, FL_KMAX = 4); all other floor words are the M2.5E lattice: even w (0x00, 0x01),
     odd w (0x00, 0x10) = one dot per 8 px on the odd row, staggered 4 px every 2 rows
 (b) walking forward (game_tick with bit 0) advances fl_ph by 38 per tick (0.15 cell, once per moving tick) and the nearest line
     moves DOWN the screen (toward the player); backward moves it up; turning (bits 2/3) leaves fl_ph and the lines alone
 (c) blocked axis: facing a wall, the phase does not advance (no movement -> no flow)
 (d) DETAIL LOW (opt_detail 0, apply_opts): fill words are 0x0000, lines still (0x00, 0xFF)
 (e) fl_set cost <= 7,000 T (M2.6); render at the start view <= 345,000 T (fps floor: 10.1 fps)
 (f) fl_k+1 = 0 switches every line off (walls-only geometry check hook used by test48 NOTHINGS)
exit 1 on any failure."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, buf, SYM, BUFCOLS, BUFSTR, rays_of
from test48 import run_until
from m23_floor_model import lines as oracle_lines, D4
fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += not ok
def fake_input(m, bits): m.set_memory_block(SYM["in_read"], bytes([0x3E, bits, 0xC9]))
FILL = ((0x00, 0x01), (0x00, 0x10))   # M2.5E: FILL[w & 1]; push de (even w, DE = 0x0100) / push bc (odd w, BC = 0x1000): the low byte lands on the even row 48+2w
LINE = (0x00, 0xFF)           # push hl, HL = 0xFF00: odd row 49+2w solid, even row black (= the fill's even row)
def floor_words(m, bytecol):
    b = buf(m); base = bytecol * BUFSTR
    return [(b[base + 48 + 2 * w], b[base + 49 + 2 * w]) for w in range(24)]       # (even row, odd row) = (L/E, H/D)
def w0(m, bytecol):
    """first floor word below the wall of this byte column: wall rows below the horizon = h/2 (h = max zbuf of its 4 rays)"""
    h = max(m.memory[SYM["zbuf"] + c] for c in rays_of(bytecol))
    return (min(h, 96) + 3) // 4
def matched_deltas(l0, l1, sign=1):
    """word delta of every line in l1 matched to its nearest line in l0 (ties resolved in the expected flow direction;
    new entrants > 3 words away are dropped)"""
    out = []
    for w in l1:
        d = min(((abs(w - a), -sign * (w - a), w - a) for a in l0), default=(99, 0, 0)); d = (d[0], d[2])
        if d[0] <= 3: out.append(d[1])
    return out
def line_words(m, bytecol):
    return [w for w, (lo, hi) in enumerate(floor_words(m, bytecol)) if (lo, hi) == LINE and w >= w0(m, bytecol)]
def flo(ws, m, bytecol):
    return [(w, lh) for w, lh in enumerate(ws) if w >= w0(m, bytecol)]
def open_floor_col(m):
    """byte column whose 24 floor words are all checker or line (no wall/sprite) at the start view: far wall ahead is
    small, the lower part of the window at the sides is floor; pick the column with the most pure words."""
    best = None
    for bc in range(BUFCOLS):
        a = w0(m, bc); ws = floor_words(m, bc)[a:]
        pure = sum(1 for w, (lo, hi) in enumerate(ws, a) if (lo, hi) in (FILL[w & 1], LINE, (0, 0))) + a
        if best is None or pure > best[0]: best = (pure, bc)
    return best
m = machine()
call(m, "init_game", "hud_init")
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))        # no pistol over the floor
clear_things(m)
set_player(m, 3.5, 7.5, 0)
# (a) phases
bad = 0
for p in range(16):
    m.set_memory_block(SYM["fl_ph"], bytes([p * 16]))
    call(m, "render")
    pure, bc = open_floor_col(m)
    got = line_words(m, bc); want = [w for w in oracle_lines(p, 4) if w >= w0(m, bc)]
    others_ok = all((lo, hi) == FILL[w & 1] for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None
    if got != want or others_ok is False:
        bad += 1; print("  phase %2d col %d: got %s want %s others_ok %s (pure %d)" % (p, bc, got, want, others_ok, pure))
check(bad == 0, "(a) line words == oracle for all 16 phases, dot lattice elsewhere (col %d, wall words %d, pure %d/24)" % (bc, w0(m, bc), pure))
# (b) flow direction + turning
m.set_memory_block(SYM["fl_ph"], bytes([0])); call(m, "render"); pure, bc = open_floor_col(m)
l0 = line_words(m, bc)
fake_input(m, 0x01); call(m, "game_tick")
ph1 = m.memory[SYM["fl_ph"]]; call(m, "render"); l1 = line_words(m, bc)
check(ph1 == 38, "(b) forward tick in open space: fl_ph 0 -> %d (38 = 0.15 cell, once per tick)" % ph1)
# from phase 8 (no wrap): the nearest line (lowest on screen = max word) must move to a larger word (down = toward the player)
set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM["fl_ph"], bytes([128])); call(m, "render"); l0 = line_words(m, bc)
call(m, "game_tick"); call(m, "render"); l = line_words(m, bc); dd = matched_deltas(l0, l)
check(dd and all(d >= 0 for d in dd) and any(d > 0 for d in dd), "(b) forward: lines move down the screen (word deltas %s, %s -> %s)" % (dd, l0, l))
set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM["fl_ph"], bytes([0])); call(m, "render"); l0 = line_words(m, bc)
fake_input(m, 0x02); call(m, "game_tick"); ph = m.memory[SYM["fl_ph"]]
check(ph == (256 - 38) & 255, "(b) backward tick: fl_ph 0 -> %d (-38)" % ph)
set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM["fl_ph"], bytes([128])); call(m, "render"); l0 = line_words(m, bc)
call(m, "game_tick"); call(m, "render"); l = line_words(m, bc); dd = matched_deltas(l0, l, -1)
check(dd and all(d <= 0 for d in dd) and any(d < 0 for d in dd), "(b) backward: lines move up the screen (word deltas %s, %s -> %s)" % (dd, l0, l))
set_player(m, 3.5, 7.5, 0); m.set_memory_block(SYM["fl_ph"], bytes([128])); call(m, "render"); l0 = line_words(m, bc); wa = w0(m, bc)
fake_input(m, 0x04); call(m, "game_tick"); fake_input(m, 0x08); call(m, "game_tick"); fake_input(m, 0x04); call(m, "game_tick")
call(m, "render")
lt = line_words(m, bc); wt = max(w0(m, bc), wa)
check(m.memory[SYM["fl_ph"]] == 128 and [w for w in lt if w >= wt] == [w for w in l0 if w >= wt], "(b) turning: fl_ph stays 128, floor lines unchanged (%s vs %s)" % (lt, l0))
# (c) blocked: face the west wall from x = 1.2 (cell 0 is wall) heading west (angle 128)
set_player(m, 1.1, 7.5, 128); m.set_memory_block(SYM["fl_ph"], bytes([0]))
fake_input(m, 0x01); call(m, "game_tick")
px = m.memory[SYM["posx"]] | (m.memory[SYM["posx"] + 1] << 8)
check(m.memory[SYM["fl_ph"]] == 0 and px == int(1.1 * 256) & 0xFFFF, "(c) walking into a wall: posx unchanged (0x%04X) and fl_ph stays 0" % px)
# (d) DETAIL LOW
set_player(m, 3.5, 7.5, 0); clear_things(m); m.set_memory_block(SYM["fl_ph"], bytes([0]))
m.set_memory_block(SYM["opt_detail"], bytes([0])); call(m, "apply_opts", "render")
ws = flo(floor_words(m, bc), m, bc); want = oracle_lines(0, 4)
check(all((lo, hi) == (LINE if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still (00,FF)")
m.set_memory_block(SYM["opt_detail"], bytes([1])); call(m, "apply_opts")
# (e) cost
t_fl = call(m, "fl_set"); t_r = call(m, "render")
check(t_fl <= 7000, "(e) fl_set %d T (<= 7,000; M2.6 D5 two-byte ceiling slots)" % t_fl)
check(t_r <= 345000, "(e) render start view %d T = %.1f fps (<= 345,000)" % (t_r, 3_500_000 / t_r))
# (f) off switch
m.set_memory_block(SYM["fl_k"] + 1, bytes([0])); call(m, "render")
check(line_words(m, bc) == [] and all((lo, hi) == FILL[w & 1] for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure lattice")
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)