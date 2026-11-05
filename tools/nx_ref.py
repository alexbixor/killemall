#!/usr/bin/env python3
"""nx_ref.py - exact integer reference renderer for the Kill'em all Spectrum Next engine
(docs/next_engine_spec_v0.1.md sections 0-5, 7, 9).  Lane R.

The Z80N engine and this file must produce IDENTICAL frame bytes for the same inputs, so everything here is
integer arithmetic following the spec literally (smul_shr sign-magnitude products, ROW() on signed Q8, int16
clamps, the RECIP/RD/SIN/COS tables imported from tools/nx_tables.py so both sides share one table).

Importable:
    render(level, px, py, a, walls, floors) -> (frame bytes (12288, row-major 128x96 palette indices),
                                                records list, zbuf list)
        level  = 2048-byte level0.bin blob or a Level object
        walls  = 65536-byte walls.bin blob (or WallTex), floors = 8192-byte floors.bin blob (or FloorTex)
        records: ordered list of {"op": "PLANE_ADD"|"DRAW_PIECE"|"VOID", "args": [...spec argument order...],
                 "kind": debug tag, "d": depth} ; the canonical comparison for lane D1 is (op, args).
    camera_info(level, px, py, a) -> dict(px, py, a, eye, mx, my, dirx, diry, plx, ply)
    SCENES: the four test scenes of spec section 9.

CLI:
    .venv/bin/python tools/nx_ref.py                 renders all four scenes into build/night/ref/
    .venv/bin/python tools/nx_ref.py hall corridor   only those scenes
Outputs per scene: <scene>.frame.bin, <scene>.png (4x), <scene>.records.json, <scene>.camera.json,
<scene>.trace.json (per-column DDA trace, debugging aid for lane D1); plus columns.txt (centre column runs) and
placeholder_walls.bin / placeholder_floors.bin when build/next/assets/{walls,floors}.bin are not (yet) there.
"""
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_tables import SIN, COS, RD, RECIP  # noqa: E402  (shared with the Z80 tables bank)

ROOT = HERE.parent
ASSETS = ROOT / "build/next/assets"
REF = ROOT / "build/night/ref"

W, H = 128, 96          # LoRes layer
MAPW, MAPH = 32, 16
HOR = 48
EYE_ABOVE_FLOOR = 22    # H32: eye = floor + 22 (0.6875 cell)
SENTINEL = 255          # frame initialised to this; palette index 255 is reserved (clamped to 254 in textures)
MAX_STEPS = 48

# spec section 9 scenes: name -> (px, py, a)
SCENES = {
    "hall": (0x0F80, 0x0780, 512),
    "corridor": (0x0480, 0x0680, 0),
    "steps_down": (0x0A60, 0x0733, 40),
    "altar": (0x0F4D, 0x0766, 768),
}
ARG_NAMES = {
    "DRAW_PIECE": ["c", "ra", "count", "tex", "s", "u", "v_first", "dv"],
    "PLANE_ADD": ["c", "h", "tex", "a", "b"],
    "VOID": ["c", "a", "b"],
}


# ---------------------------------------------------------------- section 0: primitives
def smul_shr(a, b, s):
    """sign-magnitude multiply then shift (spec 0)."""
    r = (abs(a) * abs(b)) >> s
    return -r if ((a < 0) != (b < 0)) else r


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ROW(y_q8):
    """clamp((y_q8 + 127) >> 8, 0, 96) on a signed value (Python >> is a floor shift, as intended)."""
    return clamp((y_q8 + 127) >> 8, 0, 96)


def sat16(v):
    return clamp(v, -32768, 32767)


def sat_add16(a, b):
    return min(65535, a + b)


def R_of(d):
    """section 3: R(d) = min(65535, 2*RECIP[d]) with d clamped to 8..4095."""
    return min(65535, 2 * RECIP[clamp(d, 8, 4095)])


def y_of(h, d, eye):
    """section 3: y_q8 = 48*256 - (h - eye)*R(d), exact product, clamped to int16."""
    return sat16(HOR * 256 - (h - eye) * R_of(d))


def shade_of(d):
    return 0 if d < 384 else 1 if d < 768 else 2 if d < 1536 else 3


# ---------------------------------------------------------------- section 7: level
class Cell(object):
    __slots__ = ("floor", "ceil", "solid", "wtex", "ltex", "ftex", "ctex")

    def __init__(self, b0, b1, b2, b3):
        self.floor = struct.unpack("<b", bytes([b0]))[0]
        self.ceil = struct.unpack("<b", bytes([b1]))[0]
        self.solid = (b2 >> 7) & 1
        self.ltex = (b2 >> 4) & 7
        self.wtex = b2 & 15
        self.ftex = b3 & 15
        self.ctex = (b3 >> 4) & 15

    def __repr__(self):
        return "Cell(floor=%d ceil=%d solid=%d wtex=%d ltex=%d ftex=%d ctex=%d)" % (
            self.floor, self.ceil, self.solid, self.wtex, self.ltex, self.ftex, self.ctex)


OUTSIDE = Cell(0, 0, 0x80, 0)   # outside the map = solid stone (wtex 0)


class Level(object):
    def __init__(self, blob):
        blob = bytes(blob)
        assert len(blob) == MAPW * MAPH * 4, "level must be %d bytes, got %d" % (MAPW * MAPH * 4, len(blob))
        self.blob = blob
        self.cells = [Cell(*blob[i:i + 4]) for i in range(0, len(blob), 4)]

    @staticmethod
    def inside(mx, my):
        return 0 <= mx < MAPW and 0 <= my < MAPH

    def cell(self, mx, my):
        if not self.inside(mx, my):
            return OUTSIDE
        return self.cells[my * MAPW + mx]


def load_level(path=None):
    path = pathlib.Path(path) if path else ASSETS / "level0.bin"
    return Level(path.read_bytes())


# ---------------------------------------------------------------- section 6: textures
class WallTex(object):
    """16 textures x 4 shades x 4 pages x 256 bytes; offset = ((t*4+s)*4 + (u>>3))*256 + (u&7)*32 + v.
    Data is kept raw; the renderer clamps a texel of 255 (the frame sentinel) to 254 at paint time and counts it."""
    SIZE = 16 * 4 * 4 * 256

    def __init__(self, data):
        data = bytes(data)
        assert len(data) == self.SIZE, "walls.bin must be %d bytes, got %d" % (self.SIZE, len(data))
        self.count255 = data.count(255)
        self.data = data

    def texel(self, t, s, u, v):
        return self.data[((t * 4 + s) * 4 + (u >> 3)) * 256 + (u & 7) * 32 + v]


class FloorTex(object):
    """8 textures x 4 shades x 256 bytes; offset = (f*4+s)*256 + u*16 + v."""
    SIZE = 8 * 4 * 256

    def __init__(self, data):
        data = bytes(data)
        assert len(data) == self.SIZE, "floors.bin must be %d bytes, got %d" % (self.SIZE, len(data))
        self.count255 = data.count(255)
        self.data = data

    def texel(self, f, s, u, v):
        return self.data[(f * 4 + s) * 256 + u * 16 + v]


def shade_level(level, s):
    """spec 6: shade s reduces the palette level by 3*s, never below 1 unless the texel was level 0."""
    if level == 0:
        return 0
    return max(1, level - 3 * s)


def placeholder_walls():
    """Simple bricks, one tone per brick, mortar + bevel highlight, distinct per texture id (material and
    brick geometry vary with t). Exact spec-6 byte layout."""
    out = bytearray(WallTex.SIZE)
    for t in range(16):
        mat = 1 + (t % 15)
        bw = 16 if (t & 1) == 0 else 8
        bh = 8 if (t & 2) == 0 else 4
        for u in range(32):
            for v in range(32):
                brow = v // bh
                shift = (bw // 2) if (brow & 1) else 0
                bcol = ((u + shift) % 32) // bw
                mortar = (v % bh == bh - 1) or ((u + shift) % bw == bw - 1)
                bevel = (v % bh == 0) or ((u + shift) % bw == 0)
                if mortar:
                    lvl = 4
                elif bevel:
                    lvl = 13
                else:
                    lvl = 9 + ((brow * 7 + bcol * 3 + t) % 3)   # one tone per brick
                for s in range(4):
                    out[((t * 4 + s) * 4 + (u >> 3)) * 256 + (u & 7) * 32 + v] = mat * 16 + shade_level(lvl, s)
    return bytes(out)


def placeholder_floors():
    """Slabs (8x8 or 4x4) with mortar, distinct material per floor id. Exact spec-6 byte layout."""
    out = bytearray(FloorTex.SIZE)
    for f in range(8):
        mat = 1 + ((f * 2 + 3) % 15)
        sz = 8 if (f & 1) == 0 else 4
        for u in range(16):
            for v in range(16):
                su, sv = u // sz, v // sz
                mortar = (u % sz == sz - 1) or (v % sz == sz - 1)
                bevel = (u % sz == 0) or (v % sz == 0)
                if mortar:
                    lvl = 3
                elif bevel:
                    lvl = 12
                else:
                    lvl = 8 + ((su + sv * 2 + f) % 3)
                for s in range(4):
                    out[(f * 4 + s) * 256 + u * 16 + v] = mat * 16 + shade_level(lvl, s)
    return bytes(out)


def load_textures(log=print):
    """Use lane B's build/next/assets/{walls,floors}.bin when both exist with the right sizes; otherwise generate
    placeholders and write them to build/night/ref/placeholder_*.bin (never into build/next/assets/)."""
    wp, fp = ASSETS / "walls.bin", ASSETS / "floors.bin"
    ok = wp.exists() and fp.exists() and wp.stat().st_size == WallTex.SIZE and fp.stat().st_size == FloorTex.SIZE
    if ok:
        walls, floors = WallTex(wp.read_bytes()), FloorTex(fp.read_bytes())
        src = "lane B assets %s, %s" % (wp, fp)
    else:
        why = []
        for p, sz in ((wp, WallTex.SIZE), (fp, FloorTex.SIZE)):
            if not p.exists():
                why.append("%s missing" % p.name)
            elif p.stat().st_size != sz:
                why.append("%s has %d bytes, expected %d" % (p.name, p.stat().st_size, sz))
        REF.mkdir(parents=True, exist_ok=True)
        wb, fb = placeholder_walls(), placeholder_floors()
        (REF / "placeholder_walls.bin").write_bytes(wb)
        (REF / "placeholder_floors.bin").write_bytes(fb)
        walls, floors = WallTex(wb), FloorTex(fb)
        src = "placeholders (%s) written to %s/placeholder_{walls,floors}.bin" % ("; ".join(why), REF)
    log("textures: %s; texels equal to 255 (sentinel, clamped to 254 when painted): walls %d, floors %d" % (src, walls.count255, floors.count255))
    return walls, floors, src


# ---------------------------------------------------------------- sections 2-5: the renderer
def camera_info(level, px, py, a):
    mx, my = px >> 8, py >> 8
    eye = level.cell(mx, my).floor + EYE_ABOVE_FLOOR
    return dict(px=px, py=py, a=a, eye=eye, mx=mx, my=my, dirx=COS[a], diry=SIN[a], plx=-SIN[a], ply=COS[a])


class Renderer(object):
    def __init__(self, level, px, py, a, walls, floors, trace=None):
        self.level = level if isinstance(level, Level) else Level(level)
        self.walls = walls if isinstance(walls, WallTex) else WallTex(walls)
        self.floors = floors if isinstance(floors, FloorTex) else FloorTex(floors)
        assert 0 <= px < MAPW * 256 and 0 <= py < MAPH * 256, "player outside the map"
        assert 0 <= a < 1024
        self.px, self.py, self.a = px, py, a
        self.dirx, self.diry = COS[a], SIN[a]
        self.plx, self.ply = -SIN[a], COS[a]
        self.mx0, self.my0 = px >> 8, py >> 8
        self.eye = self.level.cell(self.mx0, self.my0).floor + EYE_ABOVE_FLOOR
        self.frame = bytearray([SENTINEL]) * (W * H)
        self.painted = bytearray(W * H)          # how many times each pixel was written (must end at 1)
        self.records = []
        self.zbuf = [None] * W
        self.trace = trace
        self._plane_rows = {}
        self.plane_far_rows = 0                  # plane rows painted 0 because d > 4095
        self.guard_vlast = 0                     # WALL pieces where the v_last > 8191 guard fired
        self.guard_vneg = 0                      # WALL pieces where v_first < 0 was clamped
        self.label = [None] * (W * H)            # debug: what each pixel is (kind, h/tex, u, v)
        self.clamped255 = 0                      # painted texels that were 255 (sentinel) and were clamped to 254

    # -- paint helpers (assert each pixel is written exactly once)
    def _put(self, c, row, value, label=None):
        i = row * W + c
        assert self.painted[i] == 0, "pixel (c=%d, row=%d) drawn twice" % (c, row)
        if value == SENTINEL:                    # palette index 255 is reserved as the sentinel
            value = SENTINEL - 1
            self.clamped255 += 1
        self.painted[i] = 1
        self.frame[i] = value
        self.label[i] = label

    # -- section 5: plane row parameters, cached per (h, row)
    def _plane_row(self, h, y):
        key = (h, y)
        if key in self._plane_rows:
            return self._plane_rows[key]
        dy = 2 * (y - HOR) + 1
        dh = self.eye - h
        assert (dh > 0 and dy > 0) or (dh < 0 and dy < 0), "plane row outside its half (h=%d y=%d eye=%d)" % (h, y, self.eye)
        d = (abs(dh) * RD[abs(dy)]) >> 6
        if d > 4095:
            res = None
        else:
            s = shade_of(d)
            DX = smul_shr(d, self.plx, 14)
            DY = smul_shr(d, self.ply, 10)
            XB = (self.px + smul_shr(d, self.dirx, 8) - smul_shr(DX, 127, 1)) & 0xFFFF
            YB = ((self.py << 4) + smul_shr(d, self.diry, 4) - smul_shr(DY, 127, 1)) & 0xFFFF
            res = (d, s, DX, DY, XB, YB)
        self._plane_rows[key] = res
        return res

    def PLANE_ADD(self, c, h, tex, a, b, kind, d):
        self.records.append({"op": "PLANE_ADD", "args": [c, h, tex, a, b], "kind": kind, "d": d})
        for y in range(a, b):
            p = self._plane_row(h, y)
            if p is None:
                self.plane_far_rows += 1
                self._put(c, y, 0)
                continue
            dd, s, DX, DY, XB, YB = p
            wx = (XB + c * DX) & 0xFFFF
            wy = (YB + c * DY) & 0xFFFF
            u = (wx >> 4) & 15
            v = (wy >> 8) & 15
            self._put(c, y, self.floors.texel(tex, s, u, v), ("plane", h, tex, s, u, v, dd))

    def DRAW_PIECE(self, c, ra, count, tex, s, u, v_first, dv, kind, d):
        self.records.append({"op": "DRAW_PIECE", "args": [c, ra, count, tex, s, u, v_first, dv], "kind": kind, "d": d})
        for i in range(count):
            v = (v_first + i * dv) >> 8
            assert 0 <= v <= 31, "texel row %d out of range (c=%d ra=%d count=%d v_first=%d dv=%d)" % (v, c, ra, count, v_first, dv)
            self._put(c, ra + i, self.walls.texel(tex, s, u, v), ("wall", kind, tex, s, u, v, d))

    def VOID(self, c, a, b):
        self.records.append({"op": "VOID", "args": [c, a, b], "kind": "void", "d": 4095})
        for y in range(a, b):
            self._put(c, y, 0)

    # -- section 4 WALL: split into 1-cell tiles aligned to world height 0
    def WALL(self, c, h_top, h_bot, tex, d, u, s, ytop, ybot, kind):
        t_top = h_top
        while t_top > h_bot:
            tile_base = ((t_top - 1) // 32) * 32
            t_bot = max(h_bot, tile_base)
            y_a = y_of(t_top, d, self.eye)
            y_b = y_of(t_bot, d, self.eye)
            ra = max(ROW(y_a), ytop)
            rb = min(ROW(y_b), ybot)
            if ra < rb:
                v_top = tile_base + 32 - t_top
                dv = d >> 1
                v_first = v_top * 256 + smul_shr((ra * 256 + 128) - y_a, dv, 8)
                count = rb - ra
                v_last = v_first + (count - 1) * dv
                if v_last > 8191:
                    v_first -= (v_last - 8191)
                    self.guard_vlast += 1
                if v_first < 0:
                    v_first = 0
                    self.guard_vneg += 1
                self.DRAW_PIECE(c, ra, count, tex, s, u, v_first, dv, kind, d)
            t_top = t_bot

    # -- section 4: the column walk
    def column(self, c):
        level, px, py, eye = self.level, self.px, self.py, self.eye
        cam_c = 2 * c + 1 - 128
        rx = self.dirx + smul_shr(self.plx, cam_c, 7)
        ry = self.diry + smul_shr(self.ply, cam_c, 7)
        ddx = RECIP[min(4095, abs(rx))]
        ddy = RECIP[min(4095, abs(ry))]
        sx = -1 if rx < 0 else 1
        sy = -1 if ry < 0 else 1
        fx, fy = px & 255, py & 255
        sdx = min(65535, (fx * ddx) >> 8) if rx < 0 else min(65535, ((256 - fx) * ddx) >> 8)
        sdy = min(65535, (fy * ddy) >> 8) if ry < 0 else min(65535, ((256 - fy) * ddy) >> 8)
        mx, my = self.mx0, self.my0
        ytop, ybot = 0, H
        cur = level.cell(mx, my)
        dprev = 8
        tr = {"c": c, "rx": rx, "ry": ry, "ddx": ddx, "ddy": ddy, "sdx0": sdx, "sdy0": sdy, "steps": []} if self.trace is not None else None
        stop = None
        for _step in range(MAX_STEPS):
            if sdx < sdy:
                d = sdx
                sdx = sat_add16(sdx, ddx)
                mx += sx
                side = 0
            else:
                d = sdy
                sdy = sat_add16(sdy, ddy)
                my += sy
                side = 1
            d = max(d, 8)
            if d > 4095 or not level.inside(mx, my):
                if tr is not None:
                    tr["steps"].append([d, side, mx, my, ytop, ybot, "exhaust"])
                break
            # 2. floor of cur
            ya = ROW(y_of(cur.floor, d, eye))
            yb = ROW(y_of(cur.floor, dprev, eye))
            a_, b_ = max(ya, ytop), min(yb, ybot)
            if a_ < b_:
                self.PLANE_ADD(c, cur.floor, cur.ftex, a_, b_, "floor", d)
            ybot = min(ybot, max(ytop, ya))
            # 3. ceiling of cur
            ya = ROW(y_of(cur.ceil, dprev, eye))
            yb = ROW(y_of(cur.ceil, d, eye))
            a_, b_ = max(ya, ytop), min(yb, ybot)
            if a_ < b_:
                self.PLANE_ADD(c, cur.ceil, cur.ctex, a_, b_, "ceil", d)
            ytop = max(ytop, min(ybot, yb))
            # 4. next cell, texture column, shade
            nxt = level.cell(mx, my)
            hit = (py + smul_shr(ry, d, 8)) if side == 0 else (px + smul_shr(rx, d, 8))
            u = (hit & 255) >> 3
            s = shade_of(d)
            if side == 1:
                s = min(3, s + 1)
            # 5. solid wall
            if nxt.solid:
                self.WALL(c, cur.ceil, cur.floor, nxt.wtex, d, u, s, ytop, ybot, "solid")
                self.zbuf[c] = d
                stop = "solid"
                if tr is not None:
                    tr["steps"].append([d, side, mx, my, ytop, ybot, "solid"])
                break
            # 6. riser
            if nxt.floor > cur.floor:
                self.WALL(c, nxt.floor, cur.floor, nxt.wtex, d, u, s, ytop, ybot, "riser")
                ybot = min(ybot, max(ytop, ROW(y_of(nxt.floor, d, eye))))
            # 7. lintel
            if nxt.ceil < cur.ceil:
                self.WALL(c, cur.ceil, nxt.ceil, nxt.ltex, d, u, s, ytop, ybot, "lintel")
                ytop = max(ytop, min(ybot, ROW(y_of(nxt.ceil, d, eye))))
            if tr is not None:
                tr["steps"].append([d, side, mx, my, ytop, ybot, "open"])
            # 8. closed?
            if ytop >= ybot:
                self.zbuf[c] = d
                stop = "closed"
                break
            # 9. continue
            cur = nxt
            dprev = d
        if stop is None:                       # EXHAUST: 48 steps, d > 4095 or left the map
            if ytop < ybot:
                self.VOID(c, ytop, ybot)
            self.zbuf[c] = 4095
            stop = "exhaust"
        if tr is not None:
            tr["stop"] = stop
            tr["zbuf"] = self.zbuf[c]
            self.trace.append(tr)

    def run(self):
        for c in range(W):
            self.column(c)
        # validation: every pixel exactly once, no sentinel left
        holes = [i for i in range(W * H) if self.painted[i] == 0]
        assert not holes, "%d pixels never drawn, first at c=%d row=%d" % (len(holes), holes[0] % W, holes[0] // W)
        assert self.frame.count(SENTINEL) == 0, "sentinel bytes left in the frame"
        assert all(z is not None for z in self.zbuf)
        return bytes(self.frame), self.records, self.zbuf


def render(level, px, py, a, walls, floors, trace=None):
    """-> (frame bytes, records list, zbuf list). `trace` (optional list) receives one dict per column."""
    return Renderer(level, px, py, a, walls, floors, trace).run()


# ---------------------------------------------------------------- output helpers
def load_palette_rgb():
    """256 RGB tuples: build/next/assets/palette.bin (9-bit Next format) if present, else RRRGGGBB from the index."""
    pp = ASSETS / "palette.bin"
    rgb = []
    if pp.exists() and pp.stat().st_size == 512:
        data = pp.read_bytes()
        for i in range(256):
            b0, b1 = data[2 * i], data[2 * i + 1]
            r3, g3 = b0 >> 5, (b0 >> 2) & 7
            b3 = ((b0 & 3) << 1) | (b1 & 1)
            rgb.append((r3 * 255 // 7, g3 * 255 // 7, b3 * 255 // 7))
        return rgb, str(pp)
    for i in range(256):
        rgb.append(((i >> 5) * 255 // 7, ((i >> 2) & 7) * 255 // 7, (i & 3) * 255 // 3))
    return rgb, "RRRGGGBB from the index (no palette.bin)"


def write_png(frame, path, scale=4):
    from PIL import Image
    rgb, _ = load_palette_rgb()
    img = Image.new("RGB", (W, H))
    img.putdata([rgb[b] for b in frame])
    img = img.resize((W * scale, H * scale), Image.NEAREST)
    img.save(str(path))


def column_runs(records, zbuf, c):
    """Row runs of column c from the records: list of (row0, row1, description)."""
    runs = []
    for r in records:
        if r["args"][0] != c:
            continue
        if r["op"] == "PLANE_ADD":
            _, h, tex, a, b = r["args"]
            runs.append((a, b, "%s plane h=%d ftex=%d d=%d" % (r["kind"], h, tex, r["d"])))
        elif r["op"] == "DRAW_PIECE":
            _, ra, count, tex, s, u, v_first, dv = r["args"]
            runs.append((ra, ra + count, "%s wall wtex=%d s=%d u=%d v_first=%d dv=%d d=%d" % (r["kind"], tex, s, u, v_first, dv, r["d"])))
        else:
            _, a, b = r["args"]
            runs.append((a, b, "VOID"))
    runs.sort()
    return runs


def frame_runs(frame, c):
    """Runs of identical palette bytes down column c: list of (row0, row1, index)."""
    out = []
    start, cur = 0, frame[c]
    for y in range(1, H + 1):
        v = frame[y * W + c] if y < H else None
        if v != cur:
            out.append((start, y, cur))
            start, cur = y, v
    return out


def scene_column_report(name, cam, records, zbuf, frame, c=W // 2):
    lines = ["== scene %s  (px=0x%04X py=0x%04X a=%d eye=%d cell=(%d,%d))  centre column c=%d  ZBUF=%d" % (
        name, cam["px"], cam["py"], cam["a"], cam["eye"], cam["mx"], cam["my"], c, zbuf[c])]
    lines.append("-- draw calls (rows [a,b) in column order after sorting by row):")
    kinds = set()
    for a, b, desc in column_runs(records, zbuf, c):
        lines.append("   rows %2d..%2d (%2d): %s" % (a, b - 1, b - a, desc))
        kinds.add(desc.split()[0])
    lines.append("-- palette-index runs of the frame column (material = index>>4, level = index&15):")
    for a, b, v in frame_runs(frame, c):
        lines.append("   rows %2d..%2d (%2d): index %3d = material %2d level %2d" % (a, b - 1, b - a, v, v >> 4, v & 15))
    lines.append("-- kinds present in c=%d: %s ; lintel: %s ; riser: %s" % (
        c, " ".join(sorted(kinds)), "yes" if "lintel" in kinds else "no", "yes" if "riser" in kinds else "no"))
    return lines, kinds


def render_scene(name, level, walls, floors, log=print, src=""):
    import hashlib
    px, py, a = SCENES[name]
    cam = camera_info(level, px, py, a)
    trace = []
    rend = Renderer(level, px, py, a, walls, floors, trace)
    frame, records, zbuf = rend.run()
    REF.mkdir(parents=True, exist_ok=True)
    (REF / ("%s.frame.bin" % name)).write_bytes(frame)
    write_png(frame, REF / ("%s.png" % name))
    cam_out = dict(cam)
    cam_out["textures"] = src
    cam_out["walls_sha1"] = hashlib.sha1(walls.data).hexdigest()
    cam_out["floors_sha1"] = hashlib.sha1(floors.data).hexdigest()
    cam_out["level_sha1"] = hashlib.sha1(rend.level.blob).hexdigest()
    (REF / ("%s.camera.json" % name)).write_text(json.dumps(cam_out, indent=1))
    with open(REF / ("%s.records.json" % name), "w") as f:
        # one record per line so lane D1 can diff the file against its own call list
        f.write('{\n"scene": %s,\n"camera": %s,\n"arg_names": %s,\n' % (json.dumps(name), json.dumps(cam), json.dumps(ARG_NAMES)))
        f.write('"note": "records are in call order (column 0..127; per column: floor plane, ceiling plane, wall pieces top-down per WALL call, spec section 4 order). Compare (op, args); kind/d are debug only.",\n')
        f.write('"records": [\n')
        f.write(",\n".join(json.dumps(r, separators=(",", ":")) for r in records))
        f.write('\n],\n"zbuf": %s\n}\n' % json.dumps(zbuf))
    (REF / ("%s.trace.json" % name)).write_text(json.dumps({"scene": name, "camera": cam,
        "step_fields": ["d", "side", "mx", "my", "ytop_after", "ybot_after", "state"], "columns": trace}, indent=0))
    nplane = sum(1 for r in records if r["op"] == "PLANE_ADD")
    npiece = sum(1 for r in records if r["op"] == "DRAW_PIECE")
    nvoid = sum(1 for r in records if r["op"] == "VOID")
    hist = {}
    for b in frame:
        hist[b] = hist.get(b, 0) + 1
    log("scene %-10s eye=%3d cell=(%2d,%2d): %4d records (%d PLANE_ADD, %d DRAW_PIECE, %d VOID), zbuf min %d max %d, "
        "%d distinct palette indices, %d void(0) pixels, 255 left: %d, texels 255 clamped to 254: %d, plane rows d>4095: %d, v_last guard: %d, v_first<0 clamps: %d" % (
            name, cam["eye"], cam["mx"], cam["my"], len(records), nplane, npiece, nvoid, min(zbuf), max(zbuf),
            len(hist), hist.get(0, 0), frame.count(255), rend.clamped255, rend.plane_far_rows, rend.guard_vlast, rend.guard_vneg))
    return cam, frame, records, zbuf


def main(argv):
    names = [n for n in argv[1:] if n in SCENES] or list(SCENES)
    level = load_level()
    walls, floors, src = load_textures()
    pal, palsrc = load_palette_rgb()
    print("palette for PNGs: %s" % palsrc)
    col_lines = ["Centre-column (c=64) evidence for the four spec-9 scenes, produced by tools/nx_ref.py",
                 "textures: %s" % src, "palette: %s" % palsrc, ""]
    summary = {}
    for name in names:
        cam, frame, records, zbuf = render_scene(name, level, walls, floors, src=src)
        lines, kinds = scene_column_report(name, cam, records, zbuf, frame)
        col_lines += lines + [""]
        summary[name] = kinds
    (REF / "columns.txt").write_text("\n".join(col_lines))
    print("wrote %s" % (REF / "columns.txt"))
    for name, kinds in summary.items():
        print("centre column c=64 of %-10s: lintel %-3s riser %-3s kinds: %s" % (
            name, "yes" if "lintel" in kinds else "no", "yes" if "riser" in kinds else "no", " ".join(sorted(kinds))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
