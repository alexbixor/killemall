#!/usr/bin/env python3
"""nx_ref_with.py - render the four spec-9 reference scenes with an ALTERNATIVE texture set (lane T, texture pass 2).

Uses tools/nx_ref.py's importable render(level, px, py, a, walls, floors) unchanged (nx_ref's own CLI and defaults are not
touched) and the cameras recorded in build/night/ref/<scene>.camera.json (read-only), so the geometry is exactly the
reference's; only the texture bytes differ.

usage: nx_ref_with.py --walls W.bin --floors F.bin --palette P.bin --out-dir DIR [--quad QUAD.png] [--level level0.bin] [scene ...]
Writes per scene into DIR: <scene>.frame.bin (12288 bytes), <scene>.png (4x, palette applied), <scene>.camera.json (the camera
used + sha1 of the texture blobs), plus DIR/summary.txt; --quad writes a 2x2 contact sheet (hall, corridor / steps_down, altar).
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nx_ref  # noqa: E402

ROOT = HERE.parent
REF = ROOT / "build/night/ref"
ORDER = ["hall", "corridor", "steps_down", "altar"]


def palette_rgb(palb):
    rgb = []
    for i in range(256):
        b0, b1 = palb[2 * i], palb[2 * i + 1]
        r3, g3, b3 = b0 >> 5, (b0 >> 2) & 7, ((b0 & 3) << 1) | (b1 & 1)
        rgb.append((r3 * 255 // 7, g3 * 255 // 7, b3 * 255 // 7))
    return rgb


def frame_image(frame, rgb, scale=4):
    from PIL import Image
    img = Image.new("RGB", (nx_ref.W, nx_ref.H))
    img.putdata([rgb[b] for b in frame])
    return img.resize((nx_ref.W * scale, nx_ref.H * scale), Image.NEAREST)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--walls", required=True)
    ap.add_argument("--floors", required=True)
    ap.add_argument("--palette", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--quad", default=None, help="write a 2x2 contact sheet PNG (hall, corridor / steps_down, altar)")
    ap.add_argument("--level", default=str(nx_ref.ASSETS / "level0.bin"))
    ap.add_argument("--cameras", default=str(REF), help="directory with <scene>.camera.json (default build/night/ref)")
    ap.add_argument("scenes", nargs="*", default=[])
    a = ap.parse_args(argv[1:])
    scenes = [s for s in a.scenes if s in nx_ref.SCENES] or ORDER
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    walls_b = pathlib.Path(a.walls).read_bytes()
    floors_b = pathlib.Path(a.floors).read_bytes()
    palb = pathlib.Path(a.palette).read_bytes()
    assert len(palb) == 512, "palette.bin must be 512 bytes"
    walls, floors = nx_ref.WallTex(walls_b), nx_ref.FloorTex(floors_b)
    level = nx_ref.Level(pathlib.Path(a.level).read_bytes())
    rgb = palette_rgb(palb)
    lines = ["nx_ref_with.py: scenes rendered with walls %s (sha1 %s), floors %s (sha1 %s), palette %s (md5 %s), level %s" % (
        a.walls, hashlib.sha1(walls_b).hexdigest(), a.floors, hashlib.sha1(floors_b).hexdigest(), a.palette,
        hashlib.md5(palb).hexdigest(), a.level)]
    images = {}
    for name in scenes:
        cam_path = pathlib.Path(a.cameras) / ("%s.camera.json" % name)
        cam = json.loads(cam_path.read_text())
        px, py, ang = cam["px"], cam["py"], cam["a"]
        assert (px, py, ang) == nx_ref.SCENES[name], "camera file %s disagrees with nx_ref.SCENES" % cam_path
        frame, records, zbuf = nx_ref.render(level, px, py, ang, walls, floors)
        (out / ("%s.frame.bin" % name)).write_bytes(frame)
        img = frame_image(frame, rgb)
        img.save(str(out / ("%s.png" % name)))
        images[name] = img
        cam_out = {k: cam[k] for k in ("px", "py", "a", "eye", "mx", "my", "dirx", "diry", "plx", "ply") if k in cam}
        cam_out["camera_source"] = str(cam_path)
        cam_out["textures"] = "%s, %s" % (a.walls, a.floors)
        cam_out["walls_sha1"] = hashlib.sha1(walls_b).hexdigest()
        cam_out["floors_sha1"] = hashlib.sha1(floors_b).hexdigest()
        cam_out["palette_md5"] = hashlib.md5(palb).hexdigest()
        cam_out["level_sha1"] = hashlib.sha1(level.blob).hexdigest()
        (out / ("%s.camera.json" % name)).write_text(json.dumps(cam_out, indent=1))
        hist = {}
        for b in frame:
            hist[b] = hist.get(b, 0) + 1
        ref_frame = REF / ("%s.frame.bin" % name)
        diff = ""
        if ref_frame.exists():
            rf = ref_frame.read_bytes()
            diff = ", %d of 12288 bytes differ from %s" % (sum(1 for x, y in zip(rf, frame) if x != y), ref_frame)
        line = "scene %-10s px=0x%04X py=0x%04X a=%d: %d records, frame md5 %s, %d distinct palette indices%s" % (
            name, px, py, ang, len(records), hashlib.md5(frame).hexdigest(), len(hist), diff)
        print(line)
        lines.append(line)
    if a.quad:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.load_default(size=14)
        w, h = nx_ref.W * 4, nx_ref.H * 4
        gap, top = 8, 20
        sheet = Image.new("RGB", (2 * w + 3 * gap, 2 * (h + top) + 3 * gap), (72, 72, 72))
        d = ImageDraw.Draw(sheet)
        for i, name in enumerate(ORDER):
            if name not in images:
                continue
            x = gap + (i % 2) * (w + gap)
            y = gap + (i // 2) * (h + top + gap)
            d.text((x + 2, y + 2), name, fill=(255, 255, 255), font=font)
            sheet.paste(images[name], (x, y + top))
        sheet.save(a.quad)
        lines.append("contact sheet %s (%dx%d)" % (a.quad, sheet.size[0], sheet.size[1]))
        print(lines[-1])
    (out / "summary.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
