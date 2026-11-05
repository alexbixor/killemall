#!/usr/bin/env python3
"""m25_edit_e1.py - M2.5 step E1 (user 1 Nov 11:3xZ: "make the ceiling and the floor less dense, i.e. a square/diamond pattern";
Themis r1 14:37Z: B2/B3 + byte-order facts folded in). Idempotent: every edit asserts its OLD text occurs exactly once, or that
the NEW text is already there; exit 1 otherwise. Edits:
  gen48.py      CLRBUF: two fill registers per set (floor DE = even words, BC = odd words; ceiling DE' / BC'); pushes alternate
                per word parity (floor pushes run word 23..0 -> first opcode C5, ceiling 0..23 -> first D5); line words become
                constants 0xFF00 (floor: odd row 49+2w solid) / 0x00FF (ceiling: even row 46-2w solid).
  floor.asm     fl_set writes D5 (even w) / C5 (odd w) / E5 (line); FL_D4 even-aligned so bit 0 of L == w & 1.
  kea48.asm     apply_opts loads the three variable fill words (DETAIL LOW -> 0), line words no longer patched.
  test48.py     NOTHINGS: poke both floor fill words to the 0x55AA checker (chk48's scan assumes it; Themis B3).
  test_floor_lines.py / test_ceiling.py / m25b_zes.py: oracles expect the per-parity pattern.
Pattern "D2": floor even words 0x0100 (dot x=7 on odd row), odd words 0x1000 (dot x=3): staggered 4 px every 2 rows = diamond
lattice, 2 lit of 32 px = 6.25%. Ceiling even words 0x0001 (dot x=7 on even row), odd words 0 = aligned squares 8x4, 3.125%.
Dots sit on the row a distance line replaces, so a line word = fill word with the dot row solid (pattern stays continuous)."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
changed = []
def edit(rel, pairs):
    p = ROOT / rel; s = p.read_text(); n0 = s
    for old, new in pairs:
        if new in s: continue                                        # already applied (old may be a prefix of new)
        c = s.count(old)
        if c == 0 and "M2.5E" in s: continue                         # superseded by a later edit of the same region (chain)
        if c != 1: print("FAIL %s: expected 1 occurrence, found %d of %r" % (rel, c, old[:70])); sys.exit(1)
        s = s.replace(old, new)
    if s != n0: p.write_text(s); changed.append(rel)

# ---- gen48.py: docstring + CLRBUF emitter
edit("tools/gen48.py", [
("""  CLRBUF   PUSH-fills the buffer: rows 48-95 the floor checker (0xAA even rows / 0x55 odd rows) + distance lines, rows 0-47
           (M2.5B) the ceiling: sparse dots (0x44 even rows / 0x11 odd rows) + the mirrored distance lines (alternate set).""",
"""  CLRBUF   PUSH-fills the buffer: rows 48-95 the floor dot lattice + distance lines, rows 0-47 the ceiling lattice + the
           mirrored distance lines (alternate set). M2.5E: two fill words per set, alternating per word parity (even word w:
           DE / DE', odd: BC / BC'); floor 0x0100 / 0x1000 (dot on the odd row 49+2w, staggered 4 px = diamonds, 6.25%),
           ceiling 0x0001 / 0x0000 (dot on the even row 46-2w, aligned squares, 3.125%); line words 0xFF00 / 0x00FF."""),
("""    # ---- CLRBUF: PUSH fill, SP walks down from BUF+2048; per column 16 pushes 0 (rows 127..96), 24 pushes floor, 24 pushes 0
    # M2.5B: ceiling words live in the alternate set: DE' = dots 0x1144 (D odd row 0x11, E even row 0x44), HL' = line word
    #        0x11FF (even row 46-2w solid = mirror of the floor line row 49+2w). apply_opts patches cl_ce+1 / cl_cw+1.
    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2304", "        exx",            # M2.5C: 24 x 96 B
          "cl_ce:  ld de,%d" % (0x11 * 256 + 0x44), "cl_cw:  ld hl,%d" % (0x11 * 256 + 0xFF), "        exx",
          "cl_de:  ld de,%d" % (0x55 * 256 + 0xAA),
          "        ld a,24", "cl_col: ld hl,65450"]              # M2.3: HL = 0xFFAA floor line word; M2.5C: 24 columns, no row gap
    s += ["cl_fl:  push de"] + ["        push de"] * 23                              # M2.3: fl_set patches cl_fl..+23 (D5/E5)
    s += ["        exx", "cl_cl:  push de"] + ["        push de"] * 23 + ["        exx"]   # M2.5B: ceiling word 0 (rows 47/46) .. 23 (rows 1/0); fl_set mirrors cl_cl..+23
""",
"""    # ---- CLRBUF: PUSH fill, SP walks down from BUF+2304 (24 columns x 96 rows, column 23 first); per column 24 pushes floor
    #      (word 23 = rows 95/94 first ... word 0 = rows 49/48 last; low byte -> even row), then 24 pushes ceiling in the
    #      alternate set (word 0 = rows 46/47 first ... word 23 = rows 0/1).
    # M2.5E: two fill words per set, chosen per word parity: even words push de / de', odd words push bc / bc' (fl_set writes
    #        D5 / C5, or E5 = push hl / hl' for a distance line). Floor DE 0x0100 (dot x=7 on the odd row 49+2w), BC 0x1000
    #        (dot x=3): diamonds. Ceiling DE' 0x0001 (dot x=7 on the even row 46-2w), BC' 0: aligned squares at half density.
    #        Line words are constants: floor HL 0xFF00 (odd row solid), ceiling HL' 0x00FF (even row solid) = the fill word
    #        with its dot row replaced, so the lattice stays continuous. apply_opts patches cl_de+1 / cl_bc+1 / cl_ce+1.
    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2304", "        exx",            # M2.5C: 24 x 96 B
          "cl_ce:  ld de,%d" % 0x0001, "cl_cb:  ld bc,%d" % 0x0000, "cl_cw:  ld hl,%d" % 0x00FF, "        exx",
          "cl_de:  ld de,%d" % 0x0100, "cl_bc:  ld bc,%d" % 0x1000,
          "        ld a,24", "cl_col: ld hl,%d" % 0xFF00]        # HL = floor line word; M2.5C: 24 columns, no row gap
    s += ["cl_fl:  push bc"] + ["        push %s" % ("de" if i & 1 else "bc") for i in range(1, 24)]   # push i = word 23-i: odd word -> bc
    s += ["        exx", "cl_cl:  push de"] + ["        push %s" % ("bc" if i & 1 else "de") for i in range(1, 24)] + ["        exx"]   # push i = word i
"""),
])

# ---- floor.asm: header, fl_set parity opcode, FL_D4 alignment
edit("src/common/floor.asm", [
("""; floor.asm - M2.3 floor distance lines. CLRBUF (gen/unrolled48.asm) fills the 24 floor words of every byte column with
; PUSHes; fl_set patches those 24 push opcodes once per frame: D5 = push de (checker word 0x55AA, or 0 on DETAIL LOW),
; E5 = push hl (line word 0xFFAA: odd row solid, even row = checker -> a 1-px line). Word w covers window rows 48+2w (L/E)
; and 49+2w (H/D); its top edge is at perpendicular""",
"""; floor.asm - M2.3 floor distance lines. CLRBUF (gen/unrolled48.asm) fills the 24 floor words of every byte column with
; PUSHes; fl_set patches those 24 push opcodes once per frame: D5 = push de (fill word of the even words), C5 = push bc (fill
; word of the odd words; M2.5E dot lattice, both 0 on DETAIL LOW), E5 = push hl (line word 0xFF00: odd row solid -> a 1-px
; line). Word w covers window rows 48+2w (L/E) and 49+2w (H/D); its top edge is at perpendicular"""),
("""        push af
        xor b
        and 0xF8
        ld a,0xD5              ; push de = checker
        jr z,fl_w              ; both edges in the same half-cell interval: no grid line crosses this word
        ld a,b
fl_k:   cp FL_KMAX*16          ; tests poke fl_k+1 = 0 to switch the lines off (walls-only geometry check)
        ld a,0xD5
        jr nc,fl_w             ; k >= FL_KMAX: too far, keep the checker
        ld a,0xE5              ; push hl = line word
fl_w:   ld (de),a
        ld (ix+0),a            ; M2.5B: same opcode for the mirrored ceiling word (DE'/HL' in CLRBUF: dots / line)""",
"""        push af
        xor b
        and 0xF8
        jr z,fl_f              ; both edges in the same half-cell interval: no grid line crosses this word -> fill
        ld a,b
fl_k:   cp FL_KMAX*16          ; tests poke fl_k+1 = 0 to switch the lines off (walls-only geometry check)
        jr nc,fl_f             ; k >= FL_KMAX: too far, keep the fill
        ld a,0xE5              ; push hl = line word
        jr fl_w
fl_f:   ld a,0xD5              ; push de = fill word of the even words (M2.5E; FL_D4 is even-aligned, so bit 0 of L == w & 1)
        bit 0,l
        jr z,fl_w
        ld a,0xC5              ; push bc = fill word of the odd words
fl_w:   ld (de),a
        ld (ix+0),a            ; M2.5B: same opcode for the mirrored ceiling word (DE'/BC'/HL' in CLRBUF: fill / line)"""),
("""fl_ph:  defb 0                 ; forward distance walked, 1/256 cell, wraps
FL_D4:  defb 240""",
"""fl_ph:  defb 0                 ; forward distance walked, 1/256 cell, wraps
        if ($ and 1)
        defs 1                 ; M2.5E: FL_D4 even-aligned (fl_set reads the word parity from bit 0 of L)
        endif
FL_D4:  defb 240"""),
])

# ---- kea48.asm: apply_opts
edit("src/48k/kea48.asm", [
("""apply_opts:                    ; opt_detail 0 -> plain floor + ceiling (CLRBUF fills 0x0000, lines stay), 1 -> floor checker 0x55AA + ceiling dots 0x1144
        ld hl,0x55AA
        ld de,0x1144           ; M2.5B: ceiling dots word (DE' in CLRBUF)
        ld bc,0x11FF           ; M2.5B: ceiling line word (HL' in CLRBUF): even row solid line, odd row dots
        ld a,(opt_detail)
        or a
        jr nz,ao1
        ld h,a
        ld l,a
        ld d,a
        ld e,a
        ld b,a                 ; DETAIL LOW: ceiling line word 0x00FF (plain black around the line)
ao1:    ld (cl_de+1),hl
        ld (cl_ce+1),de
        ld (cl_cw+1),bc
        ret""",
"""apply_opts:                    ; opt_detail 0 -> plain black floor + ceiling (CLRBUF fills 0x0000, lines stay), 1 -> M2.5E dot lattice
        ld hl,0x0100           ; floor even words (DE in CLRBUF): dot x=7 on the odd row 49+2w
        ld de,0x1000           ; floor odd words (BC): dot x=3 -> staggered 4 px every 2 rows = diamonds (6.25%)
        ld bc,0x0001           ; ceiling even words (DE'): dot x=7 on the even row 46-2w; odd words (BC') stay 0 = squares 8x4 (3.125%)
        ld a,(opt_detail)
        or a
        jr nz,ao1
        ld h,a
        ld l,a
        ld d,a
        ld e,a
        ld b,a
        ld c,a                 ; DETAIL LOW: all fill words 0 (line words 0xFF00 / 0x00FF are constants now)
ao1:    ld (cl_de+1),hl
        ld (cl_bc+1),de
        ld (cl_ce+1),bc
        ret"""),
])

# ---- test48.py: walls-only geometry run needs the uniform checker chk48 scans for
edit("tools/test48.py", [
("""    if os.environ.get("NOTHINGS") and "fl_k" in SYM:
        m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))                       # M2.3: floor lines off (chk48 scans the checker)
""",
"""    if os.environ.get("NOTHINGS") and "fl_k" in SYM:
        m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))                       # M2.3: floor lines off (chk48 scans the checker)
        m.set_memory_block(SYM["cl_de"] + 1, bytes([0xAA, 0x55]))             # M2.5E: both floor fill words = the 0x55AA checker
        m.set_memory_block(SYM["cl_bc"] + 1, bytes([0xAA, 0x55]))             #        (the game's dot lattice is mostly 0x00 = a dark texel)
"""),
])

# ---- test_floor_lines.py
edit("tools/test_floor_lines.py", [
(""" (a) for every phase 0..15 the set of BUF floor words that are (0xAA, 0xFF) (1-px line) in an open byte column equals the oracle
     tools/m23_floor_model.py (same D4 table, FL_KMAX = 4); all other floor words are the 0x55AA checker""",
""" (a) for every phase 0..15 the set of BUF floor words that are (0x00, 0xFF) (1-px line) in an open byte column equals the oracle
     tools/m23_floor_model.py (same D4 table, FL_KMAX = 4); all other floor words are the M2.5E lattice: even w (0x00, 0x01),
     odd w (0x00, 0x10) = one dot per 8 px on the odd row, staggered 4 px every 2 rows"""),
(""" (d) DETAIL LOW (opt_detail 0, apply_opts): checker words are 0x0000, lines still 0xFFFF""",
""" (d) DETAIL LOW (opt_detail 0, apply_opts): fill words are 0x0000, lines still (0x00, 0xFF)"""),
("""CHK = (0xAA, 0x55)            # push de, DE = 0x55AA: E lands on the even (lower) row, D on the odd row
LINE = (0xAA, 0xFF)           # push hl, HL = 0xFFAA: even row keeps the checker, odd row solid""",
"""FILL = ((0x00, 0x01), (0x00, 0x10))   # M2.5E: FILL[w & 1]; push de (even w, DE = 0x0100) / push bc (odd w, BC = 0x1000): the low byte lands on the even row 48+2w
LINE = (0x00, 0xFF)           # push hl, HL = 0xFF00: odd row 49+2w solid, even row black (= the fill's even row)"""),
("""    for bc in range(BUFCOLS):
        ws = floor_words(m, bc)[w0(m, bc):]
        pure = sum(1 for lo, hi in ws if (lo, hi) in (CHK, LINE, (0, 0))) + w0(m, bc)""",
"""    for bc in range(BUFCOLS):
        a = w0(m, bc); ws = floor_words(m, bc)[a:]
        pure = sum(1 for w, (lo, hi) in enumerate(ws, a) if (lo, hi) in (FILL[w & 1], LINE, (0, 0))) + a"""),
("""    others_ok = all((lo, hi) == CHK for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None""",
"""    others_ok = all((lo, hi) == FILL[w & 1] for w, (lo, hi) in flo(floor_words(m, bc), m, bc) if w not in want) if pure == 24 else None"""),
("""check(bad == 0, "(a) line words == oracle for all 16 phases, checker elsewhere (col %d, wall words %d, pure %d/24)" % (bc, w0(m, bc), pure))""",
"""check(bad == 0, "(a) line words == oracle for all 16 phases, dot lattice elsewhere (col %d, wall words %d, pure %d/24)" % (bc, w0(m, bc), pure))"""),
("""check(all((lo, hi) == (LINE if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still (AA,FF)")""",
"""check(all((lo, hi) == (LINE if w in want else (0, 0)) for w, (lo, hi) in ws), "(d) DETAIL LOW: plain 0x0000 floor, lines still (00,FF)")"""),
("""check(line_words(m, bc) == [] and all((lo, hi) == CHK for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure checker")""",
"""check(line_words(m, bc) == [] and all((lo, hi) == FILL[w & 1] for w, (lo, hi) in flo(floor_words(m, bc), m, bc)), "(f) fl_k+1 = 0: no lines, pure lattice")"""),
])

# ---- test_ceiling.py
edit("tools/test_ceiling.py", [
(""" (a) open ceiling words (byte columns whose rays' walls stay below window row r) are the dots word (0x44 even row, 0x11 odd row)
     or the line word (0xFF even row, 0x11 odd row); for every phase 0..15 the ceiling line rows are the exact mirror of the""",
""" (a) open ceiling words (byte columns whose rays' walls stay below window row r) are the M2.5E lattice word (even w: 0x01 even
     row, 0x00 odd row; odd w: 0x0000 -> aligned dots every 8 px every 4 rows) or the line word (0xFF even row, 0x00 odd row);
     for every phase 0..15 the ceiling line rows are the exact mirror of the"""),
(""" (c) DETAIL LOW (opt_detail 0, apply_opts): ceiling words 0x0000, lines 0x00FF; back to DETAIL HIGH restores 0x1144 / 0x11FF.""",
""" (c) DETAIL LOW (opt_detail 0, apply_opts): ceiling words 0x0000, lines 0x00FF; back to DETAIL HIGH restores the lattice."""),
("""DOTS = (0x44, 0x11)          # (even row, odd row) of a ceiling word: rows 46-2w (E'), 47-2w (D')
LINE = (0xFF, 0x11)          # line word: even row solid, odd row dots""",
"""DOTS = ((0x01, 0x00), (0x00, 0x00))   # M2.5E: DOTS[w & 1], (even row 46-2w = E'/C', odd row 47-2w = D'/B'): even words carry the dot
LINE = (0xFF, 0x00)          # line word HL' = 0x00FF: even row solid, odd row black"""),
("""    return [w for w in range(24) if (b[base + 48 + 2 * w], b[base + 49 + 2 * w]) == (0xAA, 0xFF)]""",
"""    return [w for w in range(24) if (b[base + 48 + 2 * w], b[base + 49 + 2 * w]) == (0x00, 0xFF)]"""),
("""        pure = sum(1 for lo, hi in ceil_words(m, bc)[w0:] if (lo, hi) in (DOTS, LINE)) + w0""",
"""        pure = sum(1 for w, (lo, hi) in enumerate(ceil_words(m, bc)[w0:], w0) if (lo, hi) in (DOTS[w & 1], LINE)) + w0"""),
("""    others = all(cw[w] == DOTS for w in range(w0, 24) if w not in want)""",
"""    others = all(cw[w] == DOTS[w & 1] for w in range(w0, 24) if w not in want)"""),
("""check(all(cw[w] == (LINE if w in want else DOTS) for w in range(w0, 24)), "(c) DETAIL HIGH again: dots 0x1144, lines 0x11FF")""",
"""check(all(cw[w] == (LINE if w in want else DOTS[w & 1]) for w in range(w0, 24)), "(c) DETAIL HIGH again: lattice 0x0001/0x0000, lines 0x00FF")"""),
("""check(all(cw[w] == DOTS for w in range(w0, 24)), "(d) fl_k+1 = 0: no ceiling lines, pure dots")""",
"""check(all(cw[w] == DOTS[w & 1] for w in range(w0, 24)), "(d) fl_k+1 = 0: no ceiling lines, pure lattice")"""),
])

# ---- m25b_zes.py (ZEsarUX live screen): the open ceiling rows follow the lattice exactly
edit("tools/m25b_zes.py", [
("""    dots = sum(1 for r in range(0, top) if col[r] in (0x44, 0x11))
    if best is None or dots > best[0]: best = (dots, bc, top, bot, col)
dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
print("screen byte col %d (wall rows %d..%d): ceiling dot rows %d/%d, ceiling line rows %s, floor line rows %s" % (4 + bc, top, bot - 1, dots, top, lines_c, lines_f))
check(dots >= top - 2 * len(lines_c) - 4, "live screen col %d: the open ceiling rows are dots or lines (%d dots + %d lines of %d rows)" % (4 + bc, dots, len(lines_c), top))""",
"""    dots = sum(1 for r in range(0, top) if col[r] == (0x01 if r % 4 == 2 else 0x00))     # M2.5E lattice: dot rows 46-4k (x=7), else black
    if best is None or dots > best[0]: best = (dots, bc, top, bot, col)
dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
wrong = [r for r in range(0, top) if col[r] != (0xFF if r in lines_c else (0x01 if r % 4 == 2 else 0x00))]
print("screen byte col %d (wall rows %d..%d): ceiling lattice rows %d/%d, ceiling line rows %s, floor line rows %s, off-pattern rows %s" % (4 + bc, top, bot - 1, dots, top, lines_c, lines_f, wrong))
check(top >= 8 and len(wrong) <= 2, "live screen col %d: the open ceiling rows are the lattice or lines (%d lattice + %d lines of %d rows, %d off)" % (4 + bc, dots, len(lines_c), top, len(wrong)))"""),
])

# ---- m25b_zes.py, second pass (15:4xZ): the live game has walking zombies; the first run picked a column whose floor rows 55..75
#      carried a zombie's hand (white run 64..67 + black halo in one ray slot) and the floor/ceiling mirror check failed on it.
#      Score columns by ceiling AND floor lattice rows so a sprite-covered column loses; check the floor rows too.
edit("tools/m25b_zes.py", [
("""check(lc == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s (open part)" % (lc, mirror))""",
"""if lc != mirror: print("  column dump rows 0..95:", " ".join("%02X" % v for v in col))
check(lc == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s (open part)" % (lc, mirror))"""),
("""for bc in range(24):
    h = min(max(zb[8 * (bc // 3) + r] for r in RAYS_OF[bc % 3]), 96); top, bot = 48 - h // 2, 48 + h // 2
    col = scr_col(4 + bc)
    dots = sum(1 for r in range(0, top) if col[r] == (0x01 if r % 4 == 2 else 0x00))     # M2.5E lattice: dot rows 46-4k (x=7), else black
    if best is None or dots > best[0]: best = (dots, bc, top, bot, col)
dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
wrong = [r for r in range(0, top) if col[r] != (0xFF if r in lines_c else (0x01 if r % 4 == 2 else 0x00))]
print("screen byte col %d (wall rows %d..%d): ceiling lattice rows %d/%d, ceiling line rows %s, floor line rows %s, off-pattern rows %s" % (4 + bc, top, bot - 1, dots, top, lines_c, lines_f, wrong))
check(top >= 8 and len(wrong) <= 2, "live screen col %d: the open ceiling rows are the lattice or lines (%d lattice + %d lines of %d rows, %d off)" % (4 + bc, dots, len(lines_c), top, len(wrong)))""",
"""def lat_c(r): return 0x01 if r % 4 == 2 else 0x00                                         # M2.5E ceiling lattice: dot rows 46-4k (x=7)
def lat_f(r): return ((0x01 if ((r - 49) // 2) % 2 == 0 else 0x10) if r % 2 else 0x00)    # floor: odd row 49+2w, x=7 (even w) / x=3 (odd w)
for bc in range(24):
    h = min(max(zb[8 * (bc // 3) + r] for r in RAYS_OF[bc % 3]), 96); top, bot = 48 - h // 2, 48 + h // 2
    col = scr_col(4 + bc)
    dots = sum(1 for r in range(0, top) if col[r] == lat_c(r))
    fdots = sum(1 for r in range(bot, 96) if col[r] == lat_f(r))                            # live zombies: a sprite-covered column loses
    if best is None or dots + fdots > best[0]: best = (dots + fdots, dots, bc, top, bot, col)
_, dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
wrong = [r for r in range(0, top) if col[r] != (0xFF if r in lines_c else lat_c(r))]
wrong_f = [r for r in range(bot, 96) if col[r] != (0xFF if r in lines_f else lat_f(r))]
print("screen byte col %d (wall rows %d..%d): ceiling lattice rows %d/%d, ceiling line rows %s, floor line rows %s, off-pattern rows ceiling %s floor %s" % (4 + bc, top, bot - 1, dots, top, lines_c, lines_f, wrong, wrong_f))
check(top >= 8 and len(wrong) <= 2, "live screen col %d: the open ceiling rows are the lattice or lines (%d lattice + %d lines of %d rows, %d off)" % (4 + bc, dots, len(lines_c), top, len(wrong)))
check(len(wrong_f) <= 2, "live screen col %d: the open floor rows are the lattice (0x01/0x10 on odd rows, diamonds) or lines (%d off)" % (4 + bc, len(wrong_f)))"""),
])
print("m25_edit_e1: changed %s" % (changed or "nothing (already applied)"))
