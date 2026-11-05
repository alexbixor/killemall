#!/usr/bin/env python3
"""m26_stain_shot.py - stills from the REAL rebuilt 48K image: M2.6 blood 3 "floor stain" (3 Nov 2026). Scene as the game loop
runs it (render, game_tick): imp 2.0 cells ahead, slightly left; three shots kill it (hp 30 -> 0); after the 3 BRIGHT red flash
frames the corpse keeps its cells red WITHOUT bright = the floor stain. Then the player walks back 2 steps and turns, to show the
stain stays put and scales with distance. Per frame: oracle diff, counts of bright-red / dim-red / magenta cells, render T.
Output build/m26_stain_real.png (6 frames, 3x) and build/m26_stain_tg.png (3 frames for chat). exit 1 on any oracle diff or if no
dim-red cell survives after the flash."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img
from test_game_sprites import set_player
from test_game_doors import fake_input
from p2e_oracle import engine_expectation, diff, attrs

BRED, DRED, MAG = 0x42, 0x02, 0x43
m = fresh()
set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 1, 5.5, 7.3)
m.set_memory_block(SYM["ammo"], bytes([50])); m.set_memory_block(SYM["fire_cool"], bytes([0]))
frames = []; fails = 0
def frame(label, keys=0, fire=False):
    global fails
    pre = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
    T = call(m, "render", "hud_update")
    a = attrs(m); bad = diff(a, engine_expectation(m, pre=pre))
    scr = bytes(m.memory[16384:16384 + 6912])
    th = bytes(m.memory[SYM["things"]:SYM["things"] + 8])
    n = {k: sum(1 for r in range(12) for c in range(24) if a[r][c] == v) for k, v in (("bright red", BRED), ("dim red", DRED), ("magenta", MAG))}
    info = "hp %d flash-left %d state %d | bright red %d dim red %d magenta %d | oracle diff %d | %d T" % (
        th[6] & 31, th[6] >> 6, th[5], n["bright red"], n["dim red"], n["magenta"], len(bad), T)
    print("%-26s %s" % (label, info)); fails += bool(bad)
    frames.append((label, info, scr_img(scr), n))
    if fire: m.set_memory_block(SYM["fire_cool"], bytes([0]))
    fake_input(m, (0x10 if fire else 0) | keys); call(m, "game_tick")
frame("0 before the shots", fire=True)
frame("1 flash, shot 1", fire=False); frame("2 flash", fire=False); frame("3 flash", fire=False); frame("4 magenta again", fire=True)
frame("1 flash, shot 2", fire=False); frame("2 flash", fire=False); frame("3 flash", fire=False); frame("4 magenta again", fire=True)
frame("1 fatal: corpse flash", fire=False); frame("2 corpse flash", fire=False); frame("3 corpse flash", fire=False)
frame("4 STAIN (dim red corpse)", fire=False)
for i in range(6): frame("stain, walking back %d" % (i + 1), keys=0x02)      # down = back
for i in range(3): frame("stain, turning left %d" % (i + 1), keys=0x04)
frame("stain, final view")
stain_frames = [f for f in frames if f[0].startswith("4 STAIN") or f[0].startswith("stain")]
if any(f[3]["dim red"] == 0 for f in stain_frames): print("FAIL: a stain frame has no dim-red cell"); fails += 1
if any(f[3]["dim red"] for f in frames[:12]): print("FAIL: dim red before the corpse exists"); fails += 1
pick = [0, 9, 12, 14, 18, len(frames) - 1]
S = 3; W = 3
out = Image.new("RGB", (W * (256 * S + 8) + 8, 2 * (192 * S + 44) + 8), (30, 30, 30)); d = ImageDraw.Draw(out)
for k, i in enumerate(pick):
    label, info, im, _ = frames[i]
    x = 8 + (k % W) * (256 * S + 8); y = 4 + (k // W) * (192 * S + 44)
    d.text((x, y), "REAL 48K BUILD, frame " + label, fill=(255, 255, 0)); d.text((x, y + 14), info, fill=(200, 200, 200))
    out.paste(im.resize((256 * S, 192 * S), Image.NEAREST), (x, y + 32))
p = ROOT / "build/m26_stain_real.png"; out.save(p); print(p, out.size)
# chat picture: 3 frames, 2x, window crop rows 0..95 of the screen (the 3D window is the top 12 cell rows) + HUD kept
S = 2; W = 3; caps = {0: "before: imp 2 cells away", 9: "fatal shot: corpse flashes BRIGHT red", 12: "stain: corpse cells red, not bright",
                      18: "walked back 6 steps: stain stays", len(frames) - 1: "turned: stain where it fell"}
pick2 = [9, 12, len(frames) - 1]
out = Image.new("RGB", (W * (256 * S + 6) + 6, 192 * S + 30), (30, 30, 30)); d = ImageDraw.Draw(out)
for k, i in enumerate(pick2):
    label, info, im, _ = frames[i]
    x = 6 + k * (256 * S + 6)
    d.text((x, 4), caps[i], fill=(255, 255, 0))
    out.paste(im.resize((256 * S, 192 * S), Image.NEAREST), (x, 22))
p = ROOT / "build/m26_stain_tg.png"; out.save(p); print(p, out.size, "RESULT", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
