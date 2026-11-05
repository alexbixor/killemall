import pathlib
p = pathlib.Path('/home/ubuntu/work/killemall/tools/m25b_zes.py'); s = p.read_text()
old = '''# ceiling words straight from the back buffer of the live machine: byte column 0 (left edge, open corridor side)
def ceil_rows(bc=0):
    b = z.rd(0x6000 + bc * 128, 96)
    return b
b = ceil_rows(0)
dots = sum(1 for r in range(0, 48) if b[r] in (0x44, 0x11))
lines_c = [r for r in range(0, 48) if b[r] == 0xFF]
lines_f = [r for r in range(48, 96) if b[r] == 0xFF]
print("col 0: ceiling dot rows %d/48, ceiling line rows %s, floor line rows %s" % (dots, lines_c, lines_f))
check(dots >= 30, "live back buffer col 0: >= 30 of 48 ceiling rows are the dot words (got %d)" % dots)
mirror = [47 - (r - 48) - 1 for r in lines_f]            # floor line on odd row 49+2w <-> ceiling line on even row 46-2w
check(sorted(lines_c) == sorted(mirror) or not lines_f, "ceiling line rows %s mirror the floor line rows %s" % (lines_c, lines_f))
'''
new = '''# the live frame straight from the SCREEN (the back buffer is being rewritten while we read it): the window's left byte
# column (screen x 64..71 = byte 8) rows 8..103; the left edge of the start view is open corridor (far wall small, no sprite).
# A screen column grab is one frame (COPYBUF copies a column in one burst) -> rows are consistent inside a column.
def scr_col(byte=8):
    scr = z.grab(); out = []
    for y in range(8, 104):
        out.append(scr[((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + byte])
    return out                           # index = window row 0..95
col = scr_col(8)
dots = sum(1 for r in range(0, 48) if col[r] in (0x44, 0x11))
lines_c = [r for r in range(0, 48) if col[r] == 0xFF]
lines_f = [r for r in range(48, 96) if col[r] == 0xFF]
print("screen col 8: ceiling dot rows %d/48, ceiling line rows %s, floor line rows %s" % (dots, lines_c, lines_f))
check(dots >= 30, "live screen col 8: >= 30 of 48 ceiling rows are the dot words (got %d)" % dots)
mirror = sorted(46 - 2 * ((r - 49) // 2) for r in lines_f if r % 2 == 1)   # floor line odd row 49+2w <-> ceiling even row 46-2w
check(sorted(lines_c) == mirror and lines_f, "ceiling line rows %s mirror the floor line rows %s" % (lines_c, lines_f))
'''
assert s.count(old) == 1
p.write_text(s.replace(old, new)); print("ok")
