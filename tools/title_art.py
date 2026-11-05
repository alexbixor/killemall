#!/usr/bin/env python3
"""title_art.py - procedurally draws the Kill'em all title/loading screen (256x192) as a PNG that obeys the
Spectrum attribute rules by construction: paper is black everywhere, each 8x8 cell has exactly one ink colour
(+BRIGHT), pixels are either ink or black.  All art is generated here from geometry - nothing is downloaded or traced.

Layout: rows 0..5  big blocky "KILL'EM ALL" lettering (own 4x4-block font), stepped fire gradient
                   (bright yellow / bright red / red), BRIGHT.
        rows 6..15 corridor vanishing into a glowing furnace doorway (horned figure inside), tiled floor,
                   beamed ceiling, panelled walls, flanked by two outlined horned demon heads (black silhouettes
                   with yellow slit eyes and a white fanged mouth).
        rows 16..23 black (menu is drawn there by the front end).
Usage: title_art.py <out.png>
"""
import sys
from PIL import Image

NORM, BRI = 0xD7, 0xFF
def rgb(i, bright):
    lv = BRI if bright else NORM
    return ((lv if i & 2 else 0), (lv if i & 4 else 0), (lv if i & 1 else 0))
BLACK, BLUE, RED, MAGENTA, GREEN, CYAN, YELLOW, WHITE = range(8)

# ---------------------------------------------------------------- lettering (4x4 px blocks, 12 blocks tall)
GLYPHS = {   # 10 block rows tall (40 px), drawn at y=4 so the logo has a 4 px black margin top and bottom
 'K': ["#..#", "#..#", "#.#.", "##..", "##..", "##..", "#.#.", "#..#", "#..#", "#..#"],
 'I': ["##"] * 10,
 'L': ["#..."] * 8 + ["####", "####"],
 "'": ["###", "###", "###", "..#", ".#."] + ["..."] * 5,
 'E': ["####", "####", "#...", "#...", "###.", "###.", "#...", "#...", "####", "####"],
 'M': ["#....#", "##..##", "##..##", "#.##.#", "#.##.#"] + ["#....#"] * 5,
 ' ': [".."] * 10,
 'A': [".##.", ".##.", "#..#", "#..#", "####", "####", "#..#", "#..#", "#..#", "#..#"],
}
BLOCK = 4
TEXT = "KILL'EM ALL"
GAP = 2  # blocks between glyphs

def draw_logo(on, ink):
    width_blocks = sum(len(GLYPHS[c][0]) for c in TEXT) + GAP * (len(TEXT) - 1)
    x0 = (256 - width_blocks * BLOCK) // 2
    bx = x0
    for ch in TEXT:
        g = GLYPHS[ch]
        for by, row in enumerate(g):
            for bxx, c in enumerate(row):
                if c == '#':
                    for dy in range(BLOCK):
                        for dx in range(BLOCK):
                            on[4 + by * BLOCK + dy][bx + bxx * BLOCK + dx] = 1
        bx += (len(g[0]) + GAP) * BLOCK
    # stepped fire gradient by cell row
    bands = {0: (YELLOW, 1), 1: (YELLOW, 1), 2: (RED, 1), 3: (RED, 1), 4: (RED, 0), 5: (RED, 0)}
    for cy, col in bands.items():
        for cx in range(32):
            ink[cy][cx] = col

# ---------------------------------------------------------------- scene helpers
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
def dither(x, y, intensity):
    return 1 if intensity * 16 > BAYER[y & 3][x & 3] else 0

def in_ellipse(pt, cx, cy, rx, ry):
    return ((pt[0] - cx) / rx) ** 2 + ((pt[1] - cy) / ry) ** 2 <= 1.0

def line_pts(x1, y1, x2, y2, w=1):
    pts = set(); steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    for i in range(steps + 1):
        x = round(x1 + (x2 - x1) * i / steps); y = round(y1 + (y2 - y1) * i / steps)
        for dx in range(w):
            for dy in range(w):
                pts.add((x + dx, y + dy))
    return pts

SCENE_TOP, SCENE_BOT = 48, 127
VP = (128, 84)
DOOR = (112, 143, 72, 95)       # x0,x1,y0,y1 - cell aligned (cells 14..17, rows 9..11)
HEAD_CX = (44, 255 - 44)
HC = 92                          # head centre y
RING_COL = (WHITE, 0)            # outline colour of the demon heads

def in_door(x, y):
    return DOOR[0] <= x <= DOOR[1] and DOOR[2] <= y <= DOOR[3]

def region(x, y):
    dx, dy = x - VP[0], y - VP[1]
    top_line = (SCENE_TOP - VP[1]) * (abs(dx) / 128.0)
    bot_line = (SCENE_BOT - VP[1]) * (abs(dx) / 128.0)
    if dy < top_line: return 'ceil'
    if dy > bot_line: return 'floor'
    return 'wall'

def scene_pixel(x, y):
    """returns (colour(index,bright), on) for a scene pixel before lines/silhouettes are applied."""
    if in_door(x, y):
        return (YELLOW, 1), 1
    dx, dy = x - VP[0], y - VP[1]
    dist = max(abs(dx) / 128.0, abs(dy) / 44.0)           # 0 at VP, 1 at the scene edges
    r = region(x, y)
    if r == 'ceil':
        return (BLUE, 0), dither(x, y, 0.10)
    if r == 'floor':
        inten = 0.45 + 0.5 * max(0.0, 0.6 - dist)
        col = (RED, 1) if dist < 0.30 else (RED, 0)
        return col, dither(x, y, inten)
    inten = 0.30 + 0.5 * max(0.0, 0.5 - dist)
    col = (RED, 1) if dist < 0.22 else (MAGENTA, 0)
    return col, dither(x, y, inten)

def head_black(head_cx):
    """black silhouette pixel set of one horned demon head"""
    black = set()
    for y in range(SCENE_TOP, SCENE_BOT + 1):
        for x in range(max(0, head_cx - 40), min(256, head_cx + 41)):
            if in_ellipse((x, y), head_cx, HC, 24, 22): black.add((x, y))       # skull
            if in_ellipse((x, y), head_cx, HC + 10, 17, 18): black.add((x, y))  # jaw / muzzle
    for side in (-1, 1):                                                        # horns: up, out, curl back in
        for t in range(0, 101):
            tt = t / 100.0
            px = head_cx + side * (9 + 38 * tt - 26 * tt * tt)
            py = HC - 14 - 34 * tt + 8 * tt * tt
            r = 6.5 * (1 - tt) + 1.3
            for y in range(int(py - r) - 1, int(py + r) + 2):
                for x in range(int(px - r) - 1, int(px + r) + 2):
                    if (x - px) ** 2 + (y - py) ** 2 <= r * r: black.add((x, y))
    return {(x, y) for (x, y) in black if 0 <= x < 256 and SCENE_TOP <= y <= SCENE_BOT}

def draw_scene(on, ink):
    votes = [[{} for _ in range(32)] for _ in range(24)]
    pix_col = {}
    def put(x, y, col=None, weight=1):
        if 0 <= x < 256 and SCENE_TOP <= y <= SCENE_BOT:
            on[y][x] = 1
            c = col or pix_col[(x, y)]
            v = votes[y // 8][x // 8]; v[c] = v.get(c, 0) + weight
    def cut(x, y):
        if 0 <= x < 256 and SCENE_TOP <= y <= SCENE_BOT:
            on[y][x] = 0
    for y in range(SCENE_TOP, SCENE_BOT + 1):
        for x in range(256):
            col, o = scene_pixel(x, y)
            on[y][x] = o
            pix_col[(x, y)] = col
            if o:
                v = votes[y // 8][x // 8]; v[col] = v.get(col, 0) + 1
    # corridor edges
    for corner in ((0, SCENE_TOP), (255, SCENE_TOP), (0, SCENE_BOT), (255, SCENE_BOT)):
        for p in line_pts(VP[0], VP[1], corner[0], corner[1]):
            if not in_door(*p): put(*p, weight=2)
    # ceiling beams (solid blue, converging)
    for xe in range(-128, 384, 64):
        for p in line_pts(VP[0], VP[1], xe, SCENE_TOP - 20):
            if 0 <= p[0] < 256 and SCENE_TOP <= p[1] <= SCENE_BOT and region(*p) == 'ceil' and not in_door(*p): put(*p, weight=2)
    # wall panels: converging lines at 1/3 and 2/3 wall height + vertical pillars at perspective depths
    for frac in (0.33, 0.66):
        ye = SCENE_TOP + (SCENE_BOT - SCENE_TOP) * frac
        for xe in (0, 255):
            for p in line_pts(VP[0], VP[1], xe, round(ye)):
                if region(*p) == 'wall' and abs(p[0] - VP[0]) > 16 and not in_door(*p): put(*p, weight=2)
    for d in (20, 32, 50, 76, 110):
        for sx in (-1, 1):
            x = VP[0] + sx * d
            yt = VP[1] + (SCENE_TOP - VP[1]) * d / 128.0
            yb = VP[1] + (SCENE_BOT - VP[1]) * d / 128.0
            for p in line_pts(x, round(yt), x, round(yb), 1 if d < 50 else 2): put(*p, weight=2)
    # floor tiles: dark converging lines (2 px) + dark depth rows cut out of the dense red dither
    for xe in range(-160, 416, 48):
        for p in line_pts(VP[0], VP[1], xe, SCENE_BOT + 40, 2):
            if region(*p) == 'floor' and abs(p[1] - VP[1]) > 10 and not in_door(*p): cut(*p)
    for d in (0.30, 0.50, 0.74, 1.0):
        y = round(VP[1] + (SCENE_BOT - VP[1]) * d)
        for x in range(0, 256):
            for yy in (y, y - 1):
                if region(x, yy) == 'floor' and not in_door(x, yy): cut(x, yy)
    # doorway figure: horned silhouette standing in the glow
    for (x, y) in figure_pts(128, DOOR[3] - 1, 20):
        if in_door(x, y): on[y][x] = 0
    # per-cell ink = majority colour of ON pixels
    for cy in range(SCENE_TOP // 8, SCENE_BOT // 8 + 1):
        for cx in range(32):
            v = votes[cy][cx]
            ink[cy][cx] = max(v.items(), key=lambda kv: (kv[1], kv[0]))[0] if v else (RED, 0)
    # demon heads: black silhouettes with a 1 px ink outline, yellow slit eyes, white fanged mouth
    for head_cx in HEAD_CX:
        black = head_black(head_cx)
        for (x, y) in black: on[y][x] = 0
        def dilate(S, r):
            out = set(S)
            for (x, y) in S:
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r: out.add((x + dx, y + dy))
            return out
        ring = dilate(black, 2) - black                   # 2 px solid outline in the cell's ink colour
        halo = dilate(black, 5) - dilate(black, 2)        # 3 px dark gap so the outline reads against the dither
        for (x, y) in halo:
            if 0 <= x < 256 and SCENE_TOP <= y <= SCENE_BOT and not in_door(x, y): on[y][x] = 0
        ring = {(x, y) for (x, y) in ring if 0 <= x < 256 and SCENE_TOP <= y <= SCENE_BOT and not in_door(x, y)}
        ring_cells = {(x // 8, y // 8) for (x, y) in ring}
        for (cx, cy) in ring_cells:                       # one consistent outline colour: clear the cell's dither
            for y in range(cy * 8, cy * 8 + 8):
                for x in range(cx * 8, cx * 8 + 8):
                    if SCENE_TOP <= y <= SCENE_BOT and not in_door(x, y): on[y][x] = 0
            ink[cy][cx] = RING_COL
        for (x, y) in ring: on[y][x] = 1
        eye_cells = set(); fang_cells = set()
        for side in (-1, 1):                                                        # slanted slit eyes
            ex = head_cx + side * 11
            for i in range(9):
                x = ex + side * (i - 4)
                yy = HC - 2 - ((i - 4) * side) // 3
                for y in (yy, yy + 1, yy + 2):
                    on[y][x] = 1; eye_cells.add((x // 8, y // 8))
            on[HC - 1][ex] = 0
        mouth_y = HC + 13                                                           # mouth line + fangs
        for x in range(head_cx - 13, head_cx + 14):
            on[mouth_y][x] = 1; fang_cells.add((x // 8, mouth_y // 8))
        for k in range(-2, 3):
            x = head_cx + k * 6
            ys = (mouth_y + 1, mouth_y + 2, mouth_y + 3, mouth_y + 4) if k % 2 == 0 else (mouth_y - 4, mouth_y - 3, mouth_y - 2, mouth_y - 1)
            for j, y in enumerate(ys):
                w = 2 if (k % 2 == 0 and j < 2) or (k % 2 and j >= 2) else 1
                for xx in range(x - w + 1, x + 1):
                    on[y][xx] = 1; fang_cells.add((xx // 8, y // 8))
        for cx, cy in eye_cells: ink[cy][cx] = (YELLOW, 1)
        for cx, cy in fang_cells: ink[cy][cx] = (WHITE, 0)

def figure_pts(cx, base_y, h_total=12):
    """horned humanoid silhouette standing at base_y, centred cx, h_total px tall (legs, body, head, horns, arms)"""
    pts = set()
    s = h_total / 12.0
    for y in range(base_y - h_total + 1, base_y + 1):
        h = (base_y - y) / s
        if h <= 4: w = 1 if int(h) % 2 else 2          # legs
        elif h <= 8: w = 3                              # body
        elif h <= 9: w = 1                              # neck
        else: w = 2                                     # head
        for x in range(cx - w, cx + w + 1): pts.add((x, y))
    for dy in (1, 2):
        pts.add((cx - 3, base_y - h_total - dy + 1)); pts.add((cx + 3, base_y - h_total - dy + 1))  # horns
    for y in range(base_y - int(8 * s), base_y - int(5 * s)):
        for ax in (5, 6):
            pts.add((cx - ax, y)); pts.add((cx + ax, y))  # arms out
    return pts

def main(out):
    on = [[0] * 256 for _ in range(192)]
    ink = [[(BLACK, 0)] * 32 for _ in range(24)]
    draw_logo(on, ink)
    draw_scene(on, ink)
    img = Image.new('RGB', (256, 192), (0, 0, 0))
    px = img.load()
    for y in range(128):                     # rows 16..23 stay black
        for x in range(256):
            if on[y][x]:
                i, b = ink[y // 8][x // 8]
                px[x, y] = rgb(i, b)
    img.save(out)
    print(f"{out}: 256x192 title art written")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/title_src.png')
