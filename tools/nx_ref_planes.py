#!/usr/bin/env python3
"""nx_ref_planes.py - lane N1D: three-tier plane reference for the Spectrum Next edition B drawers
(docs/next_engine_spec_v0.2_flat.md section 4; the maths and textures are IMPORTED from tools/nx_ref.py, v0.1).

Given a records.json (v0.1 shape: the ordered DRAW_PIECE / PLANE_ADD / VOID call list of a scene), the camera
(camera.json, or the "camera" block inside records.json) and the assets (walls.bin, floors.bin), produce the frame
(12288 bytes, row-major 128x96 palette indices) for one plane tier:
  hi   - spec v0.1 section 5 exactly (every pixel its own texel) -> must equal build/night/ref/<scene>.frame.bin
  lo   - pixel (c, y) of a plane row uses wx, wy computed for column (c & 0xFE): pixels 2k, 2k+1 share a texel
  flat - no texture: a plane row is palette index material*16 + (12 - 3*s), material 6 (flag) for floors (eye above
         the plane), 7 (plaster) for ceilings, s = shade of the row depth (wall thresholds); rows with d > 4095 = 0.
Wall pieces and VOID runs are drawn by nx_ref.Renderer's own methods (unchanged in every tier).

Importable:
    render_tier(records, camera, walls, floors, tier) -> frame bytes
    tier_frame(scene, tier) -> frame bytes  (reads build/night/ref/<scene>.records.json + camera.json + assets)
CLI:
    .venv/bin/python tools/nx_ref_planes.py [--tier hi|lo|flat|all] [--records R.json] [--camera C.json] [scene ...]
    writes build/night/N1D_ref/<scene>.<tier>.frame.bin and .png and prints one line per scene/tier; for tier hi
    the line says whether the frame equals build/night/ref/<scene>.frame.bin byte for byte (the proof for the oracle).
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nx_ref  # noqa: E402  (the v0.1 reference: smul_shr, shade_of, Renderer._plane_row, WallTex, FloorTex)

ROOT = HERE.parent
ASSETS = ROOT / "build/next/assets"
REF = ROOT / "build/night/ref"
OUT = ROOT / "build/night/N1D_ref"
TIERS = ("hi", "lo", "flat")
FLAT_FLOOR_MATERIAL = 6     # manifest.json "flag"
FLAT_CEIL_MATERIAL = 7      # manifest.json "plaster"
W, H = nx_ref.W, nx_ref.H


class TierPainter(nx_ref.Renderer):
    """A nx_ref.Renderer that is fed records instead of walking a level. No level is needed: the camera block gives
    px, py, eye, dirx, diry, plx, ply. _plane_row (spec 5 row maths), DRAW_PIECE, VOID and _put are inherited."""

    def __init__(self, camera, walls, floors, tier):
        assert tier in TIERS, tier
        self.walls = walls if isinstance(walls, nx_ref.WallTex) else nx_ref.WallTex(walls)
        self.floors = floors if isinstance(floors, nx_ref.FloorTex) else nx_ref.FloorTex(floors)
        self.px, self.py, self.a = camera["px"], camera["py"], camera["a"]
        self.eye = camera["eye"]
        self.dirx, self.diry, self.plx, self.ply = camera["dirx"], camera["diry"], camera["plx"], camera["ply"]
        # the v0.1 camera block must agree with the tables (guards a mismatched camera.json)
        assert (self.dirx, self.diry) == (nx_ref.COS[self.a], nx_ref.SIN[self.a]), "camera dirx/diry do not match a"
        assert (self.plx, self.ply) == (-nx_ref.SIN[self.a], nx_ref.COS[self.a]), "camera plx/ply do not match a"
        self.tier = tier
        self.frame = bytearray([nx_ref.SENTINEL]) * (W * H)
        self.painted = bytearray(W * H)
        self.records = []
        self.label = [None] * (W * H)
        self._plane_rows = {}
        self.plane_far_rows = 0
        self.clamped255 = 0
        self.guard_vlast = self.guard_vneg = 0
        self.trace = None
        self.zbuf = [None] * W

    def PLANE_ADD(self, c, h, tex, a, b, kind=None, d=None):
        if self.tier == "hi":
            return nx_ref.Renderer.PLANE_ADD(self, c, h, tex, a, b, kind, d)
        self.records.append({"op": "PLANE_ADD", "args": [c, h, tex, a, b]})
        for y in range(a, b):
            p = self._plane_row(h, y)              # spec 5 maths from nx_ref (d, s, DX, DY, XB, YB) or None (far)
            if p is None:
                self.plane_far_rows += 1
                self._put(c, y, 0)
                continue
            dd, s, DX, DY, XB, YB = p
            if self.tier == "lo":
                ce = c & 0xFE                       # pixels 2k and 2k+1 share the texel of column 2k
                wx = (XB + ce * DX) & 0xFFFF
                wy = (YB + ce * DY) & 0xFFFF
                u = (wx >> 4) & 15
                v = (wy >> 8) & 15
                self._put(c, y, self.floors.texel(tex, s, u, v), ("plane-lo", h, tex, s, u, v, dd))
            else:                                   # flat
                material = FLAT_FLOOR_MATERIAL if self.eye - h > 0 else FLAT_CEIL_MATERIAL
                self._put(c, y, material * 16 + (12 - 3 * s), ("plane-flat", h, material, s, dd))

    def replay(self, records):
        for r in records:
            op, a = r["op"], r["args"]
            if op == "PLANE_ADD":
                self.PLANE_ADD(*a)
            elif op == "DRAW_PIECE":
                self.DRAW_PIECE(*(a + [r.get("kind"), r.get("d")]))
            elif op == "VOID":
                self.VOID(*a)
            else:
                raise ValueError(op)
        holes = [i for i in range(W * H) if self.painted[i] == 0]
        assert not holes, "%d pixels never drawn, first at c=%d row=%d" % (len(holes), holes[0] % W, holes[0] // W)
        assert self.frame.count(nx_ref.SENTINEL) == 0
        return bytes(self.frame)


def render_tier(records, camera, walls, floors, tier):
    """-> 12288 frame bytes for the tier ('hi', 'lo' or 'flat')."""
    return TierPainter(camera, walls, floors, tier).replay(records)


def load_assets():
    walls = (ASSETS / "walls.bin").read_bytes()
    floors = (ASSETS / "floors.bin").read_bytes()
    return nx_ref.WallTex(walls), nx_ref.FloorTex(floors)


def load_records(path):
    j = json.loads(pathlib.Path(path).read_text())
    return j["records"], j.get("camera")


def tier_frame(scene, tier, records_path=None, camera_path=None, assets=None):
    records_path = records_path or REF / ("%s.records.json" % scene)
    records, cam = load_records(records_path)
    camera_path = camera_path or REF / ("%s.camera.json" % scene)
    if pathlib.Path(camera_path).exists():
        cam = json.loads(pathlib.Path(camera_path).read_text())
    assert cam is not None, "no camera (camera.json missing and records.json has no camera block)"
    walls, floors = assets or load_assets()
    return render_tier(records, cam, walls, floors, tier)


def main(argv):
    tiers = list(TIERS)
    rec_path = cam_path = None
    scenes = []
    i = 0
    while i < len(argv):
        if argv[i] == "--tier":
            tiers = list(TIERS) if argv[i + 1] == "all" else [argv[i + 1]]; i += 2
        elif argv[i] == "--records":
            rec_path = argv[i + 1]; i += 2
        elif argv[i] == "--camera":
            cam_path = argv[i + 1]; i += 2
        else:
            scenes.append(argv[i]); i += 1
    scenes = scenes or ["hall", "corridor", "steps_down", "altar"]
    OUT.mkdir(parents=True, exist_ok=True)
    assets = load_assets()
    ok_all = True
    for sc in scenes:
        for tier in tiers:
            frame = tier_frame(sc, tier, rec_path, cam_path, assets)
            (OUT / ("%s.%s.frame.bin" % (sc, tier))).write_bytes(frame)
            nx_ref.write_png(frame, OUT / ("%s.%s.png" % (sc, tier)))
            line = "%-10s %-4s: %d bytes, %d distinct palette indices" % (sc, tier, len(frame), len(set(frame)))
            refp = REF / ("%s.frame.bin" % sc)
            if refp.exists():
                ref = refp.read_bytes()
                ndiff = sum(1 for x, y in zip(frame, ref) if x != y)
                if tier == "hi":
                    line += " ; differing bytes vs %s = %d -> %s" % (refp.relative_to(ROOT), ndiff, "IDENTICAL" if ndiff == 0 else "MISMATCH")
                    ok_all &= ndiff == 0
                else:
                    line += " ; differing bytes vs the hi frame = %d (expected > 0: the tier changes plane pixels)" % ndiff
            print(line)
    print("RESULT: hi tier %s the v0.1 reference frames (%s)" % ("EQUALS" if ok_all else "DIFFERS FROM", " ".join(scenes)))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
