#!/usr/bin/env python3
"""m25e_sprite_cost.py - what does drawing a zombie cost today? Python Z80 core: render T-states at the start view with no things,
then with one zombie (type 2, walk) at 1.0 / 1.5 / 2.5 / 4.0 cells ahead; prints the delta (= the sprite's own blit + vis cost) and
how many ray columns the sprite covers. Basis for the E2 decision: pixel-resolution sprite columns ~3x this delta."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, set_thing, SYM
m = machine()
call(m, "init_game", "hud_init")
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))      # pistol off: the sprite's cost alone
set_player(m, 3.5, 7.5, 0); clear_things(m)
t0 = call(m, "render"); print("no things: render %d T = %.1f fps" % (t0, 3.5e6 / t0))
for d in (1.0, 1.5, 2.5, 4.0):
    set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 2, 3.5 + d, 7.5)
    t = call(m, "render")
    vis = m.memory[SYM["vis"]:SYM["vis"] + 8]
    print("zombie at %.1f cells: render %d T (+%d T = +%.1f%%, fps %.1f); vis bytes %s" % (d, t, t - t0, 100.0 * (t - t0) / t0, 3.5e6 / t, vis.hex()))
