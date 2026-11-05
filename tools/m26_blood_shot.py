#!/usr/bin/env python3
"""m26_blood_shot.py - stills from the REAL rebuilt 48K image (build/kea48.tap): blood 1 red flash + muzzle flash (3 Nov 2026).
Sequence exactly as the game loop runs it (main: render, game_tick): imp 2.5 cells ahead; frame 0 = before the shot; the fire key
is held for one game_tick (pistol hitscan: hp 30 -> 20, flash counter 3; weapon_frame = 1 for 5 frames); frames 1..3 = imp cells
BRIGHT red + muzzle cells BRIGHT yellow; frame 4 = imp magenta again, muzzle still lit; frame 6 = muzzle off. Then two more
shots kill it: the corpse flashes red for 3 frames and turns white (window ink). Per frame: oracle diff (tools/p2e_oracle.py with
the pre-render things table), the counts of red / magenta / yellow cells, render T-states. Output build/m26_blood_real.png (3x).
exit 1 if any oracle diff != 0 or the red/white sequence is not 0,3,3,3,0 / 3,3,3,0."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img
from test_game_sprites import set_player
from test_game_doors import fake_input
from p2e_oracle import engine_expectation, diff, attrs

RED, MAG, YEL = 0x42, 0x43, 0x46
m = fresh()
set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 1, 6.0, 7.5)
m.set_memory_block(SYM["ammo"], bytes([50])); m.set_memory_block(SYM["fire_cool"], bytes([0]))
frames = []; fails = 0
def frame(label, fire):
    global fails
    pre = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
    T = call(m, "render", "hud_update")
    a = attrs(m); bad = diff(a, engine_expectation(m, pre=pre))
    scr = bytes(m.memory[16384:16384 + 6912])
    th = bytes(m.memory[SYM["things"]:SYM["things"] + 8])
    n = {k: sum(1 for r in range(12) for c in range(24) if a[r][c] == v) for k, v in (("red", RED), ("magenta", MAG), ("yellow", YEL))}
    info = "hp %d flash-left %d state %d wf %d | red %d magenta %d yellow %d | oracle diff %d | %d T" % (
        th[6] & 31, th[6] >> 6, th[5], m.memory[SYM["weapon_frame"]], n["red"], n["magenta"], n["yellow"], len(bad), T)
    print("%-28s %s" % (label, info)); fails += bool(bad)
    frames.append((label, info, scr_img(scr), n))
    if fire: m.set_memory_block(SYM["fire_cool"], bytes([0]))     # this shot is allowed at once; the natural 12-frame countdown follows
    fake_input(m, 0x10 if fire else 0); call(m, "game_tick")
frame("0 before the shot", fire=True)
for i in (1, 2, 3, 4, 5): frame("%d after shot 1" % i, fire=False)
frame("6 muzzle off", fire=True)                 # shot 2: hp 20 -> 10
for i in (1, 2, 3): frame("%d after shot 2" % i, fire=False)
frame("4 after shot 2", fire=True)               # shot 3: fatal -> corpse, flash 3
for i in (1, 2, 3, 4): frame("%d after fatal shot" % i, fire=False)
seq = [f[3]["red"] > 0 for f in frames]
want = [False, True, True, True, False, False, False, True, True, True, False, True, True, True, False]
print("red-flash sequence:", "".join("R" if s else "." for s in seq), "expected", "".join("R" if s else "." for s in want))
if seq != want: print("FAIL red flash sequence"); fails += 1
if any(f[3]["yellow"] != 2 for f in frames[1:6]) or frames[6][3]["yellow"] != 0: print("FAIL muzzle (frames 1..5 lit, 6 off)"); fails += 1
pick = [0, 1, 3, 4, 6, 11, 12, 14]
S = 3; W = 4
out = Image.new("RGB", (W * (256 * S + 8) + 8, 2 * (192 * S + 44) + 8), (30, 30, 30)); d = ImageDraw.Draw(out)
for k, i in enumerate(pick):
    label, info, im, _ = frames[i]
    x = 8 + (k % W) * (256 * S + 8); y = 4 + (k // W) * (192 * S + 44)
    d.text((x, y), "REAL 48K BUILD, frame " + label, fill=(255, 255, 0)); d.text((x, y + 14), info, fill=(200, 200, 200))
    out.paste(im.resize((256 * S, 192 * S), Image.NEAREST), (x, y + 32))
p = ROOT / "build/m26_blood_real.png"; out.save(p); print(p, out.size, "RESULT", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
