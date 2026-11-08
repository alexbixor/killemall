#!/usr/bin/env python3
"""nx_ref_flat.py - exact integer reference renderer for the Spectrum Next edition B ("flat" engine),
docs/next_engine_spec_v0.2_flat.md sections 1-3 and 5 (lane N1).  tools/nx_ref.py (v0.1, READ-ONLY) is imported for
the shared primitives (smul_shr, ROW, sat16, R_of, shade_of, texture classes, plane-row maths and pixel bookkeeping).

Importable:
    render_flat(level_bytes, px, py, a, walls, floors, ceil=32, ftex=0, ctex=1, tier="hi")
        -> (frame 12288 bytes (row-major 128x96 palette indices), records (v0.1 records.json shape), zbuf[128])
        level_bytes = one mapc level (8-byte header + 1024 cells [+ things]) or a whole `mapc.py next` file
        (leading level-count byte): the first level is used.  tier: "hi" (spec v0.1 section 5), "lo", "flat".
    to_v01_cells(level, ceil, ftex, ctex) -> 4096-byte v0.1 cell blob (32x32) for the cross-check with nx_ref.py
    map_size(w, h): context manager that sets nx_ref.MAPW/MAPH and restores the defaults (nx_ref itself is untouched)
    SCENES: the four scenes of build/night/N1_BRIEF.md (+ corridor_mid, see N1_QUESTIONS.md)

CLI:  .venv/bin/python tools/nx_ref_flat.py [scene ...]
    renders every scene into build/night/ref_flat/<scene>.{frame.bin,png,records.json,camera.json}, then runs the
    v0.1 cross-check (build/night/N1_xcheck.out) and the nx_ref.py regression (build/night/N1_ref_regress.out).
"""
import contextlib
import hashlib
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nx_ref  # noqa: E402  (READ-ONLY module of lane R; only its module globals MAPW/MAPH are set temporarily)
from nx_ref import smul_shr, ROW, sat16, sat_add16, R_of, shade_of, WallTex, FloorTex, SENTINEL, W, H, HOR  # noqa: E402
from nx_tables import SIN, COS, RD, RECIP  # noqa: E402

ROOT = HERE.parent
ASSETS = ROOT / "build/next/assets"
NIGHT = ROOT / "build/night"
REF_FLAT = NIGHT / "ref_flat"
REF_V01 = NIGHT / "ref"
LEVEL_TXT = ROOT / "assets/levels/01_entry.txt"
LEVEL_BIN = NIGHT / "N1_level01.bin"

MAPW = MAPH = 32
EYE = 22                       # spec v0.2 section 2: eye = 22 (H32) in every walkable cell
MAX_STEPS = 64                 # spec v0.2 section 3 step 1
# spec v0.2 section 1: wall texture id per cell code (index 0 = floor, never looked up)
WALLMAP = [0, 0, 1, 3, 8, 2, 13, 14, 4, 5, 6, 0, 7]
# spec v0.2 section 4 "planes-flat": material of the floor (manifest "flag" 6) and ceiling ("plaster" 7)
FLAT_MAT_FLOOR, FLAT_MAT_CEIL = 6, 7

# scenes of build/night/N1_BRIEF.md: name -> (px, py, a) ; corridor_mid is this lane's extra (N1_QUESTIONS.md Q1)
SCENES = {
    "start": (0x0380, 0x0780, 0),
    "door": (0x0C80, 0x0380, 0),
    "corridor": (0x0180, 0x0D80, 0),
    "oblique": (0x0A80, 0x0D80, 340),
    "corridor_mid": (0x0F80, 0x0D80, 0),
}
SCENE_NOTES = {
    "start": "the header pose: sx=3, sy=7, east",
    "door": "the 'D' of map row y=3 is at x=15; seen from 2.5 cells",
    "corridor": "map row y=13 is open from x=1 to x=30: the end wall is 29.5 cells away, so the centre columns exhaust (d > 4095 -> VOID(c, 0, 96), spec v0.2 section 3 step 1)",
    "oblique": "the E-wall row y=15 at 1.5 cells, about 30 degrees off the normal",
    "corridor_mid": "extra scene (not in the brief): same corridor from x=15.5 so the end wall is 15.5 cells away and no column exhausts; proves the long-view path against the v0.1 oracle on every column",
}
ARG_NAMES = nx_ref.ARG_NAMES


@contextlib.contextmanager
def map_size(w, h):
    """Temporarily parametrise nx_ref's map size (its Level/Renderer read the module globals)."""
    old = (nx_ref.MAPW, nx_ref.MAPH)
    nx_ref.MAPW, nx_ref.MAPH = w, h
    try:
        yield
    finally:
        nx_ref.MAPW, nx_ref.MAPH = old


# ---------------------------------------------------------------- section 1: the mapc level
class FlatLevel(object):
    """One `tools/mapc.py next` level: 'K', 1, w, h, sx, sy, start_angle, n_things, 1024 cells, things."""

    def __init__(self, blob):
        blob = bytes(blob)
        if blob[:1] != b"K" and len(blob) > 1 and blob[1:2] == b"K":
            blob = blob[1:]                      # whole mapc file: leading level count byte
        assert blob[0:2] == b"K\x01", "not a mapc level (magic %r)" % blob[:2]
        self.w, self.h, self.sx, self.sy, self.start_angle, self.n_things = struct.unpack_from("<BBBBBB", blob, 2)
        assert (self.w, self.h) == (MAPW, MAPH), "level must be 32x32, got %dx%d" % (self.w, self.h)
        self.cells = blob[8:8 + MAPW * MAPH]
        assert len(self.cells) == MAPW * MAPH
        self.things = [tuple(blob[8 + MAPW * MAPH + 3 * i: 8 + MAPW * MAPH + 3 * i + 3]) for i in range(self.n_things)]
        self.blob = blob[:8 + MAPW * MAPH + 3 * self.n_things]

    @staticmethod
    def inside(mx, my):
        return 0 <= mx < MAPW and 0 <= my < MAPH

    def code(self, mx, my):
        """cell code, or None outside the map (= solid stone, spec v0.2 section 1)."""
        if not self.inside(mx, my):
            return None
        return self.cells[my * MAPW + mx]

    def camera(self):
        """spec v0.2 section 1: px = sx*256 + 128, py = sy*256 + 128, a = start_angle * 4."""
        return self.sx * 256 + 128, self.sy * 256 + 128, (self.start_angle * 4) & 1023


def to_v01_cells(level, ceil=32, ftex=0, ctex=1):
    """spec v0.2 section 3 'Equivalence': the mapc level as v0.1 4-byte cells (32x32): walkable = (0, CEIL, 0,
    ftex | ctex << 4); solid = (0, 0, 0x80 | WALLMAP[code], 0) (v0.1 section 7: solid cells have 0 heights/textures)."""
    level = level if isinstance(level, FlatLevel) else FlatLevel(level)
    out = bytearray(MAPW * MAPH * 4)
    for i, code in enumerate(level.cells):
        if code == 0:
            out[4 * i:4 * i + 4] = bytes([0, ceil & 255, 0, (ftex & 15) | ((ctex & 15) << 4)])
        else:
            out[4 * i:4 * i + 4] = bytes([0, 0, 0x80 | WALLMAP[code], 0])
    return bytes(out)


# ---------------------------------------------------------------- sections 2, 3, 5: the renderer
class FlatRenderer(nx_ref.Renderer):
    """Edition B column walk (spec v0.2 section 3) on top of nx_ref.Renderer's pixel rules (v0.1 sections 3-5).
    The base class is initialised with the converted v0.1 level (32x32), which makes eye = 0 + 22 = 22 and gives
    _plane_row / PLANE_ADD / DRAW_PIECE / VOID / WALL / run() unchanged."""

    def __init__(self, level, px, py, a, walls, floors, ceil=32, ftex=0, ctex=1, tier="hi"):
        self.flat = level if isinstance(level, FlatLevel) else FlatLevel(level)
        assert ceil in (32, 64), "CEIL must be 32 or 64 (spec v0.2 section 1)"
        assert tier in ("hi", "lo", "flat")
        self.ceil, self.ftex, self.ctex, self.tier = ceil, ftex, ctex, tier
        with map_size(MAPW, MAPH):
            nx_ref.Renderer.__init__(self, to_v01_cells(self.flat, ceil, ftex, ctex), px, py, a, walls, floors)
        assert self.eye == EYE
        assert self.flat.code(self.mx0, self.my0) == 0, "camera cell (%d,%d) is not walkable" % (self.mx0, self.my0)
        self.exhausted = []                       # columns that ended with VOID(c, 0, 96) (left the map / 64 steps)
        self.clamped_far = []                     # lane N4: columns whose wall was hit at d > 4095 and drawn with d = 4095

    # spec v0.2 section 4: plane tiers "lo" and "flat" (the "hi" tier is the inherited v0.1 section 5 code)
    def PLANE_ADD(self, c, h, tex, a, b, kind, d):
        if self.tier == "hi":
            return nx_ref.Renderer.PLANE_ADD(self, c, h, tex, a, b, kind, d)
        self.records.append({"op": "PLANE_ADD", "args": [c, h, tex, a, b], "kind": kind, "d": d})
        for y in range(a, b):
            p = self._plane_row(h, y)
            if p is None:
                self.plane_far_rows += 1
                self._put(c, y, 0)
                continue
            dd, s, DX, DY, XB, YB = p
            if self.tier == "flat":
                mat = FLAT_MAT_FLOOR if h == 0 else FLAT_MAT_CEIL
                self._put(c, y, mat * 16 + (12 - 3 * s), ("plane-flat", h, tex, s, dd))
                continue
            cc = c & 0xFE                           # "lo": pixels 2k and 2k+1 share the texel of column 2k
            wx = (XB + cc * DX) & 0xFFFF
            wy = (YB + cc * DY) & 0xFFFF
            u = (wx >> 4) & 15
            v = (wy >> 8) & 15
            self._put(c, y, self.floors.texel(tex, s, u, v), ("plane-lo", h, tex, s, u, v, dd))

    def column(self, c):
        """spec v0.2 section 3: DDA until a solid cell (<= 64 steps), then wall + the two plane spans."""
        flat, px, py = self.flat, self.px, self.py
        # section 2 (v0.1): ray of column c
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
        hit_code = None
        for _step in range(MAX_STEPS):
            # step 1: advance to the next boundary (v0.1 section 4 step 1)
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
            if not flat.inside(mx, my):
                break                               # EXHAUST (left the map; cannot happen on a closed mapc level)
            code = flat.code(mx, my)
            if code != 0:
                hit_code = code
                break
        # lane N4 (8 Nov 2026, build/night/N4_result.out item 1): a wall farther than 4095 (16 cells) used to EXHAUST the column
        # into VOID(c, 0, 96) = a full-height black bar (the hardware "vertical black bars" bug); the wall is real, so d is
        # clamped to 4095 (R, shade 3, ZBUF 4095) and the column is drawn like any other. Only leaving the map / 64 steps void.
        if hit_code is not None and d > 4095:
            d = 4095
            self.clamped_far.append(c)
        if hit_code is None:                        # EXHAUST: 64 steps, d > 4095 or left the map
            self.VOID(c, 0, H)
            self.zbuf[c] = 4095
            self.exhausted.append(c)
            return
        # step 2: texture column and shade (v0.1 section 4 item 4)
        hit = (py + smul_shr(ry, d, 8)) if side == 0 else (px + smul_shr(rx, d, 8))
        u = (hit & 255) >> 3
        s = shade_of(d)
        if side == 1:
            s = min(3, s + 1)
        tex = WALLMAP[hit_code]
        # step 4 first in record order: floor plane, ceiling plane, then step 3: the wall pieces top-down
        a_ = ROW(nx_ref.y_of(0, d, EYE))
        if a_ < H:
            self.PLANE_ADD(c, 0, self.ftex, a_, H, "floor", d)
        b_ = ROW(nx_ref.y_of(self.ceil, d, EYE))
        if b_ > 0:
            self.PLANE_ADD(c, self.ceil, self.ctex, 0, b_, "ceil", d)
        self.WALL(c, self.ceil, 0, tex, d, u, s, 0, H, "solid")
        # step 5
        self.zbuf[c] = d


def render_flat(level_bytes, px, py, a, walls, floors, ceil=32, ftex=0, ctex=1, tier="hi", horizon=48):
    """-> (frame bytes, records, zbuf). See the module docstring.
    lane N5 (8 Nov 2026): `horizon` = the y-shear horizon row (horizon_row of main_b_vars.inc, default 48 = the v0.1 constant):
    nx_ref's y_of (y_q8 = HOR*256 - (h - eye)*R) and _plane_row (dy = 2*(y - HOR) + 1) read the module global HOR, which is
    set for the duration of this render only (nx_ref itself untouched, like map_size)."""
    old = nx_ref.HOR
    nx_ref.HOR = horizon
    try:
        r = FlatRenderer(level_bytes, px, py, a, walls, floors, ceil, ftex, ctex, tier)
        return r.run()
    finally:
        nx_ref.HOR = old


def camera_info(level, px, py, a, ceil=32, ftex=0, ctex=1):
    level = level if isinstance(level, FlatLevel) else FlatLevel(level)
    return dict(px=px, py=py, a=a, eye=EYE, mx=px >> 8, my=py >> 8, dirx=COS[a], diry=SIN[a], plx=-SIN[a], ply=COS[a],
                ceil=ceil, ftex=ftex, ctex=ctex)


# ---------------------------------------------------------------- the v0.1 cross-check (spec v0.2 section 3 "Equivalence")
def coalesce_planes(records):
    """Merge chained PLANE_ADD spans of one column with the same (h, tex) and touching rows (what lane S's coalescer does
    in walk.asm); other records are kept in order.  Within a column the v0.1 walker emits floor, ceiling, floor, ...
    so the merged list is re-ordered per column as: floor span, ceiling span, pieces/void (edition B's record order)."""
    out = []
    cols = {}
    for r in records:
        cols.setdefault(r["args"][0], []).append(r)
    for c in sorted(cols):
        planes, rest = {}, []
        for r in cols[c]:
            if r["op"] == "PLANE_ADD":
                _, h, tex, a, b = r["args"]
                key = (h, tex)
                if key in planes:
                    pa, pb = planes[key]
                    assert a == pb or b == pa, "non-touching spans in column %d: %s then [%d,%d)" % (c, planes[key], a, b)
                    planes[key] = (min(pa, a), max(pb, b))
                else:
                    planes[key] = (a, b)
            else:
                rest.append({"op": r["op"], "args": list(r["args"])})
        # edition B order: floor (h == 0) first, then the ceiling (h > 0), then the wall pieces / void
        for (h, tex), (a, b) in sorted(planes.items(), key=lambda kv: (kv[0][0] != 0, kv[0][0])):
            out.append({"op": "PLANE_ADD", "args": [c, h, tex, a, b]})
        out.extend(rest)
    return out


def xcheck_scene(level, px, py, a, walls, floors, ceil, ftex, ctex, log):
    """Render the scene with both renderers; -> dict with the comparison numbers."""
    fr = FlatRenderer(level, px, py, a, walls, floors, ceil, ftex, ctex)
    frame_b, rec_b, zbuf_b = fr.run()
    with map_size(MAPW, MAPH):
        v01 = nx_ref.Renderer(to_v01_cells(level, ceil, ftex, ctex), px, py, a, walls, floors)
        frame_a, rec_a, zbuf_a = v01.run()
    # lane N4: columns hit at d > 4095 are drawn at the far clamp by edition B but VOIDed by the read-only v0.1 renderer: excluded like
    # the exhausted ones (the N4 live oracle nx_test_angles.py proves those columns against render_flat directly)
    exhausted = set(fr.exhausted) | set(fr.clamped_far)
    diff_px = [i for i in range(W * H) if frame_a[i] != frame_b[i]]
    diff_cols = sorted({i % W for i in diff_px})
    diff_px_live = [i for i in diff_px if (i % W) not in exhausted]
    zdiff = [c for c in range(W) if zbuf_a[c] != zbuf_b[c]]
    zdiff_live = [c for c in zdiff if c not in exhausted]
    co_a = [r for r in coalesce_planes(rec_a) if r["args"][0] not in exhausted]
    co_b = [{"op": r["op"], "args": list(r["args"])} for r in rec_b if r["args"][0] not in exhausted]
    rec_mism = sum(1 for i in range(max(len(co_a), len(co_b))) if (co_a[i] if i < len(co_a) else None) != (co_b[i] if i < len(co_b) else None))
    res = dict(px=px, py=py, a=a, exhausted=sorted(exhausted), n_exhausted=len(exhausted), diff_pixels=len(diff_px),
               diff_pixels_live=len(diff_px_live), diff_columns=diff_cols, zbuf_diff=zdiff, zbuf_diff_live=zdiff_live,
               records_b=len(rec_b), records_v01=len(rec_a), records_v01_coalesced_live=len(co_a), records_b_live=len(co_b),
               records_mismatch_live=rec_mism, frame_sha1_b=hashlib.sha1(frame_b).hexdigest(), frame_sha1_v01=hashlib.sha1(frame_a).hexdigest())
    return res, frame_b


def _textures(log):
    wp, fp = ASSETS / "walls.bin", ASSETS / "floors.bin"
    walls, floors = WallTex(wp.read_bytes()), FloorTex(fp.read_bytes())
    log("textures: %s (sha1 %s), %s (sha1 %s)" % (wp.relative_to(ROOT), hashlib.sha1(walls.data).hexdigest(),
                                                  fp.relative_to(ROOT), hashlib.sha1(floors.data).hexdigest()))
    return walls, floors


def _level(log):
    if not LEVEL_BIN.exists():
        import subprocess
        subprocess.check_call([sys.executable, str(HERE / "mapc.py"), "next", str(LEVEL_BIN), str(LEVEL_TXT)])
    blob = LEVEL_BIN.read_bytes()
    lv = FlatLevel(blob)
    log("level: %s (%d bytes, sha1 %s) -> header sx=%d sy=%d start_angle=%d n_things=%d; cells sha1 %s; camera from header px=%04X py=%04X a=%d"
        % (LEVEL_BIN.relative_to(ROOT), len(blob), hashlib.sha1(blob).hexdigest(), lv.sx, lv.sy, lv.start_angle, lv.n_things,
           hashlib.sha1(lv.cells).hexdigest(), lv.camera()[0], lv.camera()[1], lv.camera()[2]))
    return lv


def write_scene(name, lv, walls, floors, ceil, ftex, ctex, log):
    px, py, a = SCENES[name]
    cam = camera_info(lv, px, py, a, ceil, ftex, ctex)
    rend = FlatRenderer(lv, px, py, a, walls, floors, ceil, ftex, ctex)
    frame, records, zbuf = rend.run()
    REF_FLAT.mkdir(parents=True, exist_ok=True)
    (REF_FLAT / ("%s.frame.bin" % name)).write_bytes(frame)
    nx_ref.write_png(frame, REF_FLAT / ("%s.png" % name))
    cam_out = dict(cam)
    cam_out["note"] = SCENE_NOTES.get(name, "")
    cam_out["scene"] = name
    cam_out["level"] = str(LEVEL_BIN.relative_to(ROOT))
    cam_out["level_sha1"] = hashlib.sha1(lv.blob).hexdigest()
    cam_out["walls_sha1"] = hashlib.sha1(walls.data).hexdigest()
    cam_out["floors_sha1"] = hashlib.sha1(floors.data).hexdigest()
    cam_out["exhausted_columns"] = rend.exhausted
    cam_out["frame_sha1"] = hashlib.sha1(frame).hexdigest()
    (REF_FLAT / ("%s.camera.json" % name)).write_text(json.dumps(cam_out, indent=1))
    with open(REF_FLAT / ("%s.records.json" % name), "w") as f:
        f.write('{\n"scene": %s,\n"camera": %s,\n"arg_names": %s,\n' % (json.dumps(name), json.dumps(cam), json.dumps(ARG_NAMES)))
        f.write('"note": "spec v0.2 section 3 records in call order (column 0..127; per column: floor plane, ceiling plane, wall pieces top-down; VOID(c,0,96) on exhaust). Compare (op, args); kind/d are debug only.",\n')
        f.write('"records": [\n')
        f.write(",\n".join(json.dumps(r, separators=(",", ":")) for r in records))
        f.write('\n],\n"zbuf": %s\n}\n' % json.dumps(zbuf))
    nplane = sum(1 for r in records if r["op"] == "PLANE_ADD")
    npiece = sum(1 for r in records if r["op"] == "DRAW_PIECE")
    nvoid = sum(1 for r in records if r["op"] == "VOID")
    hist = {}
    for b in frame:
        hist[b] = hist.get(b, 0) + 1
    log("scene %-12s px=%04X py=%04X a=%4d cell=(%2d,%2d): %4d records (%d PLANE_ADD, %d DRAW_PIECE, %d VOID), zbuf min %d max %d, "
        "%d exhausted columns, %d distinct palette indices, %d void(0) pixels, plane rows d>4095: %d, v_last guard: %d, v_first<0: %d, frame sha1 %s"
        % (name, px, py, a, cam["mx"], cam["my"], len(records), nplane, npiece, nvoid, min(zbuf), max(zbuf), len(rend.exhausted),
           len(hist), hist.get(0, 0), rend.plane_far_rows, rend.guard_vlast, rend.guard_vneg, hashlib.sha1(frame).hexdigest()))
    return frame, records, zbuf


def regress_v01(walls, floors, log):
    """Prove nx_ref.py (defaults restored) still reproduces build/night/ref/<scene>.frame.bin byte for byte."""
    assert (nx_ref.MAPW, nx_ref.MAPH) == (32, 16), "nx_ref defaults not restored: %r" % ((nx_ref.MAPW, nx_ref.MAPH),)
    level = nx_ref.load_level()
    ok_all = True
    for name, (px, py, a) in nx_ref.SCENES.items():
        frame, records, zbuf = nx_ref.render(level, px, py, a, walls, floors)
        ref = (REF_V01 / ("%s.frame.bin" % name)).read_bytes()
        same = frame == ref
        ok_all &= same
        refrec = json.loads((REF_V01 / ("%s.records.json" % name)).read_text())
        rec_same = [(r["op"], r["args"]) for r in records] == [(r["op"], r["args"]) for r in refrec["records"]] and zbuf == refrec["zbuf"]
        ok_all &= rec_same
        log("v0.1 regression %-10s: frame %d bytes, %d differ from %s -> %s; records %d vs %d, zbuf -> %s" % (
            name, len(frame), sum(1 for i in range(len(ref)) if frame[i] != ref[i]), (REF_V01 / ("%s.frame.bin" % name)).relative_to(ROOT),
            "IDENTICAL" if same else "DIFFERENT", len(records), len(refrec["records"]), "IDENTICAL" if rec_same else "DIFFERENT"))
    return ok_all


def main(argv):
    names = [n for n in argv[1:] if n in SCENES] or list(SCENES)
    NIGHT.mkdir(parents=True, exist_ok=True)
    ceil, ftex, ctex = 32, 0, 1          # level 01 has no #ceil/#ftex/#ctex header lines: the spec defaults
    lines = []

    def log(s):
        print(s)
        lines.append(s)
    walls, floors = _textures(log)
    lv = _level(log)
    log("CEIL=%d FTEX=%d CTEX=%d (spec v0.2 section 1 defaults; 01_entry.txt has no #ceil/#ftex/#ctex lines)" % (ceil, ftex, ctex))
    for name in names:
        write_scene(name, lv, walls, floors, ceil, ftex, ctex, log)
    (NIGHT / "N1_ref_flat.out").write_text("\n".join(lines) + "\n")
    # ---- cross-check against the v0.1 renderer on the converted level
    xl = ["v0.1 cross-check (spec v0.2 section 3 'Equivalence'): nx_ref.Renderer with MAPW=MAPH=32 on to_v01_cells(level) vs render_flat",
          "textures: %s" % lines[0], "level: %s" % lines[1], "CEIL=%d FTEX=%d CTEX=%d" % (ceil, ftex, ctex),
          "columns that exhaust (d > 4095) are excluded from the live comparison: v0.2 says VOID(c, 0, 96) there, v0.1 EXHAUST voids only [ytop, ybot) after its chained spans (see N1_QUESTIONS.md Q1)"]
    all_ok, any_exh = True, False
    for name in names:
        px, py, a = SCENES[name]
        res, _ = xcheck_scene(lv, px, py, a, walls, floors, ceil, ftex, ctex, log)
        live_ok = res["diff_pixels_live"] == 0 and not res["zbuf_diff_live"] and res["records_mismatch_live"] == 0
        full_ok = res["diff_pixels"] == 0 and not res["zbuf_diff"]
        all_ok &= live_ok
        any_exh |= res["n_exhausted"] > 0
        xl.append("%-12s px=%04X py=%04X a=%4d: frame v0.1 sha1 %s, edition B sha1 %s -> %s; differing pixels %d (in %d columns), "
                  "of which in non-exhausted columns %d; ZBUF differs in %d columns (%d non-exhausted); exhausted columns %d %s; "
                  "records: edition B %d, v0.1 %d -> coalesced non-exhausted %d vs %d, mismatching positions %d -> %s"
                  % (name, px, py, a, res["frame_sha1_v01"], res["frame_sha1_b"], "IDENTICAL" if full_ok else "DIFFERENT",
                     res["diff_pixels"], len(res["diff_columns"]), res["diff_pixels_live"], len(res["zbuf_diff"]), len(res["zbuf_diff_live"]),
                     res["n_exhausted"], ("(c=%d..%d)" % (res["exhausted"][0], res["exhausted"][-1])) if res["exhausted"] else "",
                     res["records_b"], res["records_v01"], res["records_v01_coalesced_live"], res["records_b_live"], res["records_mismatch_live"],
                     "PASS" if live_ok else "FAIL"))
    xl.append("XCHECK RESULT: %s on %d scenes (%s)" % ("PASS" if all_ok else "FAIL", len(names), ", ".join(names)))
    (NIGHT / "N1_xcheck.out").write_text("\n".join(xl) + "\n")
    print("\n".join(xl[5:]))
    # ---- regression of nx_ref.py (defaults) against build/night/ref/*.frame.bin
    rl = []
    ok = regress_v01(walls, floors, lambda s: (print(s), rl.append(s)))
    rl.append("REGRESSION RESULT: %s (nx_ref.MAPW=%d nx_ref.MAPH=%d after this module ran)" % ("PASS" if ok else "FAIL", nx_ref.MAPW, nx_ref.MAPH))
    print(rl[-1])
    (NIGHT / "N1_ref_regress.out").write_text("\n".join(rl) + "\n")
    return 0 if (all_ok and ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
