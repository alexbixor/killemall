#!/usr/bin/env python3
"""m26_ceiling_video.py - 2 Nov 'show me a video': the D5 line-diamond ceiling in motion, with the approved P2E colours.
Top pane = the game as it is on the Deck today (one ink, dot ceiling). Bottom pane = proposed: D5 ceiling (continuous
45-degree diagonal lines forming 8x8 diamonds) + P2E colours (near walls BRIGHT, zombie BRIGHT green, imp BRIGHT magenta).
Every frame is a real 48K engine frame (Python Z80 core running the shipped image, live zombie AI, scripted keys); the
D5 ceiling is composited exactly: mask = pixels that differ between a ceiling-black and a ceiling-white render of the same
state (walls, sprites, gun, distance lines are identical in both and therefore untouched). Frame durations come from the
measured T-states of render + game_tick (3.5 MHz), so the MP4 plays at real Spectrum speed."""
import sys, pathlib, shutil, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import (fresh, call, clear_things, set_thing, state, SYM, ROOT, scr_img, SCHEMES, attrs, pixel_cells,
                             recolour, KEYS)

TOP = 8                 # screen pixel row of BUF row 0
HORIZON = 48            # BUF row of the first floor row
TODAY = (0x0001, 0x0000, 0x00FF)

def poke_ceiling(m, de, bc, line):
    m.set_memory_block(SYM["cl_ce"] + 1, bytes([de & 255, de >> 8]))
    m.set_memory_block(SYM["cl_cb"] + 1, bytes([bc & 255, bc >> 8]))
    m.set_memory_block(SYM["cl_cw"] + 1, bytes([line & 255, line >> 8]))

def d5_byte(bufrow):
    """D5 pattern byte for one pixel row (same for every byte column): 45-degree X lattice, 8 px x 8 rows"""
    r = (HORIZON - 1 - bufrow) % 8
    v = 0
    for c in range(8):
        if c == r or c == (-r) % 8: v |= 0x80 >> c
    return v

PAT = [d5_byte(r) for r in range(96)]

def composite(today, black, white):
    out = bytearray(today); n = 0
    for i in range(6144):
        mask = black[i] ^ white[i]
        if not mask: continue
        y = ((i >> 11) << 6) | ((i >> 8) & 7) | (((i >> 5) & 7) << 3)
        br = y - TOP
        if not (0 <= br < HORIZON): continue      # safety: only the ceiling half of the 3D window
        out[i] = (today[i] & ~mask & 255) | (PAT[br] & mask); n += 1
    return bytes(out), n

def main(scheme="P2E"):
    title, sch = SCHEMES[scheme]
    m = fresh(); pressed = set()
    def cb(port):
        if (port & 0xFF) != 0xFE: return 0xFF
        hi = port >> 8; v = 0xFF
        for k in pressed:
            row, bit = KEYS[k]
            if not (hi >> row) & 1: v &= ~(1 << bit)
        return v
    m.set_input_callback(cb)
    nthings = sum(1 for i in range(16) if m.memory[SYM["things"] + 8 * i])
    if nthings == 0:
        sx, sy = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1]; set_thing(m, 0, 2, sx + 2.5, sy + 0.5)
    script = [(1.6, {"Q"}), (0.7, {"P"}), (1.8, {"Q"}), (0.6, {"O"}), (1.4, {"Q"}), (0.5, {"SPACE"}), (0.8, set()), (1.2, {"Q"}), (0.8, set())]
    fd = pathlib.Path("/tmp/m26_ceiling_frames"); shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
    t = 0.0; seg = 0; seg_t = 0.0; n = 0; durs = []; S = 3; masked = []
    total = sum(s for s, _ in script)
    while t < total and seg < len(script):
        pressed.clear(); pressed.update(script[seg][1])
        fr = m.memory[SYM["frames"]] | (m.memory[SYM["frames"] + 1] << 8); fr = (fr + 1) & 0xFFFF
        m.set_memory_block(SYM["frames"], bytes([fr & 255, fr >> 8]))
        poke_ceiling(m, *TODAY)
        saved = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
        clear_things(m); call(m, "render"); bgscr = bytes(m.memory[16384:16384 + 6912]); m.set_memory_block(SYM["things"], saved)
        T = call(m, "render"); zbuf, sprites = state(m); scr = bytes(m.memory[16384:16384 + 6912])
        poke_ceiling(m, 0x0000, 0x0000, 0x00FF); call(m, "render"); black = bytes(m.memory[16384:16384 + 6912])
        poke_ceiling(m, 0xFFFF, 0xFFFF, 0x00FF); call(m, "render"); white = bytes(m.memory[16384:16384 + 6912])
        poke_ceiling(m, *TODAY)
        T += call(m, "game_tick"); dt = T / 3_500_000.0
        tk = m.memory[SYM["ticks"]] | (m.memory[SYM["ticks"] + 1] << 8); tk = (tk + max(1, round(dt * 50))) & 0xFFFF
        m.set_memory_block(SYM["ticks"], bytes([tk & 255, tk >> 8]))
        A, nsc, boxes = attrs(zbuf, sprites, sch, pixel_cells(scr, bgscr) if sprites else set())
        d5scr, nm = composite(scr, black, white); masked.append(nm)
        top = scr_img(scr); bot = scr_img(recolour(d5scr, A))
        fr_img = Image.new("RGB", (256 * S, 2 * 192 * S + 2 * 18), (30, 30, 30)); d = ImageDraw.Draw(fr_img)
        d.text((6, 3), "TODAY on the Deck: one ink, dot ceiling - real engine, real speed (%.0f ms this frame)" % (dt * 1000), fill=(255, 255, 0))
        fr_img.paste(top.resize((256 * S, 192 * S), Image.NEAREST), (0, 18))
        d.text((6, 192 * S + 21), "PROPOSED: D5 ceiling (diamonds drawn with lines) + %s colours (bright near walls, green zombie)" % scheme, fill=(255, 255, 0))
        fr_img.paste(bot.resize((256 * S, 192 * S), Image.NEAREST), (0, 192 * S + 36))
        fr_img.save(fd / ("f%04d.png" % n)); durs.append(dt); n += 1
        t += dt; seg_t += dt
        if seg_t >= script[seg][0]: seg += 1; seg_t = 0.0
    lst = fd / "list.txt"
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for i, dur in enumerate(durs): f.write("file 'f%04d.png'\nduration %.4f\n" % (i, dur))
        f.write("file 'f%04d.png'\n" % (n - 1))
    out = ROOT / "build/m26_ceiling_walk_D5.mp4"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "format=yuv420p",
                        "-r", "25", "-c:v", "libx264", "-crf", "20", str(out)], capture_output=True, text=True)
    print("frames %d, real time %.2f s, mean %.2f fps, ceiling bytes masked per frame min %d max %d, mp4 %s %s bytes, ffmpeg rc %d %s" % (
        n, t, n / t, min(masked), max(masked), out, out.stat().st_size if out.exists() else -1, r.returncode, r.stderr[-300:]))
    # six-frame strip for a still
    picks = [int(n * k / 6) for k in range(6)]
    fw, fh = Image.open(fd / "f0000.png").size
    strip = Image.new("RGB", (6 * fw // 2 + 7 * 6, fh // 2 + 12), (30, 30, 30))
    for j, p in enumerate(picks):
        im = Image.open(fd / ("f%04d.png" % p)).resize((fw // 2, fh // 2), Image.NEAREST)
        strip.paste(im, (6 + j * (fw // 2 + 6), 6))
    out2 = ROOT / "build/m26_ceiling_walk_strip_D5.png"; strip.save(out2); print("strip", out2, strip.size, "frames", picks)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "P2E")
