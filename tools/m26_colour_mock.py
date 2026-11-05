#!/usr/bin/env python3
"""m26_colour_mock.py - Track 2 colour mock from REAL engine state (2 Nov 2026, "Yes do both tracks" / "videos too").
Runs the shipped 48K image in the cycle-exact Python Z80 core, renders level 1 with a zombie, then recolours the 3D window
per 8x8 attribute cell exactly as a Z80 attribute writer would (from zbuf[64] = wall height per ray column and the vis list
= sprite boxes): wall cells by distance band, ceiling/floor cells by their own ink, sprite cells "ink wins" (option 2) or not.
  stills  -> build/m26_colour_sheet_1.0.png, build/m26_colour_sheet_1.5.png (6 schemes each), build/m26_colour_full.png
  video   -> build/m26_colour_walk.mp4: scripted walk, every rendered frame, duration from T-states (real Spectrum speed),
             top = today (one ink), bottom = scheme P3 recoloured per frame.
usage: m26_colour_mock.py stills | video [scheme]"""
import sys, pathlib, subprocess, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np
from PIL import Image, ImageDraw
from test_game_sprites import machine, call, clear_things, set_thing, SYM, ROOT
from m25e_sprite_mock2 import enemy_h

PAL = np.array([(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215),
                (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)], np.uint8)
_ys = np.arange(192); _base = ((_ys & 0xC0) << 5) | ((_ys & 7) << 8) | ((_ys & 0x38) << 2)
_IDX = _base[:, None] + np.arange(32)[None, :]; _AIDX = (_ys // 8)[:, None] * 32 + np.arange(32)[None, :]

def scr_img(scr):
    s = np.frombuffer(bytes(scr), np.uint8)
    bits = np.unpackbits(s[:6144][_IDX], axis=1)
    a = np.repeat(s[6144:][_AIDX], 8, axis=1)
    col = np.where(bits == 1, a & 7, (a >> 3) & 7) + ((a >> 6) & 1) * 8
    return Image.fromarray(PAL[col])

def s8(v): return v - 256 if v > 127 else v

ENEMY_INK = {0: 0x43, 1: 0x43, 7: 0x43, 2: 0x44, 3: 0x44, 4: 0x44, 5: 0x44, 6: 0x44}   # THSPR: types 0,1,7 imp (magenta), 2..6 zombie (green)
# 2 Nov 11:4x (video with items): one table byte per item type too. 16 health BRIGHT red, 17 ammo BRIGHT yellow, 18 red key BRIGHT red,
# 19 blue key BRIGHT blue, 20 shield BRIGHT cyan; barrel / lamp (21..23) stay white (None).
ITEM_INK = {16: 0x42, 17: 0x46, 18: 0x42, 19: 0x41, 20: 0x45}
def enemy_attr(typ, st):
    """thing type/state -> attribute. Corpses (state 3) write nothing = stay the window ink (rule agreed 10:45Z: nearer sprite wins,
    corpses do not fight for cells). Items use ITEM_INK; unknown types -> None (keep window ink)."""
    if typ >= 16: return ITEM_INK.get(typ)
    if typ not in ENEMY_INK: return None
    return None if st == 3 else ENEMY_INK[typ]

# attr byte = bright<<6 | paper<<3 | ink
SCHEMES = {
    "P1": ("TODAY: one ink, white on black (shipped M2.5 E1)",
           dict(wall={"near": 0x07, "mid": 0x07, "far": 0x07}, ceil=0x07, floor=0x07, sprite=None)),
    "P2": ("TONAL: near walls BRIGHT white, rest white; floor/ceiling white; zombie BRIGHT white (no hue clash)",
           dict(wall={"near": 0x47, "mid": 0x07, "far": 0x07}, ceil=0x07, floor=0x07, sprite=0x47)),
    "P3": ("FOG+INKS: walls bright white / white / blue by distance; ceiling cyan, floor green; zombie cells BRIGHT white (ink wins)",
           dict(wall={"near": 0x47, "mid": 0x07, "far": 0x01}, ceil=0x05, floor=0x04, sprite=0x47)),
    "P4": ("WARM: walls bright yellow / yellow / red by distance; ceiling cyan, floor green; zombie cells BRIGHT white (ink wins)",
           dict(wall={"near": 0x46, "mid": 0x06, "far": 0x02}, ceil=0x05, floor=0x04, sprite=0x47)),
    "P5": ("SKY PAPER: ceiling cells blue PAPER + white ink, floor green ink; walls as P3; zombie cells bright white on black",
           dict(wall={"near": 0x47, "mid": 0x07, "far": 0x01}, ceil=0x0F, floor=0x04, sprite=0x47)),
    "P2E": ("CHOSEN 2 Nov: P2 tonal walls (near BRIGHT) + enemies coloured: zombie BRIGHT green, imp BRIGHT magenta, corpses dim; items white",
            dict(wall={"near": 0x47, "mid": 0x07, "far": 0x07}, ceil=0x07, floor=0x07, sprite="enemy")),
    "P6": ("BLEED (option 1, for comparison): P3 colours but the wall/floor colour wins inside the zombie",
           dict(wall={"near": 0x47, "mid": 0x07, "far": 0x01}, ceil=0x05, floor=0x04, sprite=None)),
}

def classify(zbuf):
    """-> (cls[12][24] in {'wall','ceil','floor'}, band[12][24] in {'near','mid','far',None}) - the Z80 writer's rule:
    a cell is a wall cell when >= 8 of its 64 pixels are wall (near >= 64 px = < 1.5 cells, mid 24..63 px, far < 24 px = > 4 cells) (per pixel column: ray = x//3, wall rows 48-hv/2 .. 48+hv/2)."""
    cls = [[None] * 24 for _ in range(12)]; band = [[None] * 24 for _ in range(12)]
    for cx in range(24):
        for cy in range(12):
            y0, y1 = 8 * cy, 8 * cy + 8; wall = 0; hvmax = 0
            for x in range(8 * cx, 8 * cx + 8):
                hv = zbuf[x // 3]
                if not hv: continue
                top, bot = max(0, 48 - hv // 2), min(96, 48 + hv // 2)
                ov = max(0, min(y1, bot) - max(y0, top))
                if ov: wall += ov; hvmax = max(hvmax, hv)
            if wall >= 8:          # any full pixel row of wall: the wall colour wins the cell (recolours at most a few lattice dots)
                cls[cy][cx] = "wall"; band[cy][cx] = "near" if hvmax >= 64 else "mid" if hvmax >= 24 else "far"
            else:
                cls[cy][cx] = "ceil" if cy < 6 else "floor"
    return cls, band

def sprite_cells(zbuf, sprites):
    """cells touched by the sprite boxes the engine draws (columns where the wall is not nearer: zbuf <= hv)."""
    cells = set()
    for hv, c0, nc, typ, st in sprites:
        hd = enemy_h(hv); bot = 48 + hv // 2; top = bot - hd
        for x in range(max(0, 3 * c0), min(192, 3 * c0 + 3 * nc)):
            if zbuf[x // 3] > hv: continue
            for cy in range(max(0, top) // 8, min(95, bot - 1) // 8 + 1):
                cells.add((cy, x // 8))
    return cells

def pixel_cells(scr, bg):
    """cells (cy,cx in the 12x24 window) where the frame differs from the same frame without the sprite = cells with zombie pixels."""
    cells = set()
    for y in range(8, 104):
        base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        for bx in range(4, 28):
            if scr[base + bx] != bg[base + bx]: cells.add(((y - 8) // 8, bx - 4))
    return cells

def attrs(zbuf, sprites, sch, pix=None):
    cls, band = classify(zbuf)
    A = np.zeros((12, 24), np.uint8)
    for cy in range(12):
        for cx in range(24):
            A[cy, cx] = sch["wall"][band[cy][cx]] if cls[cy][cx] == "wall" else sch["ceil"] if cls[cy][cx] == "ceil" else sch["floor"]
    sc = pix if pix is not None else sprite_cells(zbuf, sprites); boxes = 0; nsc = 0
    if sch["sprite"] == "enemy":
        for sp in sprites:                      # vis order is far -> near: the nearer sprite's colour wins a shared cell
            col = enemy_attr(sp[3], sp[4])
            if col is None: continue
            cells = sprite_cells(zbuf, [sp])
            if pix is not None: cells &= pix
            for cy, cx in cells:
                if A[cy, cx] != col: boxes += 1
                A[cy, cx] = col
            nsc += len(cells)
        return A, nsc, boxes
    if sch["sprite"] is not None:
        for cy, cx in sc:
            if A[cy, cx] != sch["sprite"]: boxes += 1
            A[cy, cx] = sch["sprite"]
        for cy in range(9, 12):                 # the player's weapon: BUF byte columns 10..13, rows 72..95 (hud_b.asm draw_weapon)
            for cx in range(10, 14): A[cy, cx] = sch["sprite"]
    return A, len(sc), boxes

def recolour(scr, A):
    s = bytearray(scr)
    for cy in range(12):
        for cx in range(24):
            s[6144 + (1 + cy) * 32 + 4 + cx] = int(A[cy, cx])
    return bytes(s)

def fresh():
    m = machine()
    data = (ROOT / "src/48k/gen/level48.bin").read_bytes(); assert len(data) == 1081 and data[0] == 1
    m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
    call(m, "cls", "hud_init", "init_game")
    return m

def state(m):
    zbuf = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64]); nvis = m.memory[SYM["nvis"]]
    vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6 * nvis])
    sprites = []
    for i in range(nvis):
        th = SYM["things"] + 8 * vis[6 * i + 5]           # vis byte 5 = thing INDEX (sprites_d.asm: (IX - things) / 8)
        sprites.append((vis[6 * i], s8(vis[6 * i + 1]), vis[6 * i + 2], m.memory[th], m.memory[th + 5]))
    return zbuf, sprites

def stills():
    m = fresh()
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    fulls = []
    for dist in (1.0, 1.5):
        dx, dy = {0: (dist, 0), 64: (0, dist), 128: (-dist, 0), 192: (0, -dist)}.get(ang, (dist, 0))
        clear_things(m); call(m, "render", "hud_update"); bg = bytes(m.memory[16384:16384 + 6912])
        clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy); call(m, "render", "hud_update")
        scr = bytes(m.memory[16384:16384 + 6912]); zbuf, sprites = state(m)
        assert len(sprites) == 1, sprites
        pix = pixel_cells(scr, bg)
        cls, band = classify(zbuf)
        nw = sum(r.count("wall") for r in cls); print("%.1f cells: zombie hv %d c0 %d nc %d; wall cells %d, bands near/mid/far = %d/%d/%d" % (
            dist, sprites[0][0], sprites[0][1], sprites[0][2], nw, sum(r.count("near") for r in band), sum(r.count("mid") for r in band), sum(r.count("far") for r in band)))
        S = 3; W, H = 194 * S, 98 * S; gap = 12
        sheet = Image.new("RGB", (2 * W + 3 * gap, 44 + 3 * (H + 44)), (40, 40, 40)); d = ImageDraw.Draw(sheet)
        d.text((gap, 6), "Kill'em all M2.6 Track 2 colour mock - REAL engine frame (48K image, level 1, zombie %.1f cells ahead), window recoloured" % dist, fill=(255, 255, 0))
        d.text((gap, 22), "per 8x8 cell from engine state (zbuf + vis), i.e. what a Z80 attribute writer (288 cells/frame, 0 fps cost) would produce.", fill=(255, 255, 0))
        for i, (key, (title, sch)) in enumerate(SCHEMES.items()):
            A, nsc, boxes = attrs(zbuf, sprites, sch, pix)
            img = scr_img(recolour(scr, A))
            if dist == 1.0 and key in ("P3", "P4"): fulls.append((key, title, img.copy()))
            crop = img.crop((31, 7, 225, 105)).resize((W, H), Image.NEAREST)
            x = gap + (i % 2) * (W + gap); y = 44 + (i // 2) * (H + 44)
            d.text((x, y), "%s  %s" % (key, title[:110]), fill=(255, 255, 255))
            d.text((x, y + 14), "zombie pixels in %d cells; %d of them recoloured against their surroundings (visible box cells)" % (nsc, boxes), fill=(200, 200, 200))
            sheet.paste(crop, (x, y + 30))
            print("  %s: sprite cells %d, box cells %d" % (key, nsc, boxes))
        out = ROOT / ("build/m26_colour_sheet_%.1f.png" % dist); sheet.save(out); print("sheet", out, sheet.size)
    # near-wall viewpoint: hold Q (forward) through real game ticks until a wall is < 1.5 cells away (hv >= 64)
    pressed = {"Q"}
    def cb(port):
        if (port & 0xFF) != 0xFE: return 0xFF
        hi = port >> 8; v = 0xFF
        for k in pressed:
            row, bit = KEYS[k]
            if not (hi >> row) & 1: v &= ~(1 << bit)
        return v
    m.set_input_callback(cb); clear_things(m)
    for i in range(120):
        call(m, "render", "game_tick"); zbuf, sprites = state(m)
        if max(zbuf) >= 64: break
    pressed.clear(); call(m, "render", "hud_update"); zbuf, sprites = state(m)
    scr = bytes(m.memory[16384:16384 + 6912]); cls, band = classify(zbuf)
    print("near wall after %d ticks: max hv %d, bands near/mid/far = %d/%d/%d" % (i + 1, max(zbuf), sum(r.count("near") for r in band), sum(r.count("mid") for r in band), sum(r.count("far") for r in band)))
    S = 3; W, H = 194 * S, 98 * S; gap = 12
    sheet = Image.new("RGB", (2 * W + 3 * gap, 44 + 3 * (H + 44)), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((gap, 6), "Same six schemes after walking %d game ticks forward: a wall %d px tall fills the view -> the distance bands show" % (i + 1, max(zbuf)), fill=(255, 255, 0))
    d.text((gap, 22), "near = wall >= 64 px tall (BRIGHT), mid = 32..63, far < 32 px. No zombie in this view.", fill=(255, 255, 0))
    for j, (key, (title, sch)) in enumerate(SCHEMES.items()):
        A, nsc, boxes = attrs(zbuf, sprites, sch, set())
        crop = scr_img(recolour(scr, A)).crop((31, 7, 225, 105)).resize((W, H), Image.NEAREST)
        x = gap + (j % 2) * (W + gap); y = 44 + (j // 2) * (H + 44)
        d.text((x, y), "%s  %s" % (key, title[:110]), fill=(255, 255, 255)); sheet.paste(crop, (x, y + 30))
    out = ROOT / "build/m26_colour_sheet_near.png"; sheet.save(out); print("sheet", out, sheet.size)
    # full screens (with frame + HUD) of P3 and P4 at 1.0 cells, stacked for the phone
    S = 3; full = Image.new("RGB", (256 * S, 2 * (192 * S + 24)), (40, 40, 40)); d = ImageDraw.Draw(full)
    for i, (key, title, img) in enumerate(fulls):
        y = i * (192 * S + 24); d.text((6, y + 4), "%s %s" % (key, title[:100]), fill=(255, 255, 0))
        full.paste(img.resize((256 * S, 192 * S), Image.NEAREST), (0, y + 20))
    out = ROOT / "build/m26_colour_full.png"; full.save(out); print("full", out, full.size)

KEYS = {"Q": (2, 0), "A": (1, 0), "O": (5, 1), "P": (5, 0), "SPACE": (7, 0), "M": (7, 2), "Z": (0, 1), "X": (0, 2)}

def video(key="P3"):
    title, sch = SCHEMES[key]
    m = fresh()
    pressed = set()
    def cb(port):
        if (port & 0xFF) != 0xFE: return 0xFF
        hi = port >> 8; v = 0xFF
        for k in pressed:
            row, bit = KEYS[k]
            if not (hi >> row) & 1: v &= ~(1 << bit)
        return v
    m.set_input_callback(cb)
    nthings = sum(1 for i in range(16) if m.memory[SYM["things"] + 8 * i])
    print("level things alive after init_game:", nthings)
    if nthings == 0:
        sx, sy = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1]
        set_thing(m, 0, 2, sx + 2.5, sy + 0.5)
    # scripted controls (seconds of real Spectrum time): forward, look right, forward, look left, forward, fire, stand
    script = [(1.6, {"Q"}), (0.7, {"P"}), (1.8, {"Q"}), (0.6, {"O"}), (1.4, {"Q"}), (0.5, {"SPACE"}), (0.8, set()), (1.2, {"Q"}), (0.8, set())]
    fd = pathlib.Path("/tmp/m26_colour_frames"); shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
    t = 0.0; seg = 0; seg_t = 0.0; n = 0; durs = []; S = 3
    total = sum(s for s, _ in script)
    while t < total and seg < len(script):
        pressed.clear(); pressed.update(script[seg][1])
        fr = m.memory[SYM["frames"]] | (m.memory[SYM["frames"] + 1] << 8); fr = (fr + 1) & 0xFFFF
        m.set_memory_block(SYM["frames"], bytes([fr & 255, fr >> 8]))
        saved = bytes(m.memory[SYM["things"]:SYM["things"] + 128]); nv = m.memory[SYM["nvis"]]
        clear_things(m); call(m, "render"); bgscr = bytes(m.memory[16384:16384 + 6912]); m.set_memory_block(SYM["things"], saved)
        T = call(m, "render"); zbuf, sprites = state(m); T += call(m, "game_tick")
        dt = T / 3_500_000.0
        tk = m.memory[SYM["ticks"]] | (m.memory[SYM["ticks"] + 1] << 8); tk = (tk + max(1, round(dt * 50))) & 0xFFFF
        m.set_memory_block(SYM["ticks"], bytes([tk & 255, tk >> 8]))
        scr = bytes(m.memory[16384:16384 + 6912])
        A, nsc, boxes = attrs(zbuf, sprites, sch, pixel_cells(scr, bgscr) if sprites else set())
        top = scr_img(scr); bot = scr_img(recolour(scr, A))
        fr_img = Image.new("RGB", (256 * S, 2 * 192 * S + 2 * 18), (30, 30, 30)); d = ImageDraw.Draw(fr_img)
        d.text((6, 3), "TODAY (one ink) - real engine, real speed (%.0f ms this frame)" % (dt * 1000), fill=(255, 255, 0))
        fr_img.paste(top.resize((256 * S, 192 * S), Image.NEAREST), (0, 18))
        d.text((6, 192 * S + 21), "%s %s" % (key, title[:95]), fill=(255, 255, 0))
        fr_img.paste(bot.resize((256 * S, 192 * S), Image.NEAREST), (0, 192 * S + 36))
        fr_img.save(fd / ("f%04d.png" % n)); durs.append(dt); n += 1
        t += dt; seg_t += dt
        if seg_t >= script[seg][0]: seg += 1; seg_t = 0.0
    lst = fd / "list.txt"
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for i, dur in enumerate(durs): f.write("file 'f%04d.png'\nduration %.4f\n" % (i, dur))
        f.write("file 'f%04d.png'\n" % (n - 1))
    out = ROOT / ("build/m26_colour_walk_%s.mp4" % key)
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "format=yuv420p",
                        "-r", "25", "-c:v", "libx264", "-crf", "20", str(out)], capture_output=True, text=True)
    print("frames %d, real time %.2f s, mean %.2f fps, mp4 %s %s bytes, ffmpeg rc %d %s" % (
        n, t, n / t, out, out.stat().st_size if out.exists() else -1, r.returncode, r.stderr[-300:]))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stills"
    if mode == "stills": stills()
    elif mode == "video": video(sys.argv[2] if len(sys.argv) > 2 else "P3")

def chosen():
    """2 Nov 'P2 BUT put colour on the enemies' -> sheet of the P2E scheme: zombie / imp / both / corpse, 1.0-2.5 cells."""
    key = "P2E"; title, sch = SCHEMES[key]
    m = fresh()
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    def ahead(dist, side=0.0):
        return {0: (sx + 0.5 + dist, sy + 0.5 + side), 64: (sx + 0.5 - side, sy + 0.5 + dist), 128: (sx + 0.5 - dist, sy + 0.5 - side), 192: (sx + 0.5 + side, sy + 0.5 - dist)}.get(ang, (sx + 0.5 + dist, sy + 0.5 + side))
    scenes = [("zombie 1.0 cell", [(2, 1.0, 0.0, 1)]), ("imp 1.0 cell", [(1, 1.0, 0.0, 1)]),
              ("zombie 1.5 + imp 2.5 cells", [(2, 1.5, 0.3, 1), (1, 2.5, -0.5, 1)]), ("zombie corpse 1.2 + zombie 2.0 + imp 1.7 cells", [(2, 1.2, 0.0, 3), (2, 2.0, -0.4, 1), (1, 1.7, 0.45, 1)])]
    S = 3; W, H = 194 * S, 98 * S; gap = 12
    sheet = Image.new("RGB", (2 * W + 3 * gap, 44 + 2 * (H + 44)), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    d.text((gap, 6), "CHOSEN scheme P2E (2 Nov): one white ink window, near walls BRIGHT; enemies carry their own BRIGHT ink in the cells they touch", fill=(255, 255, 0))
    d.text((gap, 22), "zombie = BRIGHT green, imp = BRIGHT magenta, corpse = same hue not bright. Real 48K engine frames, recoloured per 8x8 cell.", fill=(255, 255, 0))
    for i, (lab, th) in enumerate(scenes):
        clear_things(m); call(m, "render", "hud_update"); bg = bytes(m.memory[16384:16384 + 6912])
        clear_things(m)
        for j, (typ, dist, side, st) in enumerate(th):
            x, y = ahead(dist, side); set_thing(m, j, typ, x, y); m.set_memory_block(SYM["things"] + 8 * j + 5, bytes([st]))
        call(m, "render", "hud_update"); scr = bytes(m.memory[16384:16384 + 6912]); zbuf, sprites = state(m)
        pix = pixel_cells(scr, bg); A, nsc, boxes = attrs(zbuf, sprites, sch, pix)
        crop = scr_img(recolour(scr, A)).crop((31, 7, 225, 105)).resize((W, H), Image.NEAREST)
        x0 = gap + (i % 2) * (W + gap); y0 = 44 + (i // 2) * (H + 44)
        d.text((x0, y0), lab, fill=(255, 255, 255)); d.text((x0, y0 + 14), "vis %s; coloured cells %d" % ([(s[0], s[3], s[4]) for s in sprites], nsc), fill=(200, 200, 200))
        sheet.paste(crop, (x0, y0 + 30)); print(lab, "vis", sprites, "cells", nsc)
    out = ROOT / "build/m26_colour_chosen_P2E.png"; sheet.save(out); print("sheet", out, sheet.size)

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "chosen":
    chosen()
