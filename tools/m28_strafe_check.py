#!/usr/bin/env python3
"""m28_strafe_check.py - M2.8 strafe: direction + behaviour check on the REAL rebuilt 48K image (mock harness, 3 Nov 2026).
Scene: player at (3.5, 7.5) facing angle 0; an imp 2 cells ahead and 0.9 cell to one side. Each tick: render, read the imp's
screen position (mean byte column of its magenta cells in the 24-column window), posx/posy/angle/fl_ph. Holding X (strafe
right, b7) must (1) keep the angle, (2) move the player sideways (posy only at angle 0), (3) leave fl_ph alone, and (4) move
an imp that is on the RIGHT half of the screen toward the centre (we slide toward its side). Z (b6) = the mirror image.
exit 1 on any failed check. Output build/m28_strafe_check.out + build/m28_strafe_tg.png (3 frames: before, after X x6, after Z x6)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT, scr_img
from test_game_sprites import set_player
from test_game_doors import fake_input
from p2e_oracle import attrs
MAG = 0x43
out = open(ROOT / "build/m28_strafe_check.out", "w")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); out.write(s + "\n"); out.flush()
fails = 0
def check(ok, msg):
    global fails
    log(("PASS " if ok else "FAIL ") + msg); fails += 0 if ok else 1
def state():
    px = int.from_bytes(m.memory[SYM["posx"]:SYM["posx"] + 2], "little") / 256
    py = int.from_bytes(m.memory[SYM["posy"]:SYM["posy"] + 2], "little") / 256
    return px, py, m.memory[SYM["angle"]], m.memory[SYM["fl_ph"]]
def imp_col():
    a = attrs(m); cols = [c for r in range(12) for c in range(24) if a[r][c] == MAG]
    return (sum(cols) / len(cols) if cols else None), len(cols)
frames = []
def run(label, bits, n):
    for i in range(n):
        call(m, "render", "hud_update")
        fake_input(m, bits); call(m, "game_tick")
    call(m, "render", "hud_update")
    col, ncell = imp_col(); px, py, an, ph = state()
    log("%-22s pos (%.3f, %.3f) angle %d fl_ph %d | imp mean col %s (%d cells)" % (label, px, py, an, ph, "%.1f" % col if col is not None else "off-screen", ncell))
    frames.append((label, scr_img(bytes(m.memory[16384:16384 + 6912]))))
    return col, (px, py, an, ph)

# which side of the screen is +y at angle 0?
m = fresh(); set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 1, 5.5, 8.4)
col0, s0 = run("imp at y+0.9 (start)", 0, 0)
side = "right" if col0 is not None and col0 > 11.5 else "left"
log("at angle 0 an imp with +y offset appears on the %s half of the screen (mean col %.1f of 0..23)" % (side, col0))
# strafe toward it: if it is on the right, X (b7) must bring it toward the centre and move posy toward 8.4
bits_toward, key_toward = (0x80, "X (strafe right)") if side == "right" else (0x40, "Z (strafe left)")
col1, s1 = run("hold %s x6" % key_toward, bits_toward, 6)
check(s1[2] == s0[2], "angle unchanged while strafing (%d -> %d)" % (s0[2], s1[2]))
check(abs(s1[0] - s0[0]) < 0.01 and abs(s1[1] - s0[1]) > 0.5, "sideways move only: posx %.3f -> %.3f, posy %.3f -> %.3f (6 x 0.15 = 0.9 expected)" % (s0[0], s1[0], s0[1], s1[1]))
check(s1[3] == s0[3], "floor line phase untouched by strafing (fl_ph %d -> %d)" % (s0[3], s1[3]))
check(col1 is not None and abs(col1 - 11.5) < abs(col0 - 11.5), "imp on the %s moved toward the screen centre under %s (col %.1f -> %s)" % (side, key_toward, col0, col1))
check((s1[1] > s0[1]) == (8.4 > 7.5), "player slid toward the imp's side (posy %.3f -> %.3f, imp at 8.4)" % (s0[1], s1[1]))
# and back the other way, past the start: the imp moves to the far side
bits_away = 0xC0 ^ bits_toward; key_away = "Z (strafe left)" if bits_toward == 0x80 else "X (strafe right)"
col2, s2 = run("hold %s x12" % key_away, bits_away, 12)
check(s2[2] == s0[2], "angle still unchanged (%d)" % s2[2])
check(abs(s2[1] - (2 * s0[1] - s1[1])) < 0.02, "mirror slide: posy %.3f (expected %.3f)" % (s2[1], 2 * s0[1] - s1[1]))
check(col2 is None or abs(col2 - 11.5) > abs(col0 - 11.5), "imp moved away from the centre under %s (col %.1f -> %s)" % (key_away, col0, col2))
# both at once cancel out
col3, s3 = run("hold Z+X x4", 0xC0, 4)
check(abs(s3[1] - s2[1]) < 0.01 and abs(s3[0] - s2[0]) < 0.01, "Z+X together: no net movement (%.3f, %.3f)" % (s3[0], s3[1]))
# collision: strafe into a wall must stop, not pass through (walk sideways 40 ticks)
col4, s4 = run("hold %s x40 (wall)" % key_away, bits_away, 40)
from test_game_doors import cell
check(cell(m, int(s4[0]), int(s4[1])) == 0, "player cell stays open after sliding into the wall: pos (%.3f, %.3f)" % (s4[0], s4[1]))
# picture
W, H = 256 * 2, 192 * 2
im = Image.new("RGB", (3 * W + 16, H + 24), (20, 20, 20)); d = ImageDraw.Draw(im)
for i, (label, f) in enumerate(frames[:3]):
    d.text((4 + i * (W + 4), 4), label, fill=(255, 255, 255)); im.paste(f.resize((W, H), Image.NEAREST), (4 + i * (W + 4), 20))
im.save(ROOT / "build/m28_strafe_tg.png")
log("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
