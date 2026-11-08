#!/usr/bin/env python3
"""a3_art_check.py - lane A3 (7 Nov 2026): validate the 16 hand-drawn 32x48 hi-res frames of enemy types 3..6 (shotgunner,
floater, brute, boss) in assets/sprites_hires/ against the 16xN originals in assets/sprites_m4/ and render a comparison sheet.
Checks per frame: exactly 48 rows x 32 columns, charset {#,o,.}, bottom alignment (the frame's last opaque row must be the
original's last opaque row x2 (+0/+1): the floater's originals end 2 rows above the floor because it floats, the dead frames are
8..14 rows high and sit on the floor), and the silhouette rule: the 32x48 frame downsampled 2:1 (any opaque cell - '#' ink or
'o' black - in a 2x2 block = silhouette) must overlap the original's opaque silhouette ('#' or 'o') by >= 85% IoU, computed inside
the original's bounding box. The M4 originals carry large 'o' cores (gun tube, floater mouth, boss visor), so the silhouette is the
OPAQUE shape on both sides; the ink-only IoU (A2's reading: original '#'+'o' vs hi-res '#') is printed for information.
Writes build/night/A3_sheet.png (originals at x12, hi-res at x6, down2 diff at x12) and build/night/A3_check.out. Exit 0 = all pass.
Loaders re-used from tools/m26_hires_art_check.py and the geometry helpers from tools/a2_art_check.py (neither edited).
usage: .venv/bin/python tools/a3_art_check.py [name ...]   (default: all 16 frames)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m26_hires_art_check import load_hires, to_img       # 32x48 loader (asserts 48x32 + charset) and the pixel -> PIL helper
from a2_art_check import bbox, iou                        # bbox of a 0/1/2 grid, IoU inside a window
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMES = ["18_shotgunner_walk_a", "19_shotgunner_walk_b", "20_shotgunner_attack", "21_shotgunner_dead",
          "22_floater_a", "23_floater_b", "24_floater_attack", "25_floater_dead",
          "26_brute_walk_a", "27_brute_walk_b", "28_brute_attack", "29_brute_dead",
          "30_boss_walk_a", "31_boss_walk_b", "32_boss_attack", "34_boss_dead"]
MIN_IOU = 85.0
W, H = 32, 48

def load_m4(name):
    """16xN original of assets/sprites_m4 (bottom-aligned in the 24 box) -> 16x24 grid of 0 transparent / 1 ink / 2 opaque black."""
    rows = [l for l in (ROOT / "assets/sprites_m4" / (name + ".txt")).read_text().splitlines() if l and not l.startswith(";")]
    assert all(len(r) == 16 for r in rows) and len(rows) <= 24, name
    lo = [[{"#": 1, "o": 2}.get(ch, 0) for ch in r] for r in rows]
    return [[0] * 16 for _ in range(24 - len(lo))] + lo

def down2(hi, opaque=True):
    """32x48 grid of 0/1/2 -> 16x24: any opaque cell (or any '#' when opaque=False) in the 2x2 block."""
    out = []
    for y in range(0, H, 2):
        row = []
        for x in range(0, W, 2):
            cells = (hi[y][x], hi[y][x + 1], hi[y + 1][x], hi[y + 1][x + 1])
            row.append(1 if any((c != 0) if opaque else (c == 1) for c in cells) else 0)
        out.append(row)
    return out

def main():
    names = sys.argv[1:] or FRAMES
    lines, fails = [], []
    def say(s): print(s); lines.append(s)
    say("A3 art check: %d frames, rule = 48x32, charset #o., bottom-aligned to the original's last row x2, IoU(down2 opaque vs 16xN original opaque, in the original's bbox) >= %.0f%%" % (len(names), MIN_IOU))
    panels = []
    for name in names:
        lo = load_m4(name)
        lx0, lx1, ly0, ly1 = bbox(lo)
        try:
            hi = load_hires(name)
        except (AssertionError, FileNotFoundError) as e:
            say("FAIL %s: format: %s" % (name, e)); fails.append(name); continue
        ink = sum(r.count(1) for r in hi); blk = sum(r.count(2) for r in hi)
        hx0, hx1, hy0, hy1 = bbox(hi)
        d2 = down2(hi); d2i = down2(hi, opaque=False)
        v, inter, union = iou(lo, d2, (lx0, lx1, ly0, ly1))
        v_full, _, _ = iou(lo, d2)
        v_ink, _, _ = iou(lo, d2i, (lx0, lx1, ly0, ly1))
        bottom_ok = hy1 in (2 * ly1, 2 * ly1 + 1)
        iou_ok = v >= MIN_IOU
        ok = bottom_ok and iou_ok
        say("%s %s: 32x48 ok, ink %d black %d, hi bbox x %d..%d y %d..%d (orig x %d..%d y %d..%d, rows %d); IoU %.1f%% (%d/%d, orig bbox) "
            "| full box %.1f%% | ink-only %.1f%% | bottom: last row %d vs orig %d x2 -> %s"
            % ("ok  " if ok else "FAIL", name, ink, blk, hx0, hx1, hy0, hy1, lx0, lx1, ly0, ly1, ly1 - ly0 + 1,
               v, inter, union, v_full, v_ink, hy1, ly1, "ok" if bottom_ok else "WRONG"))
        if not ok: fails.append(name)
        a = to_img(lo, 12); b = to_img(hi, 6)
        diff = Image.new("RGB", (16, 24), (40, 40, 40)); p = diff.load()
        for y in range(24):
            for x in range(16):
                if lo[y][x] and d2[y][x]: p[x, y] = (215, 215, 215)      # agree
                elif lo[y][x]: p[x, y] = (255, 60, 60)                   # original only (lost)
                elif d2[y][x]: p[x, y] = (60, 120, 255)                  # hi-res only (added)
        c = diff.resize((192, 288), Image.NEAREST)
        panel = Image.new("RGB", (192 * 3 + 40, 288 + 40), (60, 60, 60)); d = ImageDraw.Draw(panel)
        d.text((4, 2), name, fill=(255, 255, 0))
        d.text((4, 14), "16xN original x12", fill=(200, 200, 200)); d.text((212, 14), "hi-res 32x48 x6", fill=(200, 200, 200))
        d.text((420, 14), "down2 vs orig IoU %.1f%% (red lost, blue added)" % v, fill=(200, 200, 200))
        panel.paste(a, (4, 28)); panel.paste(b, (212, 28)); panel.paste(c, (420, 28))
        panels.append(panel)
    if panels:
        cols = 2 if len(panels) > 4 else 1
        rows = (len(panels) + cols - 1) // cols
        pw, ph = panels[0].size
        sheet = Image.new("RGB", (pw * cols, ph * rows), (60, 60, 60))
        for i, p in enumerate(panels): sheet.paste(p, ((i % cols) * pw, (i // cols) * ph))
        out = ROOT / ("build/night/A3_sheet.png" if not sys.argv[1:] else "build/night/A3_sheet_part.png"); out.parent.mkdir(parents=True, exist_ok=True); sheet.save(out)
        say("sheet %s %dx%d" % (out, sheet.size[0], sheet.size[1]))
    say("RESULT: %d/%d frames pass" % (len(names) - len(fails), len(names)) + ("" if not fails else " - FAIL: " + ", ".join(fails)))
    if not sys.argv[1:]: (ROOT / "build/night/A3_check.out").write_text("\n".join(lines) + "\n")
    sys.exit(0 if not fails else 1)

if __name__ == "__main__":
    main()
