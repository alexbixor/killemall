import pathlib
p = pathlib.Path('/home/ubuntu/work/killemall/tools/m25b_zes.py'); s = p.read_text()
old = '''col = scr_col(8)
dots = sum(1 for r in range(0, 48) if col[r] in (0x44, 0x11))
lines_c = [r for r in range(0, 48) if col[r] == 0xFF]
lines_f = [r for r in range(48, 96) if col[r] == 0xFF]
print("screen col 8: ceiling dot rows %d/48, ceiling line rows %s, floor line rows %s" % (dots, lines_c, lines_f))
check(dots >= 30, "live screen col 8: >= 30 of 48 ceiling rows are the dot words (got %d)" % dots)
mirror = sorted(46 - 2 * ((r - 49) // 2) for r in lines_f if r % 2 == 1)   # floor line odd row 49+2w <-> ceiling even row 46-2w
check(sorted(lines_c) == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s" % (lines_c, lines_f))
'''
new = '''# wall span per byte column from the live zbuf (static view -> stable): rows 48-h/2 .. 47+h/2 are wall, the rest is open
zb = z.rd(SYM["zbuf"], 64)
best = None
for bc in range(16):
    h = min(max(zb[4 * bc:4 * bc + 4]), 96); top, bot = 48 - h // 2, 48 + h // 2
    col = scr_col(8 + bc)
    dots = sum(1 for r in range(0, top) if col[r] in (0x44, 0x11))
    if best is None or dots > best[0]: best = (dots, bc, top, bot, col)
dots, bc, top, bot, col = best
lines_c = [r for r in range(0, top) if col[r] == 0xFF]
lines_f = [r for r in range(bot, 96) if col[r] == 0xFF]
print("screen byte col %d (wall rows %d..%d): ceiling dot rows %d/%d, ceiling line rows %s, floor line rows %s" % (8 + bc, top, bot - 1, dots, top, lines_c, lines_f))
check(dots >= top - 2 * len(lines_c) - 4, "live screen col %d: the open ceiling rows are dots or lines (%d dots + %d lines of %d rows)" % (8 + bc, dots, len(lines_c), top))
mirror = sorted(46 - 2 * ((r - 49) // 2) for r in lines_f if r % 2 == 1 and 46 - 2 * ((r - 49) // 2) < top)   # floor odd row 49+2w <-> ceiling even row 46-2w
lc = sorted(r for r in lines_c if 49 + (46 - r) >= bot)
check(lc == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s (open part)" % (lc, mirror))
'''
assert s.count(old) == 1
p.write_text(s.replace(old, new)); print("ok")
