#!/usr/bin/env python3
"""m28_strafe_dbg.py - why does the mock not move on strafe? Call strafe / move_by directly and trace."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m26_colour_mock import fresh, call, clear_things, set_thing, SYM, ROOT
from test_game_sprites import set_player
from test_game_doors import fake_input
from test48 import run_until
from test_game_sprites import TRAP
m = fresh(); set_player(m, 3.5, 7.5, 0); clear_things(m)
def pos():
    px = int.from_bytes(m.memory[SYM["posx"]:SYM["posx"] + 2], "little"); py = int.from_bytes(m.memory[SYM["posy"]:SYM["posy"] + 2], "little")
    return px / 256, py / 256, m.memory[SYM["angle"]]
print("code at game_tick+0x2e..:", m.memory[SYM["game_tick"] + 0x2e: SYM["game_tick"] + 0x44].hex())
print("code at strafe:", m.memory[SYM["strafe"]:SYM["strafe"] + 10].hex(), "in_bits @%04X" % SYM["in_bits"])
# 1. direct: ld a,64 / call strafe / jp TRAP
prog = bytes([0x3E, 64, 0xCD]) + SYM["strafe"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x5E])
m.set_memory_block(0x5EC0, prog); m.pc = 0x5EC0; m.sp = 65008; run_until(m, TRAP)
print("after direct strafe(64):", pos())
# 2. direct move_by with A=64, B=0
prog = bytes([0x06, 0, 0x3E, 64, 0xCD]) + SYM["move_by"].to_bytes(2, "little") + bytes([0xC3, 0xF0, 0x5E])
m.set_memory_block(0x5EC0, prog); m.pc = 0x5EC0; m.sp = 65008; run_until(m, TRAP)
print("after direct move_by(64):", pos())
# 3. MOVXTAB / MOVYTAB entries at heading 64 and 0
for h in (0, 64, 192):
    x = int.from_bytes(m.memory[SYM["MOVXTAB"] + 2 * h: SYM["MOVXTAB"] + 2 * h + 2], "little", signed=True)
    y = int.from_bytes(m.memory[SYM["MOVYTAB"] + 2 * h: SYM["MOVYTAB"] + 2 * h + 2], "little", signed=True)
    print("heading %3d: dx %+d dy %+d (1/256 cell)" % (h, x, y))
# 4. a game_tick with bits 0x80
fake_input(m, 0x80); call(m, "game_tick"); print("after game_tick(0x80):", pos(), "in_bits %02X" % m.memory[SYM["in_bits"]])
fake_input(m, 0x40); call(m, "game_tick"); print("after game_tick(0x40):", pos())
fake_input(m, 0x01); call(m, "game_tick"); print("after game_tick(0x01):", pos())
print("cells around:", [[m.memory[SYM["level_data"] + 1 + 8 + y * 32 + x] for x in range(2, 6)] for y in range(6, 10)])
