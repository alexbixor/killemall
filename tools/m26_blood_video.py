#!/usr/bin/env python3
"""m26_blood_video.py - 3 Nov 2026: the 20-second scene video (2 Nov 'different types of enemies and one ammo box and one health
box. make the video 20 seconds long') from the REAL rebuilt 48K image (build/kea48.tap): D5 ceiling, P2E colours, blood 1 red
flash and the muzzle flash are all in the engine now, so every frame is the Spectrum screen exactly as the Z80 code left it (pixels
+ attributes), no compositing. Same scene, bot and method as tools/m26_scene_video.py (Python Z80 core, live AI, scripted keys,
frame durations = measured T-states of render + game_tick at 3.5 MHz = real speed).
Outputs: build/m26_blood_walk.mp4, build/m26_blood_strip.png (8 frames), build/m26_blood_hits.png (first frame of every red flash).
usage: m26_blood_video.py [dry|render]"""
import sys, pathlib, shutil, subprocess, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, SYM, ROOT, scr_img, KEYS
from m26_scene_video import controller, setup, state_idx, TOTAL

def run(render):
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
    fd = pathlib.Path("/tmp/m26_blood_frames")
    if render: shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
    t = 0.0; n = 0; durs = []; S = 3; next_log = 0.0; t_wall = time.time(); sprites = []; flash_frames = []; muzzle_frames = []
    Tr = []
    while t < TOTAL:
        pressed.clear(); pressed.update(controller(t, sprites, m))
        fr = m.memory[SYM["frames"]] | (m.memory[SYM["frames"] + 1] << 8); fr = (fr + 1) & 0xFFFF
        m.set_memory_block(SYM["frames"], bytes([fr & 255, fr >> 8]))
        pre = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
        flashing = [i for i in range(16) if 0 < pre[8 * i] < 16 and pre[8 * i + 6] & 0xC0]     # drawn red this frame if visible
        muzzle = m.memory[SYM["weapon_frame"]] != 0
        T = call(m, "render"); Tr.append(T); zbuf, sprites = state_idx(m); scr = bytes(m.memory[16384:16384 + 6912])
        shown = [i for i in flashing if any(sp[5] == i for sp in sprites)]
        if shown: flash_frames.append((n, shown))
        if muzzle: muzzle_frames.append(n)
        T += call(m, "game_tick"); dt = T / 3_500_000.0
        tk = m.memory[SYM["ticks"]] | (m.memory[SYM["ticks"] + 1] << 8); tk = (tk + max(1, round(dt * 50))) & 0xFFFF
        m.set_memory_block(SYM["ticks"], bytes([tk & 255, tk >> 8]))
        if t >= next_log:
            px = (m.memory[SYM["posx"]] | m.memory[SYM["posx"] + 1] << 8) / 256; py = (m.memory[SYM["posy"]] | m.memory[SYM["posy"] + 1] << 8) / 256
            th = []
            for i in range(5):
                b = bytes(m.memory[SYM["things"] + 8 * i:SYM["things"] + 8 * i + 8])
                th.append("%d:%s@%.1f,%.1f s%d hp%d f%d" % (i, {1: "imp", 2: "zom", 16: "HLT", 17: "AMM", 0: "---"}.get(b[0], str(b[0])),
                                                           (b[1] | b[2] << 8) / 256, (b[3] | b[4] << 8) / 256, b[5], b[6] & 31, b[6] >> 6))
            print("t=%5.1fs keys=%s player=(%.1f,%.1f) ang=%d health=%d ammo=%d %s | %s" % (
                t, "".join(sorted(pressed)) or "-", px, py, m.memory[SYM["angle"]], m.memory[SYM["health"]], m.memory[SYM["ammo"]],
                "RED" if shown else "", " ".join(th)))
            next_log += 0.5
        if render:
            im = scr_img(scr).resize((256 * S, 192 * S), Image.NEAREST)
            fr_img = Image.new("RGB", (256 * S, 192 * S + 18), (30, 30, 30)); d = ImageDraw.Draw(fr_img)
            d.text((6, 3), "REAL 48K BUILD 3 Nov: D5 ceiling + P2E colours + BLOOD 1 red flash + muzzle flash - real engine, real speed (%.0f ms this frame)%s" % (
                dt * 1000, "   << HIT" if shown else ""), fill=(255, 255, 0))
            fr_img.paste(im, (0, 18)); fr_img.save(fd / ("f%04d.png" % n))
        durs.append(dt); n += 1; t += dt
    print("frames %d, game time %.2f s, mean %.2f fps (render only %.2f fps), wall %.0f s" % (n, t, n / t, 3_500_000 * len(Tr) / sum(Tr), time.time() - t_wall))
    firsts = [f for j, (f, _) in enumerate(flash_frames) if j == 0 or f != flash_frames[j - 1][0] + 1]
    print("frames showing a red flash: %d, flashes (first frames): %s" % (len(flash_frames), firsts))
    print("frames showing the muzzle flash: %d" % len(muzzle_frames))
    if not render: return
    lst = fd / "list.txt"
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for i, dur in enumerate(durs): f.write("file 'f%04d.png'\nduration %.4f\n" % (i, dur))
        f.write("file 'f%04d.png'\n" % (n - 1))
    out = ROOT / "build/m26_blood_walk.mp4"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "format=yuv420p",
                        "-r", "25", "-c:v", "libx264", "-crf", "20", str(out)], capture_output=True, text=True)
    print("mp4 %s %s bytes, ffmpeg rc %d %s" % (out, out.stat().st_size if out.exists() else -1, r.returncode, r.stderr[-300:]))
    picks = [int(n * k / 8) for k in range(8)]
    fw, fh = Image.open(fd / "f0000.png").size
    strip = Image.new("RGB", (4 * fw // 2 + 5 * 6, 2 * (fh // 2) + 3 * 6), (30, 30, 30))
    for j, p in enumerate(picks):
        im = Image.open(fd / ("f%04d.png" % p)).resize((fw // 2, fh // 2), Image.NEAREST)
        strip.paste(im, (6 + (j % 4) * (fw // 2 + 6), 6 + (j // 4) * (fh // 2 + 6)))
    out2 = ROOT / "build/m26_blood_strip.png"; strip.save(out2); print("strip", out2, strip.size, "frames", picks)
    if firsts:
        picks = firsts[:8]; cw, ch = 194 * 3, 98 * 3                      # the 3D window: x 31..225, y 7..105 (x3)
        close = Image.new("RGB", (4 * (cw + 6) + 6, (len(picks) + 3) // 4 * (ch + 24) + 6), (30, 30, 30)); dd = ImageDraw.Draw(close)
        for j, f in enumerate(picks):
            im = Image.open(fd / ("f%04d.png" % f)).crop((31 * 3, 18 + 7 * 3, 225 * 3, 18 + 105 * 3))
            x0 = 6 + (j % 4) * (cw + 6); y0 = 6 + (j // 4) * (ch + 24)
            dd.text((x0, y0), "hit %d: frame %d, t=%.1fs - the enemy's cells BRIGHT red for 3 frames; muzzle cells yellow" % (j + 1, f, sum(durs[:f])), fill=(255, 255, 0))
            close.paste(im, (x0, y0 + 14))
        outc = ROOT / "build/m26_blood_hits.png"; close.save(outc); print("hit close-ups", outc, close.size, "frames", picks)

if __name__ == "__main__":
    run(render=(sys.argv[1] if len(sys.argv) > 1 else "dry") == "render")
