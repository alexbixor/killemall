#!/usr/bin/env python3
"""refcast.py — reference renderer for the Kill'em All 48K look (Python, pixel-exact to the planned Z80 engine).

Renders one frame of a level at Spectrum resolution: 64 rays × 2 px wide into a 128×96 window at cells x 8..23,
y 1..12; 8×8 1-bit textures repeated 4× over a wall; distance shading via per-cell attributes (ink = texture colour,
BRIGHT when near, black paper); ceiling black, floor 50 % checker; HUD frame + fps counter line.
Usage: refcast.py <level.bin> <level_index> <px> <py> <angle_deg> <out.png> [scale]
"""
import sys, math, struct
from PIL import Image

W, H = 128, 96            # game window pixels
RAYS = 64                  # 2 px per ray
WIN_X, WIN_Y = 64, 8       # window origin on the 256×192 screen
FOV = math.radians(60)
TEX = {                    # 8 bytes = 8 rows, bit7 = left pixel; index 1..7 walls, 8..10 doors, 11 secret(=1), 12 exit
    1: [0xFF, 0x81, 0x81, 0x81, 0xFF, 0x18, 0x18, 0x18],        # grey stone blocks
    2: [0xFF, 0x80, 0x80, 0x80, 0xFF, 0x08, 0x08, 0x08],        # bricks
    3: [0x00, 0x24, 0x00, 0x81, 0x00, 0x24, 0x00, 0x81],        # moss dots
    4: [0x3C, 0x42, 0x81, 0x81, 0x81, 0x81, 0x42, 0x3C],        # tech rings
    5: [0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00],        # stripes
    6: [0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81],        # cross hatch
    7: [0xF0, 0xF0, 0xF0, 0xF0, 0x0F, 0x0F, 0x0F, 0x0F],        # big checker
    8: [0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66],        # door: bars
    9: [0x66, 0x66, 0x7E, 0x7E, 0x7E, 0x7E, 0x66, 0x66],        # red door
    10: [0x66, 0x5A, 0x66, 0x5A, 0x66, 0x5A, 0x66, 0x5A],       # blue door
    12: [0xFF, 0x81, 0xBD, 0xA5, 0xA5, 0xBD, 0x81, 0xFF],       # exit panel
}
TEX[11] = TEX[1]
INK = {1: 7, 2: 2, 3: 4, 4: 1, 5: 6, 6: 3, 7: 5, 8: 6, 9: 2, 10: 1, 11: 7, 12: 4}   # Spectrum colour per texture
PAL = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215)]
BRI = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

def load(path, idx):
    b = open(path, 'rb').read(); off = 1
    for _ in range(idx + 1):
        n_things = b[off + 7]; size = 8 + 32 * 32 + 3 * n_things
        blob = b[off:off + size]; off += size
    w, h, sx, sy, ang, nt = struct.unpack('<BBBBBB', blob[2:8])
    cells = blob[8:8 + w * h]; things = [tuple(blob[8 + w * h + 3 * i: 8 + w * h + 3 * i + 3]) for i in range(nt)]
    return cells, (sx + 0.5, sy + 0.5, ang), things

def cast(cells, px, py, ang):
    """Returns per ray: (perp distance, texture index, texX 0..7, side)."""
    out = []
    dx, dy = math.cos(ang), math.sin(ang)
    plane = math.tan(FOV / 2)
    pxl, pyl = -dy * plane, dx * plane
    for r in range(RAYS):
        cam = 2 * (r + 0.5) / RAYS - 1
        rdx, rdy = dx + pxl * cam, dy + pyl * cam
        mx, my = int(px), int(py)
        ddx = abs(1 / rdx) if rdx else 1e9; ddy = abs(1 / rdy) if rdy else 1e9
        stx, sdx = (-1, (px - mx) * ddx) if rdx < 0 else (1, (mx + 1 - px) * ddx)
        sty, sdy = (-1, (py - my) * ddy) if rdy < 0 else (1, (my + 1 - py) * ddy)
        side = 0
        for _ in range(64):
            if sdx < sdy: sdx += ddx; mx += stx; side = 0
            else: sdy += ddy; my += sty; side = 1
            if cells[my * 32 + mx]: break
        tex = cells[my * 32 + mx]
        dist = (sdx - ddx) if side == 0 else (sdy - ddy)
        wall_x = (py + dist * rdy) if side == 0 else (px + dist * rdx)
        wall_x -= math.floor(wall_x)
        out.append((max(dist, 0.05), tex, int(wall_x * 32) & 7, side))
    return out

def render(cells, px, py, ang, scale=3):
    rays = cast(cells, px, py, ang)
    pix = [[0] * W for _ in range(H)]                  # 1-bit window
    tops, bots = [], []
    for r, (dist, tex, tx, side) in enumerate(rays):
        hgt = min(H, int(H / dist))
        top = (H - hgt) // 2; bot = top + hgt; tops.append(top); bots.append(bot)
        col = TEX[tex]
        for y in range(H):
            if y < top: v = 0
            elif y >= bot: v = (y ^ (r >> 0)) & 1       # floor checker (per 2-px column)
            else:
                ty = ((y - top) * 32 // max(hgt, 1)) & 7
                v = (col[ty] >> (7 - tx)) & 1
            pix[y][2 * r] = pix[y][2 * r + 1] = v
    attr = [[(0, 0)] * (W // 8) for _ in range(H // 8)]  # (ink, bright)
    for cy in range(H // 8):
        for cx in range(W // 8):
            rs = range(4 * cx, 4 * cx + 4); y0, y1 = cy * 8, cy * 8 + 8
            walls = [(rays[r][0], rays[r][1]) for r in rs if tops[r] < y1 and bots[r] > y0]
            if walls:
                d, t = min(walls); attr[cy][cx] = (INK[t], 1 if d < 3 else 0)
            elif all(bots[r] <= y0 for r in rs):          # floor: near rows white, far rows blue
                attr[cy][cx] = (7, 0) if cy >= 9 else (1, 0) if cy <= 6 else (5, 0)
            else: attr[cy][cx] = (0, 0)                      # ceiling: black
    img = Image.new('RGB', (256, 192), (0, 0, 0))
    for y in range(H):
        for x in range(W):
            ink, br = attr[y // 8][x // 8]
            img.putpixel((WIN_X + x, WIN_Y + y), (BRI if br else PAL)[ink] if pix[y][x] else (0, 0, 0))
    # HUD frame: cells around the window in dim red, status strip rows 14–16
    for x in range(256):
        for y in list(range(0, 8)) + list(range(104, 112)):
            if (x // 8 + y // 8) % 2 == 0 and y % 8 in (3, 4): img.putpixel((x, y), PAL[2])
    for y in range(112, 192):
        for x in range(256):
            if y in (112, 191) or x in (0, 255): img.putpixel((x, y), PAL[7])
    return img.resize((256 * scale, 192 * scale), Image.NEAREST), rays

if __name__ == '__main__':
    path, idx, px, py, deg, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 3
    cells, start, things = load(path, idx)
    img, rays = render(cells, px, py, math.radians(deg), scale)
    img.save(out)
    print(f"{out}: start={start} dist range {min(r[0] for r in rays):.2f}–{max(r[0] for r in rays):.2f}, textures {sorted({r[1] for r in rays})}")
