#!/usr/bin/env python3
"""m26_loop_cost.py - cycle-exact cost of ONE main-loop iteration at the start view (Python Z80 core, no ISR):
render (rays + CLRBUF + bands + sprites + COPYBUF) and game_tick separately, plus the ISR body once, for the 48K image
and (KEA128=1) the 128K image. Also the COPYBUF part alone (render with COPYBUF stubbed to ret) so the shadow-flip
saving is a measured number, not a guess."""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test48
from test_game_sprites import machine, call, set_player, clear_things, SYM
m = machine()
if os.environ.get("KEA128"):
    b1 = (test48.ROOT / "build/bank1.bin").read_bytes()
    banks = {0: bytes(m.memory[0xC000:0x10000]), 1: b1 + bytes(16384 - len(b1))}; cur = [0]
    def on_out(port, val):
        if port == 0x7FFD and (val & 7) != cur[0]:
            banks[cur[0]] = bytes(m.memory[0xC000:0x10000]); m.set_memory_block(0xC000, banks[val & 7]); cur[0] = val & 7
    m.set_output_callback(on_out); m.set_input_callback(lambda p: 0xFF)
    call(m, "bank_init")
call(m, "init_game", "hud_init")
set_player(m, 3.5, 7.5, 0)
tag = "128K" if os.environ.get("KEA128") else "48K"
t_r = call(m, "render")
t_r2 = call(m, "render")
t_g = call(m, "game_tick")
t_i = call(m, "isr")
print("%s start view (live level things): render %d T (2nd %d), game_tick %d T, isr %d T -> loop %d T = %.2f fps core, %.1f frames of 69,888 T" % (
    tag, t_r, t_r2, t_g, t_i, t_r2 + t_g, 3.5e6 / (t_r2 + t_g), (t_r2 + t_g) / 69888.0))
# COPYBUF alone: stub it (render ends with jp COPYBUF -> ret at COPYBUF)
save = bytes(m.memory[SYM["COPYBUF"]:SYM["COPYBUF"] + 1])
m.set_memory_block(SYM["COPYBUF"], bytes([0xC9]))
t_nc = call(m, "render")
m.set_memory_block(SYM["COPYBUF"], save)
print("%s render without COPYBUF %d T -> COPYBUF = %d T (%.1f%% of render)" % (tag, t_nc, t_r2 - t_nc, 100.0 * (t_r2 - t_nc) / t_r2))
clear_things(m)
t_n = call(m, "render")
print("%s render with no things %d T" % (tag, t_n))
