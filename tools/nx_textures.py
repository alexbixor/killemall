#!/usr/bin/env python3
"""nx_textures.py - lane B: palette + wall/floor textures of the Spectrum Next engine (docs/next_engine_spec_v0.1.md sections 1, 6, 7).

Writes, all under build/next/assets/:
  palette.bin    512 B : 256 entries x 2 bytes in Next 9-bit write order (byte0 = RRRGGGBB, byte1 bit0 = blue lsb);
                         index = material*16 + level (16 materials x 16 levels, level 15 brightest, level 0 of every material = black, index 0 = void)
  walls.bin     64 KB  : 16 wall textures x 4 shades x 4 pages x 256 B ; offset(t, s, u, v) = ((t*4 + s)*4 + (u >> 3))*256 + (u & 7)*32 + v  (32x32 texels)
  floors.bin     8 KB  : 8 floor textures x 4 shades x 256 B          ; offset(f, s, u, v) = (f*4 + s)*256 + u*16 + v                     (16x16 texels)
  manifest.json        : {"materials": {name: id}, "walls": {name: id}, "floors": {name: id}, "shade_rule": "...", "generator": "..."}
  preview_walls.png    : all 16 wall textures (columns W0..W15) x 4 shades (rows s0..s3) at 4x
  preview_floors.png   : all 8 floor textures (columns F0..F7, each tiled 2x2 to show the seams) x 4 shades at 4x
  preview_palette.png  : the 16 x 16 palette grid
Shades: s = 1, 2, 3 copies have every palette level reduced by 3, 6, 9 but never below level 1 unless the texel was level 0 (stays 0).
Deterministic: no randomness anywhere; the per-block tone variation comes from a fixed-seed FNV-1a hash of the block coordinates.
Art rules (mock-up reviews): ONE tone per brick/slab/plank, mortar/grout lines 1 texel, 1-texel bevel highlight top/left and shadow
bottom/right of every block, moss as whole-brick patches, vault ceiling = ribs (no gold studs), gold trim on the dais/lintel/altar,
no isolated texels anywhere (every texel shares its palette index with at least one 4-neighbour -> nothing can read as speckle).

usage: nx_textures.py [--dais-literal] [--out DIR]   generate everything. Default dais riser (walls id 5) = period-8 variant: gold
                                           nosing + shadow + bone on every 8-row course, so every 0.25-cell step riser shows its gold
                                           edge (build/night/B_QUESTIONS.md item 1, texture pass 2); --dais-literal = the spec-literal
                                           texture with the nosing in rows 0-1 only. --out DIR writes somewhere else than
                                           build/next/assets (e.g. build/night/T_assets); the variant is recorded in manifest "generator".
       nx_textures.py --verify [--out DIR]  re-read the written files and check sizes, layout, palette format and the art/shade rules
                                           (prints PASS/FAIL counts, exit code 1 on any failure)
Texture pass 2 (lane T): F1 plaster ceiling = two dark 2-texel wooden beams per cell with a 1-texel shadow line, 8x8 plaster panels
in two tones with 1-texel seams (was: one light 4-texel beam on flat plaster, which read as a flat cream area in the picture reviews).
"""
import hashlib, json, pathlib, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "build/next/assets"

# ---------------------------------------------------------------- palette ---------------------------------------------------------
# 16 materials, index = material*16 + level. Most ramps are PROPORTIONAL: colour(L) = round(T * (L + 2) / 17) per channel, with T the
# 3-bit top colour at level 15 (so the hue stays constant down the ramp - no pink/olive drift at the far shades, review round 2 - and
# the three shade steps of 3 levels each are ~1 unit of 3 bits each: even depth darkening). Level 1 is never black (max(T) >= 3).
# Channels are rounded independently so neutral greys stay neutral at every level.
MATERIALS = ["stone", "mortar", "brick", "wood", "iron", "moss", "flag", "plaster",
             "gold", "flame", "blood", "water", "rust", "bone", "dark", "bluestone"]
PROP = {
    "stone": (6, 6, 6),         # neutral grey wall stone
    "mortar": (4, 4, 4),        # dark grey joints
    "brick": (6, 3, 2),         # red-brown
    "wood": (6, 4, 2),          # brown
    "iron": (5, 5, 5),          # neutral steel grey, darker than stone (a blue tint reads as lavender in 3 bits)
    "moss": (3, 5, 1),          # yellow-green
    "flag": (5, 5, 5),          # grey floor stone, one step darker than wall stone
    "blood": (6, 1, 1),         # red
    "rust": (5, 3, 1),          # rusty brown
    "bluestone": (3, 4, 7),     # blue-grey stone
}
KEYS = {                        # explicit keypoint ramps (level, colour), linear in between, per-channel rounding: the dark ends are
    # steered so that the far shades keep reading as the same material (warm things darken to brown, not to olive or grey)
    "plaster": [(1, (1, 1, 0)), (4, (2, 2, 1)), (8, (4, 4, 3)), (12, (6, 6, 5)), (15, (7, 7, 6))],
    "gold": [(1, (1, 1, 0)), (5, (3, 2, 0)), (8, (4, 3, 0)), (11, (5, 4, 0)), (15, (7, 6, 1))],
    "bone": [(1, (1, 1, 0)), (4, (2, 2, 1)), (7, (4, 3, 2)), (10, (5, 5, 3)), (13, (6, 6, 4)), (15, (7, 7, 5))],
    "water": [(1, (0, 0, 1)), (15, (1, 3, 7))],                      # stays blue (a proportional ramp turns teal when dark)
    "flame": [(1, (2, 0, 0)), (8, (7, 3, 0)), (15, (7, 7, 4))],      # red -> orange -> pale yellow
    "dark": [(1, (1, 1, 1)), (15, (2, 2, 2))],                       # near-black neutral: levels 1-7 = (1,1,1), 8-15 = (2,2,2)
}
assert len(MATERIALS) == 16 and set(MATERIALS) == set(PROP) | set(KEYS)
TRANSPARENT_RRRGGGBB = 0xE3     # Next global transparency colour (nextreg 0x14 default): no palette entry may have this byte0


def rgb3(mat, level):
    """Next 3-bit colour (r, g, b) of palette entry material*16 + level; level 0 is black for every material"""
    if level <= 0:
        return (0, 0, 0)
    if mat in PROP:
        return tuple((2 * t * (level + 2) + 17) // 34 for t in PROP[mat])          # round(t * (level + 2) / 17)
    kp = KEYS[mat]
    for (l0, c0), (l1, c1) in zip(kp, kp[1:]):
        if l0 <= level <= l1:
            den = l1 - l0
            return tuple((2 * (a * den + (b - a) * (level - l0)) + den) // (2 * den) for a, b in zip(c0, c1))
    raise ValueError((mat, level))


def palette_rgb3():
    return [rgb3(m, l) for m in MATERIALS for l in range(16)]


def pal_entry_bytes(r, g, b):
    """Next 9-bit palette write order: byte0 = RRRGGGBB (blue msbs), byte1 bit0 = blue lsb"""
    return bytes([(r << 5) | (g << 2) | (b >> 1), b & 1])


def rgb255(c):
    return tuple(v * 255 // 7 for v in c)


# ---------------------------------------------------------------- deterministic hash --------------------------------------------
SEED = 0x9E3779B9


def hsh(*args):
    h = (0x811C9DC5 ^ SEED) & 0xFFFFFFFF
    for byte in "|".join(str(a) for a in args).encode():
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def pick(n, *args):
    return hsh(*args) % n


def tone_of(tones, seed, bx, by):
    """ONE tone per block: the first tone for 3 blocks in 4, the second for the rest (a designed variation, not a checkerboard)"""
    return tones[1] if len(tones) > 1 and pick(4, seed, bx, by) == 0 else tones[0]


# ---------------------------------------------------------------- texel helpers ---------------------------------------------------
# A texel is (material name, level 0..15). BLACK = palette index 0.
BLACK = ("stone", 0)
MORTAR = ("mortar", 5)          # (2,2,2)
GROUT = ("dark", 5)             # (1,1,1) at every shade: floor grout
CAVITY = ("dark", 5)            # (1,1,1): the back of a missing block, darker than the mortar at shade 0


def clamp(l):
    return max(1, min(15, l))


def bond(u, v, bw, bh, period, off=None):
    """running-bond block grid; returns (bx, by, x, y) = block ids and the texel position inside the block"""
    off = bw // 2 if off is None else off
    by = v // bh
    uu = (u + (off if by & 1 else 0)) % period
    return uu // bw, by, uu % bw, v % bh


def bevel(x, y, bw, bh):
    """block of bw x bh texels: 1-texel mortar on its right column and bottom row, 1-texel highlight top/left,
    1-texel shadow bottom/right, flat face inside"""
    if x == bw - 1 or y == bh - 1:
        return "mortar"
    if x == 0 or y == 0:
        return "hi"
    if x == bw - 2 or y == bh - 2:
        return "lo"
    return "face"


def shaded(mat, face, kind, hi=3, lo=3):
    return (mat, clamp(face + (hi if kind == "hi" else -lo if kind == "lo" else 0)))


def blocks(u, v, mat, tones, seed, bw=16, bh=8, period=32, mortar=MORTAR, off=None):
    """running-bond blocks, ONE tone per block (fixed hash of the block id), bevelled, 1-texel mortar"""
    bx, by, x, y = bond(u, v, bw, bh, period, off)
    k = bevel(x, y, bw, bh)
    if k == "mortar":
        return mortar
    return shaded(mat, tone_of(tones, seed, bx, by), k)


# ---------------------------------------------------------------- wall textures (32 x 32, u = along the wall, v = row from top) ---
def w_stone(u, v):
    return blocks(u, v, "stone", (12, 9), "stone")


def w_brick(u, v):
    return blocks(u, v, "brick", (12, 9), "brick", mortar=("mortar", 9))     # 16x8 bricks (Wolf3D scale), light mortar


MOSS_BLOCKS = {(0, 3), (1, 3), (0, 2)}                                   # (bx, by): the whole bottom course + one block above = a patch creeping up


def w_moss(u, v):
    bx, by, x, y = bond(u, v, 16, 8, 32)
    k = bevel(x, y, 16, 8)
    if k == "mortar":
        return MORTAR
    if (bx, by) in MOSS_BLOCKS:
        return shaded("moss", (12, 10)[pick(2, "mosstone", bx, by)], k)
    return w_stone(u, v)


def w_iron(u, v):
    x, y = u % 16, v % 16                                                # 16x16 riveted plates, 2 x 2 per cell
    if x == 15 or y == 15:
        return ("iron", 2)                                               # plate seam
    if (x in (2, 3) or x in (11, 12)) and (y in (2, 3) or y in (11, 12)):
        return ("iron", 15)                                              # 2x2 rivets
    if x == 0 or y == 0:
        return ("iron", 14)                                              # levels 14/10/7 give 4 distinct greys at every shade step
    if x == 14 or y == 14:
        return ("iron", 7)
    return ("iron", 10)


def plank(u, v, seed="plank"):
    p, x = u // 8, u % 8                                                 # vertical planks 8 wide, 1-texel dark seam, ONE tone each
    if x == 7:
        return ("dark", 10)
    return shaded("wood", (12, 10)[pick(4, seed, p) == 0], "hi" if x == 0 else "lo" if x == 6 else "face")


def rail(v, top, bot, mat="wood", face=8):
    if v < top or v > bot:
        return None
    return (mat, clamp(face + 4)) if v == top else (mat, clamp(face - 4)) if v == bot else (mat, face)


def w_wood(u, v):
    return rail(v, 6, 9) or rail(v, 22, 25) or plank(u, v)


def w_dais(u, v):
    """riser face: gold nosing rows 0-1, dark shadow row 2, then bone blocks whose courses end at rows 7, 15, 23, 31
    (so 0.25-cell risers show whole courses)"""
    if v < 2:
        return ("gold", 14 if v == 0 else 12)
    if v == 2:
        return ("dark", 5)
    c = v // 8
    y0 = 3 if c == 0 else c * 8
    bh = (c + 1) * 8 - y0
    uu = (u + (4 if c & 1 else 0)) % 32
    k = bevel(uu % 8, v - y0, 8, bh)
    if k == "mortar":
        return MORTAR
    return shaded("bone", (13, 11)[pick(4, "dais", uu // 8, c) == 0], k)


def w_dais_p8(u, v):
    """alternative (--dais-period8): nosing + shadow + bone on every 8-row course, so every 0.25-cell riser gets a gold edge
    whatever its world height"""
    y = v % 8
    if y < 2:
        return ("gold", 14 if y == 0 else 12)
    if y == 2:
        return ("dark", 5)
    c = v // 8
    uu = (u + (4 if c & 1 else 0)) % 32
    k = bevel(uu % 8, y - 3, 8, 5)
    if k == "mortar":
        return MORTAR
    return shaded("bone", (13, 11)[pick(4, "dais", uu // 8, c) == 0], k)


def w_lintel(u, v):
    if v < 3:
        return ("dark", 12)                                              # dark course (2,2,2)
    if v in (3, 4):
        return ("gold", 14 if v == 3 else 11)                            # gold trim
    return w_stone(u, v - 5)                                             # stone courses aligned under the trim


def w_altar(u, v):
    d2 = abs(2 * u - 31) + abs(2 * v - 31)                               # = 2 * (|u - 15.5| + |v - 15.5|)
    if d2 in (24, 26):
        return ("gold", 14)                                              # one big gold diamond outline, 2 texels thick, one tone
    return blocks(u, v, "bone", (13, 11), "altarface")


def w_bluestone(u, v):
    return blocks(u, v, "bluestone", (12, 9), "bluestone", bw=8, bh=8)


SKULL = ["................",
         ".....BBBBBB.....",
         "...BBBBBBBBBB...",
         "..BBBBBBBBBBBB..",
         "..BBBBBBBBBBBB..",
         ".BBBBBBBBBBBBBB.",
         ".BBDDDBBBBDDDBB.",
         ".BBDDDBBBBDDDBB.",
         ".BBDDDBBBBDDDBB.",
         ".BBBBBBBBBBBBBB.",
         "..BBBBBDDBBBBB..",
         "..BBBBBBBBBBBB..",
         "...BBBBBBBBBB...",
         "...BBDDDDDDBB...",
         "....BBBBBBBB....",
         "................"]
assert all(len(r) == 16 for r in SKULL)


def w_skulls(u, v):
    sx, sy, x, y = u // 16, v // 16, u % 16, v % 16                      # 2 x 2 big skulls per cell on a dark ground
    ch = SKULL[y][x]
    if ch == "B":
        return ("bone", (13, 11)[pick(4, "skull", sx, sy) == 0])
    if ch == "D":
        return ("dark", 5)                                               # eye sockets, nose, mouth (1,1,1)
    return ("mortar", 12)                                                # ground: dark grey that still steps down with depth (3,2,1,1)


def w_banner(u, v):
    if v < 2 and 8 <= u <= 23:
        return ("gold", 12)                                              # rod
    du2 = abs(2 * u - 31)                                                # 2 * |u - 15.5|
    hw2 = 11 if v <= 21 else 11 - 2 * (v - 21)                           # cloth 12 wide, pointed bottom rows 22..26
    if 2 <= v <= 26 and du2 <= hw2:
        if du2 + abs(2 * v - 23) <= 7:
            return ("gold", 13)                                          # emblem: gold diamond
        if du2 >= 11 and v <= 21:
            return ("blood", 7)                                          # rolled edges
        return ("blood", 11)
    return w_stone(u, v)


RING = [".iiii.",
        "ii..ii",
        "i....i",
        "i....i",
        "ii..ii",
        ".iiii."]                                                        # 6x6 iron ring handle, columns 23..28, rows 13..18


def w_irondoor(u, v):
    for top, bot in ((5, 9), (21, 25)):                                  # two dark iron straps with bright 2x2 rivets on each plank
        if top <= v <= bot:
            if v in (top + 1, top + 2) and (u % 8) in (3, 4):
                return ("iron", 14)
            return ("iron", 9) if v == top else ("iron", 2) if v == bot else ("iron", 5)
    if 13 <= v <= 18 and 23 <= u <= 28 and RING[v - 13][u - 23] == "i":
        return ("iron", 12)
    return plank(u, v, "irondoor")


FLAME = ["....o...",
         "...oo...",
         "...oyo..",
         "..oyyo..",
         "..oyyyo.",
         ".oyywyo.",
         ".oywwyo.",
         ".oyywyo.",
         "..oyyo..",
         "..oooo.."]                                                     # rows 4..13, columns 12..19


def w_torch(u, v):
    if 4 <= v <= 13 and 12 <= u <= 19:
        ch = FLAME[v - 4][u - 12]
        if ch != ".":
            return ("flame", {"o": 7, "y": 11, "w": 15}[ch])
    if v == 14 and 13 <= u <= 18:
        return ("rust", 14)                                              # cup rim
    if 15 <= v <= 16 and 13 <= u <= 18:
        return ("rust", 10)                                              # cup
    if 17 <= v <= 26 and 15 <= u <= 16:
        return ("rust", 12 if u == 15 else 8)                            # arm (lit / shadow side)
    if 27 <= v <= 28 and 13 <= u <= 18:
        return ("rust", 8)                                               # wall plate
    return w_stone(u, v)


def w_crumble(u, v):
    """stone wall with two blocks fallen out (dark cavities), two sunken blocks (darker, no bevel) and one 2-texel wide crack
    running down into the upper cavity (three straight runs, so it reads as a crack and not as scattered texels)"""
    bx, by, x, y = bond(u, v, 16, 8, 32)
    k = bevel(x, y, 16, 8)
    if k == "mortar":
        return MORTAR
    if (bx, by) in ((1, 1), (0, 3)):
        return CAVITY                                                    # missing blocks
    if (bx, by) in ((0, 0), (1, 2)):
        return ("stone", 7)                                              # sunken blocks, one flat dark tone
    if (bx, by) == (1, 0) and x in (5 + (y + 1) // 3, 6 + (y + 1) // 3):   # crack: x 5-6 (rows 0-1), 6-7 (rows 2-4), 7-8 (rows 5-6)
        return CAVITY
    return w_stone(u, v)


VINE = [0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 2, 2, 1, 1, 0, 0, -1, -1, -2, -2, -2, -3, -3, -3, -3, -2, -2, -1, -1, 0, 0]


def w_vines(u, v):
    for base, phase in ((8, 0), (24, 16)):                               # two wandering stems 2 wide with 4x3 leaves
        i = (v + phase) % 32
        c = base + VINE[i]
        if u in (c, c + 1):
            return ("moss", 8)
        if i % 8 in (2, 3, 4):
            left = ((i // 8) & 1) == 0
            lo_, hi_ = (c - 4, c - 1) if left else (c + 2, c + 5)
            if lo_ <= u <= hi_:
                return ("moss", 12)
    return w_stone(u, v)


def w_black(u, v):
    return BLACK


# ---------------------------------------------------------------- floor textures (16 x 16, u = x east, v = y south) --------------
def f_flag(u, v):
    return blocks(u, v, "flag", (12, 9), "flag", bw=8, bh=8, period=16, mortar=GROUT, off=0)


# F1 "plaster ceiling with beams" (texture pass 2, lane T): the first version (one 4-texel beam on flat plaster 12) read as a flat
# cream area in the picture reviews. Now, seen from below and tiling once per cell: TWO dark wooden beams per cell, 2 texels wide,
# running along v (u = 0-1 and 8-9, ONE tone per beam), a 1-texel near-black shadow line on the +u side of each beam (u = 2, 10), and
# between the beams plaster panels on an 8 x 8 grid (faces u = 3..7 / 11..15, v = 0..6 / 8..14; 1-texel neutral grey seam at v = 7
# and 15), each panel ONE of two plaster tones (the fourth panel of every cell is the darker one: a designed variation, not a
# checkerboard). Review round 1 of this pass: wood level 8 (4,2,1) read as "orange/rust", plaster 6/8 lines as "khaki smears" ->
# beams wood 7 (3,2,1) = dark brown, shadow = the "dark" ramp (1,1,1). Round 2: neutral grey seams (3,3,3) read as "grey rafters /
# vault truss lines" -> round 3: faint plaster seams, one step darker than the darker panel tone.
BEAM_U = (0, 8)                 # first column of each beam; the beam is u = b, b+1 and its shadow line is u = b+2
BEAM_TONES = (7, 7)             # wood (3,2,1): dark brown, one tone per plank (level 8 (4,2,1) read as orange; 5 (2,2,1) is olive)
PLASTER_TONES = (12, 10)        # (6,6,5) and (5,5,4): light plaster, faint two-tone panels
PLASTER_SEAM = ("plaster", 8)   # (4,4,3): faint 1-texel seam between the panels, one step darker than the darker panel
PLASTER_SHADOW = ("dark", 5)    # (1,1,1): the 1-texel shadow line beside each beam (same ramp as the floor grout)
PLASTER_ODD_PANEL = (1, 1)      # (u // 8, v // 8) of the darker panel


def f_plaster(u, v):
    for b, tone in zip(BEAM_U, BEAM_TONES):
        if b <= u <= b + 1:
            return ("wood", tone)
        if u == b + 2:
            return PLASTER_SHADOW
    if v % 8 == 7:
        return PLASTER_SEAM
    return ("plaster", PLASTER_TONES[1] if (u // 8, v // 8) == PLASTER_ODD_PANEL else PLASTER_TONES[0])


def f_vault(u, v):
    """plan view of one rib-vault bay per cell: transverse ribs along the cell edges (lit + shadow texel) and two diagonal
    groin ribs 2 texels wide, dark flat panels between (no studs)"""
    if u == 15 or v == 15:
        return ("stone", 12)                                             # edge rib, lit half (continues as u == 0 of the next cell)
    if u == 0 or v == 0:
        return ("stone", 9)                                              # edge rib, shadow half
    if u - v in (0, 1) or u + v in (14, 15):
        return ("stone", 12)                                             # diagonal ribs, 2 texels wide, one tone
    return ("stone", 6)                                                  # panels: one dark tone


def f_tread(u, v):
    return blocks(u, v, "bone", (13,), "tread", bw=8, bh=8, period=16, mortar=MORTAR, off=0)     # 2x2 slabs per cell, one tone


def f_altar(u, v):
    d2 = abs(2 * u - 15) + abs(2 * v - 15)                               # 2 * (|u - 7.5| + |v - 7.5|)
    if d2 in (8, 10):
        return ("gold", 14)                                              # gold diamond: bright rim 2 texels thick ...
    if d2 < 8:
        return ("gold", 11)                                              # ... and a darker fill
    k = bevel(u, v, 16, 16)                                              # one bone slab per cell
    return MORTAR if k == "mortar" else shaded("bone", 12, k)


WATER_BANDS = (13, 13, 10, 10, 7, 7, 10, 10)


def f_water(u, v):
    return ("water", WATER_BANDS[v % 8])


def f_cobble(u, v):
    return blocks(u, v, "stone", (9, 7), "cobble", bw=8, bh=8, period=16, mortar=GROUT, off=4)


POOL = ["................",                                              # asymmetric splat: heavy left lobe, one connected drip trailing down-right
        "................",
        "....rr..........",
        "...rrrrr........",
        "..rrrrrrrr......",
        ".rrrrrrrrrrr....",
        ".rrrrrrrrrrrr...",
        "..rrrrrrrrrrrr..",
        "..rrrrrrrrrrr...",
        "...rrrrrrrrr....",
        ".....rrrrrr.....",
        "......rrrrr.....",
        ".........rr.....",
        ".........rr.....",
        "..........rr....",
        "................"]
assert all(len(r) == 16 for r in POOL)


def f_bloodflag(u, v):
    if POOL[v][u] == "r":
        return ("blood", 8) if f_flag(u, v) == GROUT else ("blood", 11)  # the slab grooves show through the pool a little darker
    return f_flag(u, v)


WALLS = [("stone", w_stone), ("brick", w_brick), ("moss", w_moss), ("iron", w_iron), ("wood_door", w_wood),
         ("dais", w_dais), ("lintel", w_lintel), ("altar_face", w_altar), ("blue_stone", w_bluestone),
         ("bone_wall", w_skulls), ("banner", w_banner), ("iron_door", w_irondoor), ("torch", w_torch),
         ("crumbling", w_crumble), ("vines", w_vines), ("black", w_black)]
FLOORS = [("flag", f_flag), ("plaster", f_plaster), ("vault", f_vault), ("tread", f_tread),
          ("altar_top", f_altar), ("water", f_water), ("cobble", f_cobble), ("blood_flag", f_bloodflag)]

SHADE_RULE = ("palette index = material*16 + level (16 materials x 16 levels, level 15 brightest; level 0 of every material is black, "
              "index 0 = void). Shade copies s = 0..3: level_s = level - 3*s (i.e. -3, -6, -9), clamped so it never goes below level 1 "
              "unless the texel was level 0 (which stays 0 = black); the material is unchanged. The engine picks s from depth d (Q8): "
              "s = 0 if d < 384, 1 if d < 768, 2 if d < 1536, else 3; walls hit on side 1 use min(3, s + 1) (spec section 4).")


def shade_index(mat, level, s):
    if level == 0:
        return 0
    return MATERIALS.index(mat) * 16 + max(1, level - 3 * s)


def wall_offset(t, s, u, v):
    return ((t * 4 + s) * 4 + (u >> 3)) * 256 + (u & 7) * 32 + v


def floor_offset(f, s, u, v):
    return (f * 4 + s) * 256 + u * 16 + v


def select_variant(dais_period8):
    WALLS[5] = ("dais", w_dais_p8 if dais_period8 else w_dais)


def variant_of(argv_or_generator):
    """the dais variant named by a CLI argv list or by the manifest's "generator" string: period-8 nosing is the default
    (texture pass 2), the spec-literal texture (nosing in rows 0-1 only) needs --dais-literal. A manifest written by the
    pass-1 generator says "--dais-period8" explicitly and nothing at all for its (then default) literal variant."""
    if isinstance(argv_or_generator, (list, tuple)):
        return "--dais-literal" not in argv_or_generator
    words = str(argv_or_generator).split()
    return "--dais-period8" in words or ("--dais-literal" not in words and "pass2" in words)


def out_dir(argv):
    """--out DIR (relative to the repo root) selects where generate writes / verify reads; default build/next/assets"""
    if "--out" in argv:
        p = pathlib.Path(argv[argv.index("--out") + 1])
        return p if p.is_absolute() else ROOT / p
    return ASSETS


def despeckle(tx, n):
    """pixel-art clean-up pass: a texel whose (material, level) differs from all four wrapping neighbours would read as speckle
    (typically a bevel corner cut off by an overlay such as the altar diamond or the banner). It takes the value of the most
    common neighbour (ties: left, up, right, down - deterministic). Returns the number of texels changed."""
    changed = 0
    for _ in range(4):
        fixes = []
        for u in range(n):
            for v in range(n):
                nb = [tx[(u - 1) % n][v], tx[u][(v - 1) % n], tx[(u + 1) % n][v], tx[u][(v + 1) % n]]
                if tx[u][v] not in nb:
                    fixes.append((u, v, max(nb, key=lambda c: (nb.count(c), -nb.index(c)))))
        if not fixes:
            break
        for u, v, c in fixes:
            tx[u][v] = c
        changed += len(fixes)
    return changed


DESPECKLED = {}


def build_walls():
    b = bytearray(65536)
    for t, (name, fn) in enumerate(WALLS):
        tx = [[fn(u, v) for v in range(32)] for u in range(32)]
        DESPECKLED["W%d" % t] = despeckle(tx, 32)
        for s in range(4):
            for u in range(32):
                for v in range(32):
                    b[wall_offset(t, s, u, v)] = shade_index(tx[u][v][0], tx[u][v][1], s)
    return bytes(b)


def build_floors():
    b = bytearray(8192)
    for f, (name, fn) in enumerate(FLOORS):
        tx = [[fn(u, v) for v in range(16)] for u in range(16)]
        DESPECKLED["F%d" % f] = despeckle(tx, 16)
        for s in range(4):
            for u in range(16):
                for v in range(16):
                    b[floor_offset(f, s, u, v)] = shade_index(tx[u][v][0], tx[u][v][1], s)
    return bytes(b)


# ---------------------------------------------------------------- previews (decoded from the written bytes) ---------------------
def decode_palette(palb):
    pal = []
    for i in range(256):
        b0, b1 = palb[2 * i], palb[2 * i + 1]
        pal.append(rgb255(((b0 >> 5) & 7, (b0 >> 2) & 7, ((b0 & 3) << 1) | (b1 & 1))))
    return pal


def wall_image(walls, pal, t, s):
    im = Image.new("RGB", (32, 32))
    px = im.load()
    for u in range(32):
        for v in range(32):
            px[u, v] = pal[walls[wall_offset(t, s, u, v)]]
    return im


def floor_image(floors, pal, f, s, tile=2):
    im = Image.new("RGB", (16 * tile, 16 * tile))
    px = im.load()
    for x in range(16 * tile):
        for y in range(16 * tile):
            px[x, y] = pal[floors[floor_offset(f, s, x % 16, y % 16)]]
    return im


def sheet(path, title, col_labels, row_labels, imgs, scale=4):
    """imgs[col][row] = PIL image; every image is drawn at `scale` with NEAREST (pixel art)"""
    font = ImageFont.load_default(size=14)
    size = imgs[0][0].size[0] * scale
    gap, left, top = 10, 44, 48
    im = Image.new("RGB", (left + len(col_labels) * (size + gap), top + len(row_labels) * (size + gap)), (72, 72, 72))
    d = ImageDraw.Draw(im)
    d.text((left, 6), title, fill=(235, 235, 235), font=font)
    for c, lab in enumerate(col_labels):
        x = left + c * (size + gap)
        d.text((x + 2, top - 20), lab, fill=(255, 255, 255), font=font)
        for r, rl in enumerate(row_labels):
            y = top + r * (size + gap)
            if c == 0:
                d.text((6, y + size // 2 - 8), rl, fill=(255, 255, 255), font=font)
            im.paste(imgs[c][r].resize((size, size), Image.NEAREST), (x, y))
    im.save(path)
    return im.size


def palette_sheet(path, pal):
    font = ImageFont.load_default(size=12)
    cell = 22
    im = Image.new("RGB", (90 + 16 * cell, 20 + 16 * cell), (72, 72, 72))
    d = ImageDraw.Draw(im)
    for m, name in enumerate(MATERIALS):
        d.text((4, 20 + m * cell + 4), "%2d %s" % (m, name), fill=(255, 255, 255), font=font)
        for l in range(16):
            d.rectangle([90 + l * cell, 20 + m * cell, 90 + (l + 1) * cell - 1, 20 + (m + 1) * cell - 1], fill=pal[m * 16 + l])
    for l in range(16):
        d.text((90 + l * cell + 5, 3), "%X" % l, fill=(255, 255, 255), font=font)
    im.save(path)


def md5(b):
    return hashlib.md5(b).hexdigest()


def generate(argv):
    p8 = variant_of(argv)
    select_variant(p8)
    dest = out_dir(argv)
    dest.mkdir(parents=True, exist_ok=True)
    palb = b"".join(pal_entry_bytes(*c) for c in palette_rgb3())
    walls, floors = build_walls(), build_floors()
    manifest = {"materials": {m: i for i, m in enumerate(MATERIALS)},
                "walls": {name: i for i, (name, _) in enumerate(WALLS)},
                "floors": {name: i for i, (name, _) in enumerate(FLOORS)},
                "shade_rule": SHADE_RULE,
                "generator": "tools/nx_textures.py pass2" + (" --dais-period8" if p8 else " --dais-literal")}
    out = {"palette.bin": palb, "walls.bin": walls, "floors.bin": floors,
           "manifest.json": (json.dumps(manifest, indent=1) + "\n").encode()}
    print("output directory %s (dais variant: %s)" % (dest, "period-8 nosing" if p8 else "spec-literal nosing rows 0-1"))
    for name, data in out.items():
        (dest / name).write_bytes(data)
        print("%-14s %6d bytes  md5 %s" % (name, len(data), md5(data)))
    print("despeckled texels: " + ", ".join("%s=%d" % kv for kv in DESPECKLED.items() if kv[1]) + "  (total %d)" % sum(DESPECKLED.values()))
    pal = decode_palette(palb)
    w = sheet(dest / "preview_walls.png", "walls.bin: 16 wall textures (32x32) x 4 shades, 4x", ["W%d" % t for t in range(16)],
              ["s%d" % s for s in range(4)], [[wall_image(walls, pal, t, s) for s in range(4)] for t in range(16)])
    f = sheet(dest / "preview_floors.png", "floors.bin: 8 floor/ceiling textures (16x16, tiled 2x2) x 4 shades, 4x",
              ["F%d" % t for t in range(8)], ["s%d" % s for s in range(4)], [[floor_image(floors, pal, t, s) for s in range(4)] for t in range(8)])
    palette_sheet(dest / "preview_palette.png", pal)
    print("preview_walls.png %dx%d, preview_floors.png %dx%d, preview_palette.png" % (w + f))


# ---------------------------------------------------------------- verification (reads the files back) ---------------------------
def isolated_texels(get, n):
    """texels whose palette index differs from all four (wrapping) neighbours = what reads as speckle"""
    return sum(1 for u in range(n) for v in range(n)
               if get(u, v) not in (get((u + 1) % n, v), get((u - 1) % n, v), get(u, (v + 1) % n), get(u, (v - 1) % n)))


def verify(argv=()):
    fails, passes = [], 0

    def check(cond, msg):
        nonlocal passes
        if cond:
            passes += 1
        else:
            fails.append(msg)

    src = out_dir(list(argv))
    palb = (src / "palette.bin").read_bytes()
    walls = (src / "walls.bin").read_bytes()
    floors = (src / "floors.bin").read_bytes()
    man = json.loads((src / "manifest.json").read_text())
    p8 = variant_of(man["generator"])
    select_variant(p8)
    print("verifying %s (manifest generator: %s -> dais variant %s)" % (src, man["generator"], "period-8" if p8 else "spec-literal"))
    for name, data in (("palette.bin", palb), ("walls.bin", walls), ("floors.bin", floors)):
        print("%-12s %6d bytes  md5 %s" % (name, len(data), md5(data)))
    check(len(palb) == 512, "palette.bin size %d" % len(palb))
    check(len(walls) == 65536, "walls.bin size %d" % len(walls))
    check(len(floors) == 8192, "floors.bin size %d" % len(floors))
    check(set(man) == {"materials", "walls", "floors", "shade_rule", "generator"}, "manifest keys %s" % sorted(man))
    check(man["materials"] == {m: i for i, m in enumerate(MATERIALS)} and len(man["walls"]) == 16 and len(man["floors"]) == 8, "manifest ids")
    check(list(man["walls"].values()) == list(range(16)) and list(man["floors"].values()) == list(range(8)), "manifest ids are 0..n-1 in order")
    # palette format and content
    check(all(palb[2 * i + 1] in (0, 1) for i in range(256)), "palette byte1 must be 0/1 (blue lsb only)")
    check(palb[0] == 0 and palb[1] == 0, "palette index 0 must be black")
    check(all(palb[2 * (m * 16)] == 0 and palb[2 * (m * 16) + 1] == 0 for m in range(16)), "level 0 of every material black")
    check(all(palb[2 * (m * 16 + 1)] != 0 or palb[2 * (m * 16 + 1) + 1] != 0 for m in range(16)), "level 1 of every material is not black")
    check(all(palb[2 * i] != TRANSPARENT_RRRGGGBB for i in range(256)), "no palette entry equals the Next global transparency colour 0xE3")
    pal3 = [((palb[2 * i] >> 5) & 7, (palb[2 * i] >> 2) & 7, ((palb[2 * i] & 3) << 1) | (palb[2 * i + 1] & 1)) for i in range(256)]
    check(pal3 == palette_rgb3(), "palette.bin bytes match the ramps (per-channel 3-bit rounding)")
    for m in range(16):
        lum = [sum(pal3[m * 16 + l]) for l in range(16)]
        check(all(a <= b for a, b in zip(lum, lum[1:])), "ramp %s not monotonic" % MATERIALS[m])
    for m in ("stone", "mortar", "iron", "flag", "dark"):
        mi = MATERIALS.index(m)
        check(all(pal3[mi * 16 + l][0] == pal3[mi * 16 + l][1] == pal3[mi * 16 + l][2] for l in range(16)), "grey ramp %s stays neutral at every level" % m)
    # walls: shade rule for every texel against the s=0 copy, texel by texel
    bad = 0
    for t in range(16):
        for u in range(32):
            for v in range(32):
                i0 = walls[wall_offset(t, 0, u, v)]
                for s in range(1, 4):
                    i = walls[wall_offset(t, s, u, v)]
                    want = 0 if (i0 & 15) == 0 else (i0 & 0xF0) | max(1, (i0 & 15) - 3 * s)
                    bad += i != want
    check(bad == 0, "walls shade rule violated at %d texels" % bad)
    bad = 0
    for f in range(8):
        for u in range(16):
            for v in range(16):
                i0 = floors[floor_offset(f, 0, u, v)]
                for s in range(1, 4):
                    i = floors[floor_offset(f, s, u, v)]
                    want = 0 if (i0 & 15) == 0 else (i0 & 0xF0) | max(1, (i0 & 15) - 3 * s)
                    bad += i != want
    check(bad == 0, "floors shade rule violated at %d texels" % bad)
    # the written bytes equal a fresh deterministic generation (same variant as recorded in the manifest)
    check(walls == build_walls(), "walls.bin == deterministic regeneration")
    check(floors == build_floors(), "floors.bin == deterministic regeneration")

    def wmats(t, rows=range(32), s=0):
        return {MATERIALS[walls[wall_offset(t, s, u, v)] >> 4] for u in range(32) for v in rows if walls[wall_offset(t, s, u, v)]}

    def fmats(f):
        return {MATERIALS[floors[floor_offset(f, 0, u, v)] >> 4] for u in range(16) for v in range(16) if floors[floor_offset(f, 0, u, v)]}

    check(all(walls[wall_offset(15, s, u, v)] == 0 for s in range(4) for u in range(32) for v in range(32)), "W15 black = all index 0")
    check(all(walls[wall_offset(t, 0, u, v)] != 0 for t in range(15) for u in range(32) for v in range(32)), "W0..W14 contain no void texels")
    check(all(floors[floor_offset(f, 0, u, v)] != 0 for f in range(8) for u in range(16) for v in range(16)), "F0..F7 contain no void texels")
    check(wmats(5, range(0, 2)) == {"gold"}, "W5 dais rows 0-1 gold: %s" % wmats(5, range(0, 2)))
    check(wmats(5, range(2, 3)) == {"dark"}, "W5 dais row 2 dark: %s" % wmats(5, range(2, 3)))
    if not p8:
        check(wmats(5, range(3, 32)) == {"bone", "mortar"}, "W5 dais rows 3-31 bone blocks: %s" % wmats(5, range(3, 32)))
    else:
        check(all(wmats(5, range(c * 8 + 3, c * 8 + 8)) == {"bone", "mortar"} for c in range(4)), "W5 period-8 dais: bone courses")
        check(all(wmats(5, range(c * 8, c * 8 + 2)) == {"gold"} and wmats(5, range(c * 8 + 2, c * 8 + 3)) == {"dark"} for c in range(4)),
              "W5 period-8 dais: gold nosing rows 0-1 + dark shadow row 2 of every 8-row course (so every 0.25-cell riser shows its gold edge)")
    check(wmats(6, range(0, 3)) == {"dark"}, "W6 lintel rows 0-2 dark course: %s" % wmats(6, range(0, 3)))
    check(wmats(6, range(3, 5)) == {"gold"}, "W6 lintel rows 3-4 gold: %s" % wmats(6, range(3, 5)))
    check(wmats(6, range(5, 32)) == {"stone", "mortar"}, "W6 lintel rows 5-31 stone: %s" % wmats(6, range(5, 32)))
    check(wmats(7) == {"bone", "mortar", "gold"}, "W7 altar face bone + gold diamond: %s" % wmats(7))
    check(wmats(2) == {"stone", "mortar", "moss"}, "W2 moss = stone + moss patches: %s" % wmats(2))
    check(wmats(9) == {"bone", "mortar", "dark"}, "W9 bone wall = skulls on dark ground: %s" % wmats(9))
    check("gold" not in fmats(2) and fmats(2) == {"stone"}, "F2 vault: stone ribs only, no gold studs: %s" % fmats(2))
    check(fmats(3) == {"bone", "mortar"}, "F3 tread bone slabs: %s" % fmats(3))
    check(fmats(4) == {"bone", "mortar", "gold"}, "F4 altar top gold diamond on bone: %s" % fmats(4))
    check(fmats(0) == {"flag", "dark"}, "F0 flagstones + dark grout: %s" % fmats(0))
    check(fmats(1) == {"plaster", "wood", "dark"}, "F1 plaster panels + seams, wooden beams, dark shadow lines: %s" % fmats(1))
    # F1 texture pass 2: clearly textured, beams of wood, panels of plaster
    pal255_ = decode_palette(palb)

    def lum(i):
        return sum(pal255_[i])

    f1 = [[floors[floor_offset(1, 0, u, v)] for v in range(16)] for u in range(16)]
    f1_levels = {i & 15 for col in f1 for i in col if i}
    check(len(f1_levels) >= 3, "F1 has at least 3 distinct non-zero palette levels: %s" % sorted(f1_levels))
    wood_cols = [u for u in range(16) if all(MATERIALS[f1[u][v] >> 4] == "wood" for v in range(16))]
    check(wood_cols and all(MATERIALS[f1[u][v] >> 4] != "wood" for u in range(16) if u not in wood_cols for v in range(16)),
          "F1 beams: every wood texel belongs to a full-height beam column: %s" % wood_cols)
    beams = [u for u in wood_cols if (u - 1) % 16 not in wood_cols]                    # first column of each beam
    check(len(beams) >= 1 and all(u + 1 in wood_cols and (u + 2) % 16 not in wood_cols for u in beams),
          "F1 beams are exactly 2 texels wide (wood columns %s)" % wood_cols)
    check(all(len({f1[u][v] for v in range(16)} | {f1[u + 1][v] for v in range(16)}) == 1 for u in beams), "F1 one tone per beam (plank)")
    shadow_cols = [(u + 2) % 16 for u in beams]
    seam_rows = (7, 15)
    plaster_face = [f1[u][v] for u in range(16) for v in range(16) if MATERIALS[f1[u][v] >> 4] == "plaster" and v not in seam_rows]
    check(plaster_face and all(u not in wood_cols and u not in shadow_cols
                               for u in range(16) for v in range(16) if MATERIALS[f1[u][v] >> 4] == "plaster"),
          "F1 plaster only on the panel faces and seams (not in beams or shadow lines)")
    face_min = min(lum(i) for i in plaster_face) if plaster_face else 0
    beam_lum = max(lum(f1[u][0]) for u in beams) if beams else 0
    check(beam_lum < face_min, "F1 beams darker than the darkest plaster tone (beam %d vs plaster %d)" % (beam_lum, face_min))
    check(all(len({f1[u][v] for v in range(16)}) == 1 and MATERIALS[f1[u][0] >> 4] not in ("wood", "plaster") and lum(f1[u][0]) < beam_lum
              for u in shadow_cols), "F1 1-texel shadow line beside each beam: one index, darker than the beam, not wood/plaster")
    panels = {}
    for u in range(16):
        for v in range(16):
            if MATERIALS[f1[u][v] >> 4] == "plaster" and v not in seam_rows:
                panels.setdefault((u // 8, v // 8), set()).add(f1[u][v])
    check(len(panels) == 4 and all(len(s) == 1 for s in panels.values()), "F1 plaster panels (8x8 grid): ONE tone per panel")
    check(len({i for s in panels.values() for i in s}) == 2, "F1 plaster panels use exactly two plaster tones")
    seam = [f1[u][v] for u in range(16) for v in seam_rows if u not in wood_cols and u not in shadow_cols]
    check(len(set(seam)) == 1 and MATERIALS[seam[0] >> 4] != "wood" and lum(seam[0]) < face_min,
          "F1 1-texel seam between the panels: one index, darker than the plaster panels, not wood")
    check(fmats(5) == {"water"}, "F5 water: %s" % fmats(5))
    check("blood" in fmats(7) and "flag" in fmats(7), "F7 blood-stained flag: %s" % fmats(7))
    # moss comes as whole blocks: every moss texel's block (16x8 running bond) is moss on its entire face
    moss_ok = True
    for u in range(32):
        for v in range(32):
            bx, by, x, y = bond(u, v, 16, 8, 32)
            is_moss = MATERIALS[walls[wall_offset(2, 0, u, v)] >> 4] == "moss"
            if bevel(x, y, 16, 8) != "mortar" and is_moss != ((bx, by) in MOSS_BLOCKS):
                moss_ok = False
    check(moss_ok, "W2 moss patches are whole blocks")
    # mortar / grout lines 1 texel: no 2x2 block of mortar texels in the block textures (wrapping)
    for t in (0, 1, 2, 5, 6, 7, 8, 13):
        def ism(u, v):
            i = walls[wall_offset(t, 0, u % 32, v % 32)]
            return i and MATERIALS[i >> 4] == "mortar"
        thick = sum(1 for u in range(32) for v in range(32) if ism(u, v) and ism(u + 1, v) and ism(u, v + 1) and ism(u + 1, v + 1))
        check(thick == 0, "W%d mortar thicker than 1 texel at %d places" % (t, thick))
    for f in (0, 1, 3, 6, 7):
        def isg(u, v):
            i = floors[floor_offset(f, 0, u % 16, v % 16)]
            return i and MATERIALS[i >> 4] in ("mortar", "dark")
        thick = sum(1 for u in range(16) for v in range(16) if isg(u, v) and isg(u + 1, v) and isg(u, v + 1) and isg(u + 1, v + 1))
        check(thick == 0, "F%d grout/seam/shadow lines thicker than 1 texel at %d places" % (f, thick))
    # one tone per block: in the block walls every block face (excluding the bevel) is a single palette index
    for t, bw, bh in ((0, 16, 8), (1, 16, 8), (8, 8, 8)):
        multi = 0
        for by in range(32 // bh):
            for bx in range(32 // bw):
                faces = set()
                for x in range(1, bw - 2):
                    for y in range(1, bh - 2):
                        off = (bw // 2) if by & 1 else 0
                        u = (bx * bw + x - off) % 32
                        faces.add(walls[wall_offset(t, 0, u, by * bh + y)])
                multi += len(faces) > 1
        check(multi == 0, "W%d blocks with more than one face tone: %d" % (t, multi))
    # bevel: in the stone wall the highlight (x == 0 or y == 0 of a block) is brighter than the face, the shadow (x == bw-2 / y == bh-2) darker
    bev_ok = True
    for u in range(32):
        for v in range(32):
            bx, by, x, y = bond(u, v, 16, 8, 32)
            k = bevel(x, y, 16, 8)
            if k == "mortar":
                continue
            face_u = (bx * 16 + 2 - (8 if by & 1 else 0)) % 32
            face = walls[wall_offset(0, 0, face_u, by * 8 + 2)] & 15
            lvl = walls[wall_offset(0, 0, u, v)] & 15
            if (k == "hi" and not lvl > face) or (k == "lo" and not lvl < face) or (k == "face" and lvl != face):
                bev_ok = False
    check(bev_ok, "W0 bevel: highlight top/left brighter, shadow bottom/right darker than the face")
    # speckle gate: no isolated texel anywhere (every texel shares its index with a 4-neighbour)
    for t in range(16):
        n = isolated_texels(lambda u, v, t=t: walls[wall_offset(t, 0, u, v)], 32)
        check(n == 0, "W%d has %d isolated texels (speckle)" % (t, n))
    for f in range(8):
        n = isolated_texels(lambda u, v, f=f: floors[floor_offset(f, 0, u, v)], 16)
        check(n == 0, "F%d has %d isolated texels (speckle)" % (f, n))
    # visible depth darkening: mean 8-bit luminance of each shade copy strictly decreases (textures 0..14)
    pal255 = decode_palette(palb)
    for t in range(15):
        lum = [sum(sum(pal255[walls[wall_offset(t, s, u, v)]]) for u in range(32) for v in range(32)) for s in range(4)]
        check(lum[0] > lum[1] > lum[2] > lum[3], "W%d shades do not darken monotonically: %s" % (t, lum))
    for f in range(8):
        lum = [sum(sum(pal255[floors[floor_offset(f, s, u, v)]]) for u in range(16) for v in range(16)) for s in range(4)]
        check(lum[0] > lum[1] > lum[2] > lum[3], "F%d shades do not darken monotonically: %s" % (f, lum))
    for m in fails:
        print("FAIL:", m)
    print("verify: %d checks passed, %d failed" % (passes, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--verify" in sys.argv[1:]:
        sys.exit(verify(sys.argv[1:]))
    generate(sys.argv[1:])
