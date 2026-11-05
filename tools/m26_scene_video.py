#!/usr/bin/env python3
"""m26_scene_video.py - 2 Nov 'add two more enemies ... different types of enemies and one ammo box and one health box. make the
video 20 seconds long'. Same method as m26_ceiling_video.py (real 48K engine frames, Python Z80 core, live AI, scripted keys,
D5 ceiling composited from a black/white ceiling pair, P2E colours per 8x8 cell, frame durations from measured T-states).
Scene: level-1 start room, things replaced by: zombie, imp, zombie, health box, ammo box (positions below).
usage: m26_scene_video.py dry      -> prints one line per 0.5 s (player, visible sprites, health/ammo) - no pictures
       m26_scene_video.py render   -> build/m26_scene_walk_D5_P2E.mp4 + build/m26_scene_strip.png"""
import sys, pathlib, shutil, subprocess, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import (fresh, call, clear_things, set_thing, state, SYM, ROOT, scr_img, SCHEMES, attrs, pixel_cells,
                             recolour, KEYS, s8, sprite_cells)
from m26_ceiling_video import poke_ceiling, composite, TODAY
import m26_splat

# things: (slot, type, x, y). types: 1 imp, 2 zombie, 16 health, 17 ammo. Player starts at (3.5, 7.5) facing east (angle 0;
# +y = screen right). Start room x 1..14, y 1..11 with a 4x4 pillar at x 8..11, y 4..7.
THINGS = [(0, 2, 7.5, 10.5),      # zombie A: ahead-right, 5 cells
          (1, 1, 12.5, 9.5),      # imp: ahead, 9 cells, below the pillar line (visible)
          (2, 2, 7.5, 4.5),       # zombie B: ahead-left, 5 cells
          (3, 16, 5.0, 7.5),      # health box: 1.5 cells straight ahead (picked up on the walk; health starts at 60)
          (4, 17, 6.0, 7.9)]      # ammo box: 2.5 cells ahead, a little right (picked up right after)
START_HEALTH = 60
TOTAL = 20.0
# keys: Q forward, A back, O turn left, P turn right, SPACE fire. The player is a small script (a bot): first look at the scene,
# then walk over the two boxes, then turn toward the nearest live enemy and fire when it is in the centre; back away if it gets
# closer than about one cell so it stays in view.
def controller(t, sprites, m):
    """the bot: 1.2 s look, 2.2 s walk over the boxes, then face the nearest live enemy (from the things table), fire when its
    sprite spans the centre column (the engine's own hitscan window, game_g.asm), step back if it is closer than ~1 cell."""
    import math
    if t < 1.2: return set()
    if t < 3.4: return {"Q"}
    px = (m.memory[SYM["posx"]] | m.memory[SYM["posx"] + 1] << 8) / 256; py = (m.memory[SYM["posy"]] | m.memory[SYM["posy"] + 1] << 8) / 256
    ang = m.memory[SYM["angle"]]
    live = []
    for i in range(5):
        b = bytes(m.memory[SYM["things"] + 8 * i:SYM["things"] + 8 * i + 8])
        if 0 < b[0] < 16 and b[5] != 3:
            x, y = (b[1] | b[2] << 8) / 256, (b[3] | b[4] << 8) / 256
            live.append((math.hypot(x - px, y - py), x, y))
    if not live: return set()                                   # all dead: hold the view on the corpses
    d, x, y = min(live)
    want = int(round(math.atan2(y - py, x - px) * 128 / math.pi)) & 255     # angle units: 256 per turn, 64 = +y
    diff = ((want - ang + 128) & 255) - 128                                  # -128..127, positive = turn right (P)
    keys = set()
    in_view = [sp for sp in sprites if sp[3] < 16 and sp[4] != 3 and sp[1] <= 33 and sp[1] + sp[2] >= 31]
    if in_view: keys.add("SPACE")
    if abs(diff) > 3: keys.add("P" if diff > 0 else "O")
    if d < 1.1: keys.add("A")
    return keys
OUT = "m26_scene_walk_D5_P2E"
OUT_BLOOD = "m26_scene_walk_D5_P2E_blood1"
OUT_SPLAT = "m26_scene_walk_D5_P2E_blood2"

# 2 Nov 12:2x 'Show me 1 first': blood effect 1 = the cells an enemy occupies are written BRIGHT red for FLASH_FRAMES rendered
# frames after a hit (hit = its hit points went down during game_tick, including the fatal hit). Reuses the P2E cell writer.
FLASH_FRAMES = 3
FLASH_ATTR = 0x42          # BRIGHT + red ink, black paper

def state_idx(m):
    """like m26_colour_mock.state but each sprite also carries its thing index (vis byte 5)."""
    zbuf = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64]); nvis = m.memory[SYM["nvis"]]
    vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6 * nvis]); out = []
    for i in range(nvis):
        idx = vis[6 * i + 5]; th = SYM["things"] + 8 * idx
        out.append((vis[6 * i], s8(vis[6 * i + 1]), vis[6 * i + 2], m.memory[th], m.memory[th + 5], idx))
    return zbuf, out

def setup(m):
    clear_things(m)
    for slot, typ, x, y in THINGS: set_thing(m, slot, typ, x, y)
    m.set_memory_block(SYM["health"], bytes([START_HEALTH])); call(m, "hud_update")

def run(render, blood=False, splat=False):
    scheme = "P2E"; title, sch = SCHEMES[scheme]
    m = fresh(); pressed = set()
    def cb(port):
        if (port & 0xFF) != 0xFE: return 0xFF
        hi = port >> 8; v = 0xFF
        for k in pressed:
            row, bit = KEYS[k]
            if not (hi >> row) & 1: v &= ~(1 << bit)
        return v
    m.set_input_callback(cb)
    setup(m)
    splats = m26_splat.Splats(); splat_T = []
    if splat:
        placed = m26_splat.install(m, "decor"); print("splat frames installed:", [("%04X" % a, n) for a, n in placed])
    fd = pathlib.Path("/tmp/m26_scene_frames")
    if render: shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
    t = 0.0; seg = 0; n = 0; durs = []; S = 3; next_log = 0.0; t_wall = time.time(); sprites = []; flash = {}; hit_frames = []
    while t < TOTAL:
        pressed.clear(); pressed.update(controller(t, sprites, m))
        fr = m.memory[SYM["frames"]] | (m.memory[SYM["frames"] + 1] << 8); fr = (fr + 1) & 0xFFFF
        m.set_memory_block(SYM["frames"], bytes([fr & 255, fr >> 8]))
        poke_ceiling(m, *TODAY)
        saved = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
        clear_things(m); call(m, "render"); bgscr = bytes(m.memory[16384:16384 + 6912]); m.set_memory_block(SYM["things"], saved)
        T0 = None
        if splat and splats.live:
            sv = splats.hide(m); T0 = call(m, "render"); scr0 = bytes(m.memory[16384:16384 + 6912]); splats.show(m, sv)   # same frame without the splat
        T = call(m, "render"); zbuf, sprites = state_idx(m); scr = bytes(m.memory[16384:16384 + 6912])
        if T0 is not None: splat_T.append((n, T, T0, len(splats.live)))
        if render:
            poke_ceiling(m, 0x0000, 0x0000, 0x00FF); call(m, "render"); black = bytes(m.memory[16384:16384 + 6912])
            poke_ceiling(m, 0xFFFF, 0xFFFF, 0x00FF); call(m, "render"); white = bytes(m.memory[16384:16384 + 6912])
            poke_ceiling(m, *TODAY)
        hp_before = [m.memory[SYM["things"] + 8 * i + 6] for i in range(5)]
        T += call(m, "game_tick"); dt = T / 3_500_000.0
        flashing = [sp for sp in sprites if flash.get(sp[5], 0) > 0]        # this rendered frame shows the flash for these
        for i in range(5):
            if m.memory[SYM["things"] + 8 * i + 6] < hp_before[i]:
                flash[i] = FLASH_FRAMES + 1   # +1: decremented below, shows on the next 3 renders
                if splat:
                    b = bytes(m.memory[SYM["things"] + 8 * i:SYM["things"] + 8 * i + 8])
                    px = (m.memory[SYM["posx"]] | m.memory[SYM["posx"] + 1] << 8) / 256; py = (m.memory[SYM["posy"]] | m.memory[SYM["posy"] + 1] << 8) / 256
                    splats.spawn(m, (b[1] | b[2] << 8) / 256, (b[3] | b[4] << 8) / 256, px, py)
        splat_now = [sp for sp in sprites if sp[3] in m26_splat.SPLAT_TYPES]
        if splat: splats.tick(m)
        for i in list(flash):
            flash[i] -= 1
            if flash[i] <= 0: del flash[i]
        tk = m.memory[SYM["ticks"]] | (m.memory[SYM["ticks"] + 1] << 8); tk = (tk + max(1, round(dt * 50))) & 0xFFFF
        m.set_memory_block(SYM["ticks"], bytes([tk & 255, tk >> 8]))
        if t >= next_log or not render:
            px = (m.memory[SYM["posx"]] | m.memory[SYM["posx"] + 1] << 8) / 256; py = (m.memory[SYM["posy"]] | m.memory[SYM["posy"] + 1] << 8) / 256
            th = []
            for i in range(5):
                b = bytes(m.memory[SYM["things"] + 8 * i:SYM["things"] + 8 * i + 8])
                th.append("%d:%s@%.1f,%.1f s%d hp%d" % (i, {1: "imp", 2: "zom", 16: "HLT", 17: "AMM", 0: "---"}.get(b[0], str(b[0])),
                                                      (b[1] | b[2] << 8) / 256, (b[3] | b[4] << 8) / 256, b[5], b[6]))
            if t >= next_log:
                print("t=%5.1fs seg=%d keys=%s player=(%.1f,%.1f) ang=%d health=%d ammo=%d vis=%s | %s" % (
                    t, seg, "".join(sorted(pressed)) or "-", px, py, m.memory[SYM["angle"]], m.memory[SYM["health"]], m.memory[SYM["ammo"]],
                    [(s[3], s[0], s[1], s[2]) for s in sprites], " ".join(th)))
                next_log += 0.5
        if render:
            pix = pixel_cells(scr, bgscr) if sprites else set()
            A, nsc, boxes = attrs(zbuf, [sp[:5] for sp in sprites], sch, pix)
            if blood and flashing:
                for sp in flashing:
                    for cy, cx in sprite_cells(zbuf, [sp[:5]]) & pix: A[cy, cx] = FLASH_ATTR
            if splat and splat_now and T0 is not None:
                # only the cells the splat's own pixels (and its black halo) land in go red - the enemy's other cells keep their ink
                for cy, cx in pixel_cells(scr, scr0) & pix: A[cy, cx] = m26_splat.SPLAT_ATTR
            if (blood and flashing) or (splat and splat_now): hit_frames.append(n)
            d5scr, nm = composite(scr, black, white)
            top = scr_img(scr); bot = scr_img(recolour(d5scr, A))
            fr_img = Image.new("RGB", (256 * S, 2 * 192 * S + 2 * 18), (30, 30, 30)); d = ImageDraw.Draw(fr_img)
            d.text((6, 3), "TODAY on the Deck: one ink, dot ceiling - real engine, real speed (%.0f ms this frame)" % (dt * 1000), fill=(255, 255, 0))
            fr_img.paste(top.resize((256 * S, 192 * S), Image.NEAREST), (0, 18))
            d.text((6, 192 * S + 21), "PROPOSED: D5 ceiling + P2E colours" + (" + BLOOD 1: enemy flashes BRIGHT RED for 3 frames when hit" if blood else "") + (" + BLOOD 2: red SPLATTER sprite at the chest for 3 frames (real engine sprite)" if splat else ""), fill=(255, 255, 0))
            fr_img.paste(bot.resize((256 * S, 192 * S), Image.NEAREST), (0, 192 * S + 36))
            fr_img.save(fd / ("f%04d.png" % n))
        durs.append(dt); n += 1
        t += dt
    print("frames %d, game time %.2f s, mean %.2f fps, wall %.0f s, frames with a red flash: %d %s" % (n, t, n / t, time.time() - t_wall, len(hit_frames), hit_frames))
    if not render: return
    lst = fd / "list.txt"
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for i, dur in enumerate(durs): f.write("file 'f%04d.png'\nduration %.4f\n" % (i, dur))
        f.write("file 'f%04d.png'\n" % (n - 1))
    out = ROOT / ("build/%s.mp4" % (OUT_SPLAT if splat else OUT_BLOOD if blood else OUT))
    if splat_T:
        print("SPLAT COST (T-states of render, same frame with / without the splat sprite):")
        deltas = []
        for fn, Tw, Two, nl in splat_T:
            deltas.append(Tw - Two); print("  frame %3d: with %7d  without %7d  delta %+6d T  (%d splat sprite(s))" % (fn, Tw, Two, Tw - Two, nl))
        print("  mean delta %+d T = %.2f%% of a %d T frame; max %+d T; frames affected %d of %d" % (
            sum(deltas) / len(deltas), 100.0 * sum(deltas) / len(deltas) / (sum(durs) / len(durs) * 3_500_000), sum(durs) / len(durs) * 3_500_000, max(deltas), len(splat_T), n))
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "format=yuv420p",
                        "-r", "25", "-c:v", "libx264", "-crf", "20", str(out)], capture_output=True, text=True)
    print("mp4 %s %s bytes, ffmpeg rc %d %s" % (out, out.stat().st_size if out.exists() else -1, r.returncode, r.stderr[-300:]))
    picks = [int(n * k / 8) for k in range(8)]
    if (blood or splat) and hit_frames:
        firsts = [f for j, f in enumerate(hit_frames) if j == 0 or f != hit_frames[j - 1] + 1]      # first frame of each flash
        picks = firsts[:8]
        Z = 2; cw, ch = 194 * 3, 98 * 3                     # the 3D window inside the bottom pane: x 31..225, y 7..105 (x3)
        close = Image.new("RGB", (4 * (cw + 6) + 6, (len(picks) + 3) // 4 * (ch + 24) + 6), (30, 30, 30)); dd = ImageDraw.Draw(close)
        for j, f in enumerate(picks):
            im = Image.open(fd / ("f%04d.png" % f)).crop((31 * 3, 612 + 7 * 3, 225 * 3, 612 + 105 * 3))
            x0 = 6 + (j % 4) * (cw + 6); y0 = 6 + (j // 4) * (ch + 24)
            dd.text((x0, y0), "hit %d: frame %d, t=%.1fs%s" % (j + 1, f, sum(durs[:f]), " - red splatter sprite at the chest (3 frames: burst, burst, drip)" if splat else " - the enemy's cells go bright red for 3 frames"), fill=(255, 255, 0))
            close.paste(im, (x0, y0 + 14))
        outc = ROOT / ("build/m26_scene_blood%s_hits.png" % ("2" if splat else "1")); close.save(outc); print("hit close-ups", outc, close.size, "frames", picks)
    fw, fh = Image.open(fd / "f0000.png").size
    strip = Image.new("RGB", (4 * fw // 2 + 5 * 6, 2 * (fh // 2) + 3 * 6), (30, 30, 30))
    for j, p in enumerate(picks):
        im = Image.open(fd / ("f%04d.png" % p)).resize((fw // 2, fh // 2), Image.NEAREST)
        strip.paste(im, (6 + (j % 4) * (fw // 2 + 6), 6 + (j // 4) * (fh // 2 + 6)))
    out2 = ROOT / ("build/m26_scene_strip%s.png" % ("_blood2" if splat else "_blood1" if blood else "")); strip.save(out2); print("strip", out2, strip.size, "frames", picks)

if __name__ == "__main__":
    run(render=(sys.argv[1] if len(sys.argv) > 1 else "dry") == "render", blood="blood1" in sys.argv[2:], splat="blood2" in sys.argv[2:])
