#!/usr/bin/env python3
"""test_ceiling.py - M2.5 step B textured ceiling (CLRBUF alternate-set pushes + fl_set mirror), Python Z80 core, no emulator.
 (a) open ceiling words (byte columns whose rays' walls stay below window row r) are the M2.5E lattice word (even w: 0x01 even
     row, 0x00 odd row; odd w: 0x0000 -> aligned dots every 8 px every 4 rows) or the line word (0xFF even row, 0x00 odd row);
     for every phase 0..15 the ceiling line rows are the exact mirror of the
     floor line rows: floor word w (rows 48+2w, 49+2w, line on the odd row 49+2w) <-> ceiling rows 47-2w, 46-2w, line on 46-2w.
 (b) walls still cover the dots: in every ray column the band's own slot bits above the horizon are exactly the texel
     (no dot bleeds through a wall: rows topr..47 of a solid far wall are all ones / lit-side texture equals the texture page).
 (c) DETAIL LOW (opt_detail 0, apply_opts): ceiling words 0x0000, lines 0x00FF; back to DETAIL HIGH restores the lattice.
 (d) fl_k+1 = 0 switches the ceiling lines off too (pure dots).
 (e) cost: fl_set <= 7,000 T (M2.6); render at the start view <= 345,000 T (>= 10.1 fps).
 (f) COSTAB/PLXTAB/MOVXTAB aliases: COSTAB[a] == SINTAB[(a+64) & 255] for all a (and the same for PLX/PLY, MOVX/MOVY).
exit 1 on any failure."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, buf, SYM, BUFCOLS, BUFSTR, rays_of, bytecol_of, SLOTM
from m23_floor_model import lines as oracle_lines
fails = 0
def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg); fails += not ok
DOTS = ((0x41, 0x80), (0x14, 0x22), (0x14, 0x08), (0x41, 0x22))   # M2.6 D5: DOTS[w & 3] = (even row 46-2w, odd row 47-2w): 45-degree X lattice, 8x8 diamonds
LINE = (0xFF, 0x00)          # line word HL' = 0x00FF: even row solid, odd row black
def ceil_words(m, bc):
    b = buf(m); base = bc * BUFSTR
    return [(b[base + 46 - 2 * w], b[base + 47 - 2 * w]) for w in range(24)]        # word w covers rows 46-2w / 47-2w
def floor_lines(m, bc):
    b = buf(m); base = bc * BUFSTR
    return [w for w in range(24) if (b[base + 48 + 2 * w], b[base + 49 + 2 * w]) == (0x00, 0xFF)]
def top_word(m, bc):
    """first ceiling word (nearest the horizon) that is above every wall of this byte column: wall rows above the horizon =
    h/2 -> rows 48-h/2..47 are wall; word w is clean when 46-2w < 48 - h/2 - 1 ..."""
    h = max(m.memory[SYM["zbuf"] + c] for c in rays_of(bc))
    return (min(h, 96) + 3) // 4
def open_col(m):
    best = None
    for bc in range(BUFCOLS):
        w0 = top_word(m, bc)
        pure = sum(1 for w, (lo, hi) in enumerate(ceil_words(m, bc)[w0:], w0) if (lo, hi) in (DOTS[w & 3], LINE)) + w0
        if best is None or pure > best[0]: best = (pure, bc, w0)
    return best

m = machine()
call(m, "init_game", "hud_init")
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
clear_things(m)
set_player(m, 3.5, 7.5, 0)
# (a) mirror for all phases
bad = 0
for p in range(16):
    m.set_memory_block(SYM["fl_ph"], bytes([p * 16]))
    call(m, "render")
    pure, bc, w0 = open_col(m)
    cw = ceil_words(m, bc)
    got = [w for w in range(w0, 24) if cw[w] == LINE]
    want = [w for w in oracle_lines(p, 4) if w >= w0]
    fl = [w for w in floor_lines(m, bc) if w >= w0]
    others = all(cw[w] == DOTS[w & 3] for w in range(w0, 24) if w not in want)
    if got != want or got != fl or not others:
        bad += 1; print("  phase %2d col %d: ceiling %s floor %s oracle %s others_dots %s (pure %d, w0 %d)" % (p, bc, got, fl, want, others, pure, w0))
check(bad == 0, "(a) ceiling line words == mirror of the floor lines == oracle for all 16 phases, dots elsewhere (col %d, w0 %d, pure %d/24)" % (bc, w0, pure))
# (b) walls cover the dots: render the same view with a black ceiling (DETAIL LOW) and with dots (DETAIL HIGH); inside every
#     ray column's own slot bits, the wall rows above the horizon (48 - h/2 .. 47) must be identical -> the band's (byte and C)
#     or B erases the dots under the wall, lit or dark side, solid or textured.
m.set_memory_block(SYM["fl_ph"], bytes([0]))
m.set_memory_block(SYM["opt_detail"], bytes([0])); call(m, "apply_opts", "render"); b_lo = buf(m)
m.set_memory_block(SYM["opt_detail"], bytes([1])); call(m, "apply_opts", "render"); b_hi = buf(m)
zb = [m.memory[SYM["zbuf"] + c] for c in range(64)]
leak = 0; checked = 0
for c in range(64):
    h = min(zb[c], 96)
    if h < 2: continue
    bc, mask, top = bytecol_of(c), SLOTM[c & 7], 48 - h // 2
    for r in range(top, 48):
        checked += 1
        if (b_lo[bc * BUFSTR + r] ^ b_hi[bc * BUFSTR + r]) & mask: leak += 1
check(leak == 0 and checked > 0, "(b) wall slot bits above the horizon identical with black vs dotted ceiling: %d slot-rows checked, %d leaks" % (checked, leak))
# (c) DETAIL LOW / HIGH
pure, bc, w0 = open_col(m)
m.set_memory_block(SYM["opt_detail"], bytes([0])); call(m, "apply_opts", "render")
cw = ceil_words(m, bc); want = [w for w in oracle_lines(0, 4) if w >= w0]
check(all(cw[w] == ((0xFF, 0x00) if w in want else (0, 0)) for w in range(w0, 24)), "(c) DETAIL LOW: ceiling 0x0000, lines (FF,00) (col %d words %d..23)" % (bc, w0))
m.set_memory_block(SYM["opt_detail"], bytes([1])); call(m, "apply_opts", "render")
cw = ceil_words(m, bc)
check(all(cw[w] == (LINE if w in want else DOTS[w & 3]) for w in range(w0, 24)), "(c) DETAIL HIGH again: D5 lattice words by w&3, lines 0x00FF")
# (d) lines off
m.set_memory_block(SYM["fl_k"] + 1, bytes([0])); call(m, "render")
cw = ceil_words(m, bc)
check(all(cw[w] == DOTS[w & 3] for w in range(w0, 24)), "(d) fl_k+1 = 0: no ceiling lines, pure lattice")
m.set_memory_block(SYM["fl_k"] + 1, bytes([4 * 16]))
# (e) cost
t_fl = call(m, "fl_set"); t_r = call(m, "render")
check(t_fl <= 7000, "(e) fl_set %d T (<= 7,000; M2.6 D5 two-byte ceiling slots)" % t_fl)
check(t_r <= 345000, "(e) render start view %d T = %.1f fps (<= 345,000)" % (t_r, 3_500_000 / t_r))
# (f) table aliases
def word(addr): return m.memory[addr] | (m.memory[addr + 1] << 8)
ok = True
for x, y in (("COSTAB", "SINTAB"), ("PLXTAB", "PLYTAB"), ("MOVXTAB", "MOVYTAB")):
    ok &= SYM[x] == SYM[y] + 128
    ok &= all(word(SYM[x] + 2 * a) == word(SYM[y] + 2 * ((a + 64) & 255)) for a in range(256))
check(ok, "(f) COSTAB/PLXTAB/MOVXTAB = y table + 128 B, 256 entries each equal the +64 angle entry (1,152 B saved)")
print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
