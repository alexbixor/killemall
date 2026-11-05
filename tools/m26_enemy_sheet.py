#!/usr/bin/env python3
"""m26_enemy_sheet.py - 2 Nov 'show me an image of all enemies'. One picture, three parts:
  (1) the source art of every enemy frame (assets/sprites/00..07, 16x24 / 16x12), 8x enlarged, in the P2E colour of its type;
  (2) the same frames as the 48K engine really draws them in the 3D window (real render, zombie / imp at 1.0 and 2.0 cells, each
      state: walk A, walk B, attack, dead), recoloured per cell with P2E;
  (3) the hand-drawn hi-res 32x48 zombie walk A (Track 1, 128K only), for scale.
Output build/m26_enemy_sheet.png."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, state, SYM, ROOT, scr_img, SCHEMES, attrs, pixel_cells, recolour

ART = [("imp walk A", "00_imp_walk_a.txt", 3), ("imp walk B", "01_imp_walk_b.txt", 3), ("imp attack", "02_imp_attack.txt", 3),
       ("imp dead", "03_imp_dead.txt", 7),
       ("zombie walk A", "04_zombie_walk_a.txt", 4), ("zombie walk B", "05_zombie_walk_b.txt", 4), ("zombie attack", "06_zombie_attack.txt", 4),
       ("zombie dead", "07_zombie_dead.txt", 7)]
RGB = {3: (255, 0, 255), 4: (0, 255, 0), 7: (255, 255, 255)}

def load_art(path):
    rows = [l.rstrip("\n") for l in (ROOT / "assets/sprites" / path).read_text().splitlines() if l and not l.startswith(";")]
    return rows

def art_img(rows, ink, z):
    h = len(rows); w = max(len(r) for r in rows)
    im = Image.new("RGB", (w * z, h * z), (0, 0, 0)); d = ImageDraw.Draw(im)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "#": d.rectangle((x * z, y * z, x * z + z - 1, y * z + z - 1), fill=ink)
            elif ch == "o": d.rectangle((x * z, y * z, x * z + z - 1, y * z + z - 1), fill=(40, 40, 40))
    return im

def main():
    title, sch = SCHEMES["P2E"]
    Z = 8; gap = 14
    # ---- part 1: source art
    arts = [(lab, art_img(load_art(f), RGB[ink], Z)) for lab, f, ink in ART]
    row_h = 24 * Z + 26
    p1_w = sum(a.size[0] for _, a in arts) + gap * (len(arts) + 1)
    # ---- part 2: engine renders
    m = fresh()
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    def ahead(dist, side=0.0):
        return {0: (sx + 0.5 + dist, sy + 0.5 + side), 64: (sx + 0.5 - side, sy + 0.5 + dist), 128: (sx + 0.5 - dist, sy + 0.5 - side),
                192: (sx + 0.5 + side, sy + 0.5 - dist)}.get(ang, (sx + 0.5 + dist, sy + 0.5 + side))
    # (label, [(type, dist, side, state, frames-bit)]) ; state 0 idle = walk A, 1 chase = walk A/B by frames bit 2, 2 attack, 3 dead
    scenes = [("zombie walk A, 1.0 cell", [(2, 1.0, 0.0, 0)], 0), ("zombie walk B, 1.0 cell", [(2, 1.0, 0.0, 1)], 4),
              ("zombie attack, 1.0 cell", [(2, 1.0, 0.0, 2)], 0), ("zombie dead, 1.0 cell", [(2, 1.0, 0.0, 3)], 0),
              ("imp walk A, 1.0 cell", [(1, 1.0, 0.0, 0)], 0), ("imp walk B, 1.0 cell", [(1, 1.0, 0.0, 1)], 4),
              ("imp attack, 1.0 cell", [(1, 1.0, 0.0, 2)], 0), ("imp dead, 1.0 cell", [(1, 1.0, 0.0, 3)], 0),
              ("zombie + imp at 2.0 cells", [(2, 2.0, -0.6, 1), (1, 2.0, 0.6, 1)], 0),
              ("zombie 1.5, imp 3.0 cells", [(2, 1.5, 0.4, 1), (1, 3.0, -0.5, 1)], 0)]
    crops = []
    for lab, th, frbit in scenes:
        m.set_memory_block(SYM["frames"], bytes([frbit, 0]))
        clear_things(m); call(m, "render", "hud_update"); bg = bytes(m.memory[16384:16384 + 6912])
        clear_things(m)
        for j, (typ, dist, side, st) in enumerate(th):
            x, y = ahead(dist, side); set_thing(m, j, typ, x, y); m.set_memory_block(SYM["things"] + 8 * j + 5, bytes([st]))
        call(m, "render", "hud_update"); scr = bytes(m.memory[16384:16384 + 6912]); zbuf, sprites = state(m)
        A, nsc, boxes = attrs(zbuf, sprites, sch, pixel_cells(scr, bg))
        crops.append((lab, scr_img(recolour(scr, A)).crop((31, 7, 225, 105)).resize((194 * 2, 98 * 2), Image.NEAREST),
                      [(s[3], s[4], s[0]) for s in sprites]))
    # ---- part 3: hi-res zombie
    hi_rows = [l.rstrip("\n") for l in (ROOT / "assets/sprites_hires/04_zombie_walk_a.txt").read_text().splitlines() if l and not l.startswith(";")]
    hi = art_img(hi_rows, RGB[4], 4)
    lo = art_img(load_art("04_zombie_walk_a.txt"), RGB[4], 8)
    # ---- compose
    W = max(p1_w, 5 * (194 * 2 + gap) + gap, 1400)
    H = 40 + row_h + 30 + 2 * (98 * 2 + 30) + 30 + 48 * 4 + 40
    sheet = Image.new("RGB", (W, H), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((gap, 6), "KILL'EM ALL - all enemies (2 Nov). Part 1: the source art, 16x24 pixels (dead = 16x12), 8x enlarged, in the colour each type gets in the game.", fill=(255, 255, 0))
    d.text((gap, 20), "'#' = ink pixel; dark grey = opaque black pixel (eye socket, mouth); black = see-through. The imp is magenta, the zombie green, corpses white.", fill=(255, 255, 0))
    x = gap; y = 40
    for lab, a in arts:
        d.text((x, y), lab, fill=(255, 255, 255)); sheet.paste(a, (x, y + 14)); x += a.size[0] + gap
    y += row_h
    d.text((gap, y), "Part 2: how the 48K engine really draws them in the 3D window (real engine frames, P2E colours per 8x8 cell). Each panel = one state at 1.0 cell; last two = pairs at distance.", fill=(255, 255, 0))
    y += 16
    for i, (lab, c, vis) in enumerate(crops):
        cx = gap + (i % 5) * (194 * 2 + gap); cy = y + (i // 5) * (98 * 2 + 30)
        d.text((cx, cy), lab, fill=(255, 255, 255)); d.text((cx, cy + 12), "vis (type,state,height px): %s" % vis, fill=(170, 170, 170))
        sheet.paste(c, (cx, cy + 26))
    y += 2 * (98 * 2 + 30) + 14
    d.text((gap, y), "Part 3: scale check - today's 16x24 zombie walk A (left, 8x) next to the hand-drawn 32x48 hi-res zombie walk A for the 128K Track 1 (right, 4x = same on-screen scale).", fill=(255, 255, 0))
    sheet.paste(lo, (gap, y + 18)); sheet.paste(hi, (gap + lo.size[0] + 40, y + 18))
    d.text((gap + lo.size[0] + 40 + hi.size[0] + 20, y + 18), "16x24 = 384 pixel positions; 32x48 = 1,536 (4x the detail).\nOnly the 128K edition gets the hi-res one (needs the route-2 renderer).", fill=(255, 255, 255))
    out = ROOT / "build/m26_enemy_sheet.png"; sheet.save(out); print("sheet", out, sheet.size)
    for lab, c, vis in crops: print(lab, vis)

if __name__ == "__main__":
    main()
