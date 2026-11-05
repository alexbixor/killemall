#!/usr/bin/env python3
"""m29b_slowmo_video.py - assemble the frame-exact captures of m29b_slowmo.py (48k, 128k, next) into ONE slow-motion video:
1 s of game time (50 ticks) stretched 10x, each panel shows exactly the frames that machine drew, held for their real
duration; under each panel a strip plots the camera x position of every drawn frame (dots) against game time (the 10 game
steps are the vertical lines). Output build/m29b_slowmo.mp4 + build/m29b_slowmo_end.png."""
import json, pathlib, subprocess, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from run48 import scr_to_png
ROOT = pathlib.Path(__file__).resolve().parent.parent
SLOW = 10; FPS = 25; TICKS = 50
LABEL = {"48k": "48K classic", "128k": "128K (camera glide)", "next": "Spectrum Next 28 MHz (camera glide)"}
data = {}
for m in ("48k", "128k", "next"):
    d = ROOT / ("build/m29b_slowmo_%s" % m); j = json.loads((d / "index.json").read_text())
    fr = j["frames"]
    for e in fr:
        png = d / e["scr"].replace(".scr", ".png"); scr_to_png((d / e["scr"]).read_bytes(), str(png)); e["png"] = str(png)
    data[m] = fr
x0 = min(e["x"] for fr in data.values() for e in fr); x1 = max(e["x"] for fr in data.values() for e in fr)
W, H = 512, 384; GH = 110; CAP = 40
fd = ROOT / "build/m29b_slowmo_frames"; shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
total = TICKS * SLOW * FPS // 50                     # video frames: 50 ticks * 10 slow / 50 Hz * 25 fps = 250
names = []
for n in range(total + 1):
    t = n / float(total) * TICKS                      # game time in ticks
    panels = []
    for m in ("48k", "128k", "next"):
        fr = data[m]; cur = None
        for e in fr:
            if e["ticks"] <= t: cur = e
        if cur is None: cur = fr[0]
        im = Image.open(cur["png"]).convert("RGB").resize((W, H), Image.NEAREST)
        pan = Image.new("RGB", (W, CAP + H + GH), (0, 0, 0)); d = ImageDraw.Draw(pan)
        d.text((6, 4), LABEL[m], fill=(255, 255, 255))
        shown = sum(1 for e in fr if e["ticks"] <= t)
        d.text((6, 22), "game time %.2f s   frames drawn %2d   camera x %.3f" % (t / 50.0, shown, cur["x"]), fill=(255, 255, 0))
        pan.paste(im, (0, CAP))
        g = Image.new("RGB", (W, GH), (16, 16, 16)); gd = ImageDraw.Draw(g)
        gy0, gy1 = 12, GH - 14
        for k in range(0, TICKS + 1, 5):             # game steps every 5 ticks
            gx = int(k / TICKS * (W - 1)); gd.line([(gx, gy0), (gx, gy1)], fill=(60, 60, 60))
        gd.text((2, GH - 12), "0 s", fill=(140, 140, 140)); gd.text((W - 30, GH - 12), "1 s", fill=(140, 140, 140))
        gd.text((2, 0), "camera x of each drawn frame vs when it was drawn (vertical lines = game steps, 10/s)", fill=(140, 140, 140))
        prev = None
        for e in fr:
            if e["ticks"] > t: break
            gx = int(e.get("cam_ticks", e["ticks"]) / TICKS * (W - 1)); gy = int(gy1 - (e["x"] - x0) / max(1e-6, x1 - x0) * (gy1 - gy0))
            col = (255, 255, 0) if e is cur else (0, 200, 255)
            if prev: gd.line([prev, (gx, gy)], fill=(0, 120, 160))
            gd.rectangle([gx - 2, gy - 2, gx + 2, gy + 2], fill=col); prev = (gx, gy)
        pan.paste(g, (0, CAP + H)); panels.append(pan)
    Wt = sum(p.width for p in panels) + 8 * 2; Ht = panels[0].height + 26
    out = Image.new("RGB", (Wt, Ht), (24, 24, 24)); x = 0
    for p in panels: out.paste(p, (x, 0)); x += p.width + 8
    ImageDraw.Draw(out).text((8, Ht - 20), "M2.9b slow motion: 1 s of game time played at 1/10 speed; every frame each machine drew is shown for its real duration", fill=(200, 200, 200))
    nm = fd / ("f%04d.png" % n); out.save(nm); names.append(nm)
shutil.copyfile(names[-1], ROOT / "build/m29b_slowmo_end.png"); shutil.copyfile(names[len(names) // 2], ROOT / "build/m29b_slowmo_mid.png")
with open(fd / "list.txt", "w") as f:
    for nm in names: f.write("file '%s'\nduration %.4f\n" % (nm.name, 1.0 / FPS))
    f.write("file '%s'\nduration 2.0\n" % names[-1].name)
mp4 = ROOT / "build/m29b_slowmo.mp4"
r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(fd / "list.txt"), "-vf", "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-r", str(FPS), str(mp4)], capture_output=True, text=True)
print("frames per machine:", {m: len(fr) for m, fr in data.items()}, "x range %.2f..%.2f" % (x0, x1))
print("mp4 %s %d bytes, %d video frames, ffmpeg rc %d %s" % (mp4, mp4.stat().st_size if mp4.exists() else 0, len(names), r.returncode, r.stderr.strip()[:200]))
