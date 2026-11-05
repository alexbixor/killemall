#!/usr/bin/env python3
"""m25e_sprite_mock2.py - engine-EXACT sprite sampling (Themis r1 B1 fix): for a thing at virtual height hv, enemies use
hd = enemy_h(hv) = hv - hv/4 + hv/16 (integer shifts, then & 254); nc = NCTAB[hv] = round(2*hv/9) clamped 1..28; STEPTAB[nc] =
round(SRC_W*256/nc); the source column of ray column i is (i*step) >> 8; ROWTAB[v] = clamp(trunc(top + v*VSTEP[hd/2]/256)),
VSTEP = round(hd*256/BOX_H), top = 48 + hv/2 - hd, v = 0..BOX_H; a source row v paints screen rows ROWTAB[v]..ROWTAB[v+1]-1
(forward fixed point, as sprites_e.asm builds it). Renders the walk_a zombie as 16x24 (today), 16x48 and 32x48 EPX sources at
hv 64 and 40 on a plain background -> build/m25e_sprite_mock2.png. Prints the sampled nc/hd and how many distinct source
columns / rows actually reach the screen (the honest 'resolution' number)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m25e_hires_proto import load, epx
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parents[1]

def enemy_h(hv):
    c = hv >> 2; a = hv - c; c >>= 2; return (a + c) & 254
def nctab(hv): return max(1, min(28, round(2 * hv / 9))) if hv else 0

def render(px, hv, enemy=True):
    """px = list of rows of 0/1/None (None transparent), bottom-aligned in a BOX_H box of SRC_W columns. -> dict (col,row)->0/1."""
    box_h, src_w = len(px), len(px[0])
    hd = enemy_h(hv) if enemy else hv & 254
    nc = nctab(hv)
    step = min(65535, round(src_w * 256 / nc))
    vstep = round(hd * 256 / box_h)
    top = ((48 + hv // 2) << 8) - (hd << 8)             # 8.8 signed
    rowtab = []
    acc = top
    for v in range(box_h + 1):
        r = acc >> 8
        r = 0 if acc < 0 else (96 if r > 96 else r)
        rowtab.append(r); acc += vstep
    out = {}
    for i in range(nc):
        u = ((i * step) >> 8) % src_w
        for v in range(box_h):
            val = px[v][u]
            if val is None: continue
            for r in range(rowtab[v], rowtab[v + 1]):
                for dx in range(3): out[(3 * i + dx, r)] = val
    used_u = len({((i * step) >> 8) % src_w for i in range(nc)})
    used_v = len({v for v in range(box_h) if rowtab[v + 1] > rowtab[v]})
    return out, nc, hd, used_u, used_v

def to_px(art, w, h):
    """load()/epx() rows of 0 transparent / 1 ink / 2 opaque black -> rows of 1/0/None, bottom-aligned into h rows x w cols."""
    rows = [[{1: 1, 2: 0}.get(v) for v in r] for r in art]
    pad = [[None] * w for _ in range(h - len(rows))]
    return pad + rows

def main():
    art = load("04_zombie_walk_a")
    src16 = to_px(art, 16, 24)
    e = epx(art)                                                   # 32 x 48 strings
    src32 = to_px(e, 32, 48)
    src16x48 = [[r[2 * x] if r[2 * x] is not None else r[2 * x + 1] for x in range(16)] for r in src32]   # left half-pixel wins
    cases = [("16x24 (today)", src16), ("16x48", src16x48), ("32x48 EPX", src32)]
    W, H, S = 96, 96, 3
    sheet = Image.new("RGB", (len(cases) * (W * S + 10), 2 * (H * S + 24)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for ci, (lab, px) in enumerate(cases):
        for ri, hv in enumerate((64, 40)):
            out, nc, hd, uu, uv = render(px, hv)
            img = Image.new("RGB", (W, H), (0, 0, 0))
            for (x, y), v in out.items():
                xx = x + (W - 3 * nc) // 2
                if 0 <= xx < W and 0 <= y < H: img.putpixel((xx, y), (255, 255, 255) if v else (0, 0, 0))
            for x in range(W): img.putpixel((x, 48), (60, 60, 60)) if img.getpixel((x, 48)) == (0, 0, 0) else None
            sheet.paste(img.resize((W * S, H * S), Image.NEAREST), (ci * (W * S + 10), ri * (H * S + 24) + 20))
            d.text((ci * (W * S + 10) + 2, ri * (H * S + 24) + 4), "%s hv %d: nc %d hd %d, src cols used %d/%d rows used %d/%d" % (lab, hv, nc, hd, uu, len(px[0]), uv, len(px)), fill=(255, 255, 255))
            print("%-14s hv %3d: nc %2d hd %2d  source columns reaching the screen %2d/%2d  source rows %2d/%2d" % (lab, hv, nc, hd, uu, len(px[0]), uv, len(px)))
    out = ROOT / "build/m25e_sprite_mock2.png"; sheet.save(out); print("sheet", out, sheet.size)

if __name__ == "__main__":
    main()
