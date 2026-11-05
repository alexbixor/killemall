#!/usr/bin/env python3
"""m22_mockup.py - attribute-legal 256x192 mockup of the M2.2 look (Northern-Lights/TTT style, non-bright palette).
3D window (rows 1..12, cols 8..23) reused from a real M2.1 frame (de-brightened, floor one grey checker), framed by a 1-px red
line in the pixel rows/columns just outside it (x 63 / x 192 / y 7) and a red rail at y 104 (row 13); two red dividers at
x 83 and x 171 split the panel into AMMO | HEALTH+SHIELD | KEYS+KILLS. Flat 1-px line art, labels bold red, values white.
Panel rows: 14 labels (+ values right-aligned), 16-17 instruments, 18 second labels/values, 20 second instruments.
  AMMO   cols 2..9 : 10 cartridge slots (1 slot = 10 rounds) drawn as the ammo of the weapon at hand: pistol = grey lead
                     head (attr row 16) over a brass case (attr row 17); shotgun = red shell over a brass base. Empty slot =
                     outlines only. Value row 14, weapon name row 19.
  HEALTH cols 11..19: framed white bar 72x10 rows 16-17 (turns red at <= 33), label + value row 14.
  SHIELD cols 11..19: framed cyan bar 72x10 rows 20-21, label + value row 18.
  KEYS   cols 22..31: 16x8 pills (red R, blue B): filled with black letter = held, outline = missing.  KILLS row 18 + value.
Validation: every 8x8 cell has <= 1 ink on black paper and no BRIGHT; exit 1 otherwise (the mockup must be drawable).
usage: m22_mockup.py [health ammo keys kills shield]   (defaults 100 46 R 1 50); env WEAPON=pistol|shotgun
out: build/m22_mockup_1x.png, build/m22_mockup.png (3x), build/m22_mockup_vs_ttt.png"""
import sys, os
from PIL import Image, ImageDraw

HEALTH = int(sys.argv[1]) if len(sys.argv) > 1 else 100
AMMO = int(sys.argv[2]) if len(sys.argv) > 2 else 46
KEYS = sys.argv[3] if len(sys.argv) > 3 else "R"          # letters held: R and/or B
KILLS = int(sys.argv[4]) if len(sys.argv) > 4 else 1
SHIELD = int(sys.argv[5]) if len(sys.argv) > 5 else 50
WEAPON = os.environ.get("WEAPON", "pistol")

ROM = open('tools/zesarux/48.rom', 'rb').read()
BLK, B, R, M, G, C, Y, W = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0),
                            (215, 215, 215)]
IDX = {0: BLK, 1: B, 2: R, 3: M, 4: G, 5: C, 6: Y, 7: W}

def base(c):                       # any rgb -> spectrum colour index (bright dropped)
    r, g, b = c
    return (b > 127) * 1 + (r > 127) * 2 + (g > 127) * 4

src = Image.open('build/m21_play_02_fight.png').convert('RGB').resize((256, 192), Image.NEAREST)
img = Image.new('RGB', (256, 192), BLK)
px, sp = img.load(), src.load()
for y in range(8, 104):            # 3D window: de-bright; floor rows (y >= 72) cyan band -> grey checker colour
    for x in range(64, 192):
        i = base(sp[x, y])
        if y >= 72 and i == 5:
            i = 7
        px[x, y] = IDX[i]
d = ImageDraw.Draw(img)

def glyph(ch):
    o = 0x3D00 + (ord(ch) - 32) * 8
    return list(ROM[o:o + 8])

def text(x, y, s, col, bold=True):
    for ch in s:
        for r, b in enumerate(glyph(ch)):
            if bold:
                b |= b >> 1
            for i in range(8):
                if b & (128 >> i):
                    px[x + i, y + r] = col
        x += 8

def polyline(pts, col):
    d.line(pts, fill=col, width=1)

def bitmap(x, y, rows, col):       # rows of '#'/'.' strings
    for r, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == '#':
                px[x + i, y + r] = col

def bar(x, y, w, v, col):          # framed bar w x 8 at (x,y): 1-px frame, 6-px fill of (w-2)*v/100
    d.rectangle([x, y, x + w - 1, y + 7], outline=col)
    f = (w - 2) * max(0, min(v, 100)) // 100
    if f:
        d.rectangle([x + 1, y + 1, x + f, y + 6], fill=col)

# ---- frame: window border, rail, dividers (all red, 1 px)
polyline([(63, 7), (192, 7)], R)
polyline([(63, 7), (63, 104)], R)
polyline([(192, 7), (192, 104)], R)
polyline([(0, 104), (255, 104)], R)
for yy in range(105, 168):
    px[83, yy] = R
    px[171, yy] = R

# ---- AMMO panel (cols 2..9, x 16..79)
text(16, 112, "AMMO", R)
text(56, 112, "%02d" % AMMO, W)
lit = (min(AMMO, 99) + 9) // 10
HEAD = ["..#..", ".###.", "#####", "#####", "#####", "#####"]                  # pistol: lead head, y 130..135 (row 16)
HEAD_EMPTY = ["..#..", ".#.#.", "#...#", "#...#", "#...#", "#...#"]
CASE = ["#####"] * 7                                                           # brass case y 136..142 (row 17)
CASE_EMPTY = ["#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#####"]
SHELL = [".###.", "#####", "#####", "#####", "#####", "#####", "#####"]        # shotgun: red shell y 129..135 (row 16)
SBASE = ["#####"] * 5                                                          # brass base y 136..140 (row 17)
SBASE_EMPTY = ["#####", "#...#", "#...#", "#...#", "#####"]
SHELL_EMPTY = [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#"]
for k in range(10):
    x = 16 + 6 * k
    if WEAPON == "shotgun":
        if k < lit:
            bitmap(x, 129, SHELL, R)
            bitmap(x, 136, SBASE, Y)
        else:
            bitmap(x, 129, SHELL_EMPTY, R)
            bitmap(x, 136, SBASE_EMPTY, Y)
    else:
        if k < lit:
            bitmap(x, 130, HEAD, W)
            bitmap(x, 136, CASE, Y)
        else:
            bitmap(x, 130, HEAD_EMPTY, W)
            bitmap(x, 136, CASE_EMPTY, Y)
text(16, 152, "SHOTGUN" if WEAPON == "shotgun" else "PISTOL", W)

# ---- HEALTH + SHIELD panel (cols 11..20, x 88..167): icon col 11, bar cols 12..20 (72 px)
hcol = R if HEALTH <= 33 else W
text(88, 112, "HEALTH", R)
text(144, 112, "%03d" % HEALTH, hcol)
def hbar(x, y, v, col):            # 72 x 10 bar: 1-px frame, solid fill (70*v/100 px), empty part = 50% checker trough
    d.rectangle([x, y, x + 71, y + 9], outline=col)                 # (TTT "grey") so the bar reads as a bar even when low
    f = 70 * max(0, min(v, 100)) // 100
    if f:
        d.rectangle([x + 1, y + 1, x + f, y + 8], fill=col)
    for yy in range(y + 1, y + 9):
        for xx in range(x + 1 + f, x + 71):
            if (xx + yy) & 1 == 0:
                px[xx, yy] = col
hbar(88, 128, HEALTH, hcol)                                        # HEALTH bar cols 11..19, rows 16-17
text(88, 144, "SHIELD", R)
text(144, 144, "%03d" % SHIELD, W)
hbar(88, 160, SHIELD, C)                                           # SHIELD bar cols 11..19, rows 20-21

# ---- KEYS + KILLS panel (cols 22..31, x 176..255)
text(176, 112, "KEYS", R)
def pill(x, y, col, letter, held):
    if held:
        d.rounded_rectangle([x, y, x + 15, y + 7], radius=4, fill=col)
        for r, b in enumerate(glyph(letter)):
            for i in range(8):
                if b & (128 >> i):
                    px[x + 4 + i, y + r] = BLK
    else:
        d.rounded_rectangle([x, y, x + 15, y + 7], radius=4, outline=col)
        for r, b in enumerate(glyph(letter)):
            for i in range(8):
                if b & (128 >> i) and 1 <= r <= 6:
                    px[x + 4 + i, y + r] = col
pill(176, 128, R, "R", "R" in KEYS)
pill(200, 128, B, "B", "B" in KEYS)
text(176, 144, "KILLS", R)
text(224, 144, "%03d" % KILLS, W)

# ---- validation: one ink per cell on black paper, no BRIGHT
bad = []
for cyc in range(24):
    for cxc in range(32):
        cols = {px[cxc * 8 + i, cyc * 8 + j] for i in range(8) for j in range(8)} - {BLK}
        if len(cols) > 1 or any(max(c) > 215 for c in cols):
            bad.append((cxc, cyc, sorted(cols)))
img.save('build/m22_mockup_1x.png')
img.resize((768, 576), Image.NEAREST).save('build/m22_mockup.png')
ref = Image.open('ref/ttt/shot_5_549332.png').convert('RGB').resize((512, 384), Image.NEAREST)
side = Image.new('RGB', (1040, 384), (40, 40, 40))
side.paste(img.resize((512, 384), Image.NEAREST), (0, 0))
side.paste(ref, (528, 0))
side.save('build/m22_mockup_vs_ttt.png')
print("cells violating attribute rules:", len(bad), bad[:8])
sys.exit(1 if bad else 0)
