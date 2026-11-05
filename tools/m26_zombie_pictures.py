#!/usr/bin/env python3
"""m26_zombie_pictures.py - side-by-side pictures for the principal (1 Nov, "Show me pictures"):
LEFT  = today's real engine output (Python Z80 core, 48K image, level 1, zombie planted D cells ahead), 3D window crop.
RIGHT = route 2 mock on the SAME real background: the zombie redrawn from the 32x48 EPX art in 2-px columns with the engine's
        own geometry (hv, c0, nc, hd, top from the vis entry; 48-row ROWTAB; per-pixel zbuf occlusion). Not engine output.
Distances 1.0 / 1.5 / 2.5 cells. Output build/m26_zombie_compare.png (3x) + build/m26_zombie_closeup.png (6x crops)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, clear_things, set_thing
from run48 import scr_to_png
from m25e_hires_proto import load, epx
from m25e_sprite_mock2 import enemy_h, nctab, to_px
from m26_hires_art_check import load_hires
from PIL import Image, ImageDraw

def s8(v): return v - 256 if v > 127 else v

def route2_pixels(px, hv, c0, nc, zbuf):
    """32x48 source (rows of 1 ink / 0 black / None), 2-px columns over the same 3*nc px width -> {(x,y): 0/1} window coords."""
    hd = enemy_h(hv)
    width = 3 * nc
    nc2 = width // 2
    step = round(32 * 256 / nc2)
    vstep = round(hd * 256 / 48)
    acc = ((48 + hv // 2) << 8) - (hd << 8)
    rowtab = []
    for v in range(49):
        r = acc >> 8
        rowtab.append(0 if acc < 0 else (96 if r > 96 else r)); acc += vstep
    x0 = 3 * c0
    out = {}
    for i in range(nc2):
        u = ((i * step) >> 8) % 32
        for dx in (0, 1):
            x = x0 + 2 * i + dx
            if not 0 <= x < 192: continue
            ray = x // 3
            z = zbuf[ray]
            if z > hv: continue                      # wall nearer in this ray (engine rule: zbuf <= hv visible)
            for v in range(48):
                val = px[v][u]
                if val is None: continue
                for r in range(rowtab[v], rowtab[v + 1]): out[(x, r)] = val
    used_u = len({((i * step) >> 8) % 32 for i in range(nc2)})
    used_v = len({v for v in range(48) if rowtab[v + 1] > rowtab[v]})
    return out, nc2, hd, used_u, used_v

def main():
    m = machine()
    lvl = ROOT / "src/48k/gen/level48.bin"
    data = lvl.read_bytes(); assert len(data) == 1081 and data[0] == 1
    m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
    call(m, "cls", "hud_init", "init_game")
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    art32 = to_px(epx(load("04_zombie_walk_a")), 32, 48)
    art32h = to_px(load_hires("04_zombie_walk_a"), 32, 48)
    tmp = ROOT / "build/m26_tmp.png"
    rows = []
    for dist in (1.0, 1.5, 2.5):
        dx, dy = {0: (dist, 0), 64: (0, dist), 128: (-dist, 0), 192: (0, -dist)}.get(ang, (dist, 0))
        clear_things(m); call(m, "render", "hud_update")
        # scr_to_png writes a 3x (768x576) image: bring both stills back to 1 px = 1 Spectrum pixel before cropping
        scr_to_png(bytes(m.memory[16384:16384 + 6912]), str(tmp)); bg = Image.open(tmp).convert("RGB").resize((256, 192), Image.NEAREST)
        clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy); call(m, "render", "hud_update")
        scr_to_png(bytes(m.memory[16384:16384 + 6912]), str(tmp)); today = Image.open(tmp).convert("RGB").resize((256, 192), Image.NEAREST)
        assert today.size == (256, 192) and bg.size == (256, 192)
        vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6]); nvis = m.memory[SYM["nvis"]]
        zbuf = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
        assert nvis == 1, nvis
        hv, c0, nc = vis[0], s8(vis[1]), vis[2]
        pix, nc2, hd, uu, uv = route2_pixels(art32, hv, c0, nc, zbuf)
        mock = bg.copy(); p = mock.load()
        for (x, y), v in pix.items():
            p[32 + x, 8 + y] = (215, 215, 215) if v else (0, 0, 0)      # same palette white as run48.scr_to_png
        pixh = route2_pixels(art32h, hv, c0, nc, zbuf)[0]
        mockh = bg.copy(); ph = mockh.load()
        for (x, y), v in pixh.items():
            ph[32 + x, 8 + y] = (215, 215, 215) if v else (0, 0, 0)
        today_cols = len({((i * min(65535, round(16 * 256 / nc))) >> 8) % 16 for i in range(nc)})
        lab = "%.1f cells: hv %d, drawn %d px tall, %d px wide | today %d cols x 24 rows (%d src cols used) | route 2 %d cols x 48 rows (%d src cols used)" % (
            dist, hv, hd, 3 * nc, nc, today_cols, nc2, uu)
        print(lab)
        rows.append((dist, today.crop((31, 7, 225, 105)), mock.crop((31, 7, 225, 105)), lab, hv, hd, c0, nc, mockh.crop((31, 7, 225, 105))))
    # sheet 1: full window crops at 3x
    S = 3; W, H = 194 * S, 98 * S
    sheet = Image.new("RGB", (3 * W + 24, len(rows) * (H + 30) + 26), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((4, 4), "LEFT: today, real engine (48K image).  MIDDLE: route 2 mock, 16x24 art EPX-upscaled.  RIGHT: route 2 mock, hand-drawn 32x48 art. Same scene.", fill=(255, 255, 0))
    for i, (dist, a, b, lab, hv, hd, c0, nc, c) in enumerate(rows):
        y = 26 + i * (H + 30)
        d.text((4, y), "%.1f cells - TODAY (3-px cols, 16x24 art)" % dist, fill=(255, 255, 255))
        d.text((W + 16, y), "%.1f cells - ROUTE 2 + EPX upscale (mock)" % dist, fill=(255, 255, 255))
        d.text((2 * W + 28, y), "%.1f cells - ROUTE 2 + hand-drawn 32x48 (mock)" % dist, fill=(255, 255, 255))
        sheet.paste(a.resize((W, H), Image.NEAREST), (0, y + 14)); sheet.paste(b.resize((W, H), Image.NEAREST), (W + 12, y + 14))
        sheet.paste(c.resize((W, H), Image.NEAREST), (2 * W + 24, y + 14))
    out = ROOT / "build/m26_zombie_compare.png"; sheet.save(out); print("sheet", out, sheet.size)
    # sheet 2: close-ups of the zombie box at 6x (1.5 and 2.5 cells)
    Z = 6; tiles = []
    for dist, a, b, lab, hv, hd, c0, nc, c in rows:
        top = 48 + hv // 2 - hd
        x0 = max(0, 1 + 3 * c0 - 6); x1 = min(194, 1 + 3 * c0 + 3 * nc + 6)
        y0 = max(0, 1 + top - 4); y1 = min(98, 1 + 48 + hv // 2 + 4)
        tiles.append((dist, a.crop((x0, y0, x1, y1)), b.crop((x0, y0, x1, y1)), c.crop((x0, y0, x1, y1))))
    tw = max(t[1].size[0] for t in tiles) * Z; th = max(t[1].size[1] for t in tiles) * Z
    close = Image.new("RGB", (3 * tw + 24, len(tiles) * (th + 20) + 20), (40, 40, 40)); d = ImageDraw.Draw(close)
    d.text((4, 4), "close-ups, 6x: today (left) | route 2 + EPX upscale (middle) | route 2 + hand-drawn 32x48 (right)", fill=(255, 255, 0))
    for i, (dist, a, b, c) in enumerate(tiles):
        y = 20 + i * (th + 20)
        d.text((4, y), "%.1f cells today" % dist, fill=(255, 255, 255)); d.text((tw + 16, y), "%.1f cells route 2 + EPX" % dist, fill=(255, 255, 255))
        d.text((2 * tw + 28, y), "%.1f cells route 2 + hand-drawn" % dist, fill=(255, 255, 255))
        close.paste(a.resize((a.size[0] * Z, a.size[1] * Z), Image.NEAREST), (0, y + 12))
        close.paste(b.resize((b.size[0] * Z, b.size[1] * Z), Image.NEAREST), (tw + 12, y + 12))
        close.paste(c.resize((c.size[0] * Z, c.size[1] * Z), Image.NEAREST), (2 * tw + 24, y + 12))
    out2 = ROOT / "build/m26_zombie_closeup.png"; close.save(out2); print("closeup", out2, close.size)
    tmp.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
