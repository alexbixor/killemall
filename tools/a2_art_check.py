#!/usr/bin/env python3
"""a2_art_check.py - lane A2 (6 Nov 2026): validate the four 32x48 hi-res zombie frames in assets/sprites_hires/ against
the 16x24 originals in assets/sprites/ and render a comparison sheet.
Checks per frame: exactly 48 rows x 32 columns, charset {#,o,.}, bottom alignment (ink on the last row of the box, like the
16x24 originals which all end on row 23), and the silhouette rule: the 32x48 frame downsampled 2:1 (any '#' in a 2x2 block
= ink) must overlap the original's ink by >= 85% IoU, computed inside the original's bounding box. Prints ink/black counts
and the exact numbers per frame; writes build/night/A2_sheet.png (hi-res frames at x6, originals at x12 beside each) and
build/night/A2_check.out (the table). Exit 0 = all pass. Loaders re-used from tools/m26_hires_art_check.py (not edited).
usage: .venv/bin/python tools/a2_art_check.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m26_hires_art_check import load_hires, to_img   # 32x48 loader (asserts 48x32 + charset) and the pixel -> PIL helper
from m25e_hires_proto import load                     # 16x24 loader (rows of 0/1)
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMES = ["04_zombie_walk_a", "05_zombie_walk_b", "06_zombie_attack", "07_zombie_dead"]
# 04 is the pre-A2 reference frame (M2.6 route 2 art, drawn before the silhouette rule existed and not owned by lane A2): its
# IoU is printed for information but does not gate the exit code; the rule is a hard gate for the three A2 frames.
GATED = {"05_zombie_walk_b", "06_zombie_attack", "07_zombie_dead"}
MIN_IOU = 85.0
W, H = 32, 48

def down2(hi, ink_only=True):
    """32x48 grid of 0/1/2 -> 16x24 silhouette: any '#' (or any opaque cell when ink_only=False) in the 2x2 block."""
    out = []
    for y in range(0, H, 2):
        row = []
        for x in range(0, W, 2):
            cells = (hi[y][x], hi[y][x + 1], hi[y + 1][x], hi[y + 1][x + 1])
            row.append(1 if any(c == 1 or (not ink_only and c) for c in cells) else 0)
        out.append(row)
    return out

def bbox(px):
    xs = [x for r in px for x, v in enumerate(r) if v]; ys = [y for y, r in enumerate(px) if any(r)]
    return min(xs), max(xs), min(ys), max(ys)

def iou(a, b, box=None):
    """IoU of two 16x24 0/1 grids; box = (x0, x1, y0, y1) inclusive restricts the count to that window."""
    x0, x1, y0, y1 = box if box else (0, 15, 0, 23)
    inter = union = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if a[y][x] and b[y][x]: inter += 1
            if a[y][x] or b[y][x]: union += 1
    return 100.0 * inter / union if union else 0.0, inter, union

def pad24(lo):
    """16xh original (bottom-aligned in the 24 box) -> 16x24."""
    return [[0] * 16 for _ in range(24 - len(lo))] + lo

def main():
    lines, fails = [], []
    def say(s): print(s); lines.append(s)
    say("A2 art check: %d frames, rule = 48x32, charset #o., bottom-aligned, IoU(down2 vs 16x24 original, in the original's bbox) >= %.0f%%" % (len(FRAMES), MIN_IOU))
    panels = []
    for name in FRAMES:
        try:
            hi = load_hires(name)
        except AssertionError as e:
            say("FAIL %s: format: %s" % (name, e)); fails.append(name); continue
        lo = pad24(load(name))
        ink = sum(r.count(1) for r in hi); blk = sum(r.count(2) for r in hi)
        hx0, hx1, hy0, hy1 = bbox(hi); lx0, lx1, ly0, ly1 = bbox(lo)
        d2 = down2(hi); d2o = down2(hi, ink_only=False)
        v, inter, union = iou(lo, d2, (lx0, lx1, ly0, ly1))
        v_full, _, _ = iou(lo, d2)
        v_opq, _, _ = iou(lo, d2o, (lx0, lx1, ly0, ly1))
        bottom_ok = any(hi[H - 1]) and (ly1 == 23)
        iou_ok = v >= MIN_IOU
        ok = bottom_ok and (iou_ok or name not in GATED)
        tag = "ok  " if ok else "FAIL"
        if name not in GATED and not iou_ok: tag = "info"
        say("%s %s: 32x48 ok, ink %d black %d, hi bbox x %d..%d y %d..%d (orig x %d..%d y %d..%d); IoU %.1f%% (%d/%d, orig bbox) "
            "| full box %.1f%% | with 'o' %.1f%% | bottom row inked: %s%s"
            % (tag, name, ink, blk, hx0, hx1, hy0, hy1, lx0, lx1, ly0, ly1, v, inter, union, v_full, v_opq, "yes" if any(hi[H - 1]) else "NO",
               "" if name in GATED else " [pre-A2 reference frame: IoU informational, not gated]"))
        if not ok: fails.append(name)
        # panel: original x12 (16x24 -> 192x288) | hi-res x6 (32x48 -> 192x288) | down2 silhouette diff x12
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
        d.text((4, 14), "16x24 original x12", fill=(200, 200, 200)); d.text((212, 14), "hi-res 32x48 x6", fill=(200, 200, 200))
        d.text((420, 14), "down2 vs orig IoU %.1f%% (red lost, blue added)" % v, fill=(200, 200, 200))
        panel.paste(a, (4, 28)); panel.paste(b, (212, 28)); panel.paste(c, (420, 28))
        panels.append(panel)
    if panels:
        sheet = Image.new("RGB", (panels[0].size[0], sum(p.size[1] for p in panels)), (60, 60, 60))
        y = 0
        for p in panels: sheet.paste(p, (0, y)); y += p.size[1]
        out = ROOT / "build/night/A2_sheet.png"; out.parent.mkdir(parents=True, exist_ok=True); sheet.save(out)
        say("sheet %s %dx%d" % (out, sheet.size[0], sheet.size[1]))
    say("RESULT: %d/%d frames pass" % (len(FRAMES) - len(fails), len(FRAMES)) + ("" if not fails else " - FAIL: " + ", ".join(fails)))
    (ROOT / "build/night/A2_check.out").write_text("\n".join(lines) + "\n")
    sys.exit(0 if not fails else 1)

if __name__ == "__main__":
    main()
