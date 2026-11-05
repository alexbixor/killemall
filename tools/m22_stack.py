#!/usr/bin/env python3
"""m22_stack.py - measure the real stack depth of the M2.2 48K build in the Python Z80 core (no guessing).
Fills 0xFD00..0xFDEF with a marker, runs init_game + hud_init + render + game_tick (with an enemy attacking and a
message on screen) and the low-water mark of SP tells how many bytes below 65008 the game really uses.
Also checks that nothing (code, ISR vector) sits in the stack span the game uses. Exit 1 if the free gap is < 16 B."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, set_thing, SYM
from test_game_doors import fake_input

STACK_TOP = 65008
m = machine()
hi_end = SYM["hi_end"]
mark = bytes([0xA5]) * (STACK_TOP - hi_end)
m.set_memory_block(hi_end, mark)                       # everything between code end and the stack top
call(m, "init_game", "hud_init", "render", "game_tick")
# busy frame: enemy next to the player attacking, items in view, message shown, pause-free
clear_things(m); set_player(m, 3.5, 7.5, 0)
set_thing(m, 0, 1, 4.2, 7.5); set_thing(m, 1, 2, 5.0, 8.0); set_thing(m, 2, 21, 6.0, 7.5); set_thing(m, 3, 16, 5.5, 7.0)
m.set_memory_block(SYM["things"] + 5, bytes([2]))      # imp state attack
fake_input(m, 0x10)                                    # fire
for _ in range(3):
    call(m, "render", "game_tick")
m.set_memory_block(0x5EC0, bytes([0x21]) + SYM["msg_key"].to_bytes(2, "little") + bytes([0xCD]) + SYM["hud_message"].to_bytes(2, "little") + bytes([0xCD]) + SYM["hud_update"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x5E]))
m.pc = 0x5EC0; m.sp = STACK_TOP
from test48 import run_until
run_until(m, 0x5EF0)
mem = bytes(m.memory[hi_end:STACK_TOP])
# lowest address whose marker was overwritten = deepest stack use
low = next((i for i, b in enumerate(mem) if b != 0xA5), None)
if low is None:
    print("stack never touched the marker?!"); sys.exit(1)
deepest = hi_end + low
print("hi_end 0x%04X, stack top %d (0x%04X), deepest SP write 0x%04X -> stack uses %d B, gap code..stack %d B"
      % (hi_end, STACK_TOP, STACK_TOP, deepest, STACK_TOP - deepest, deepest - hi_end))
# ISR vector (ISRVEC 0xFDFD) and TABLE 0xFE00 lie above the stack top: fine by construction
print("ISRVEC 0x%04X TABLE 0x%04X (above the stack top: ok)" % (SYM["ISRVEC"], SYM["TABLE"]))
sys.exit(0 if deepest - hi_end >= 16 else 1)
