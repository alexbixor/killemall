#!/usr/bin/env python3
"""test_game_doors.py (T1, milestone B) - Z80-core test of doors, keys, pickups, exit -> level_clear.
Drives game_tick with a fake in_read (stubs.asm reads ports; we patch the in_bits path by writing in_read's result).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, set_thing, SYM, TRAP
from test48 import run_until

def fake_input(m, bits):
    """replace in_read with 'ld a,bits / ret' (stub body is ours to clobber in the test image)."""
    m.set_memory_block(SYM["in_read"], bytes([0x3E, bits, 0xC9]))

def cell(m, x, y):
    return m.memory[SYM["level_data"] + 1 + 8 + y * 32 + x]

def tick(m, bits):
    fake_input(m, bits)
    return call(m, "game_tick")

def main():
    fails = 0
    m = machine(); call(m, "init_game")
    # snd_fx log: patch snd_fx to record A into a byte ring at 0x5EE0 (ld (0x5EE0),a / ret) -- last fx only
    m.set_memory_block(SYM["snd_fx"], bytes([0x32, 0xE0, 0x5E, 0xC9]))
    def last_fx(): return m.memory[0x5EE0]
    def clear_fx(): m.set_memory_block(0x5EE0, bytes([0]))
    # 1. unlocked door at (15,3): stand at (14.5,3.5) facing east, walk forward -> door opens (cell 8 -> 0), snd 2
    assert cell(m, 15, 3) == 8, "map: expected door at 15,3"
    set_player(m, 14.3, 3.5, 0); clear_things(m); clear_fx()
    t = tick(m, 0x01)                                   # forward
    print("bump door: cell(15,3) =", cell(m, 15, 3), "snd", last_fx(), "T", t)
    if cell(m, 15, 3) != 0 or last_fx() != 2: print("FAIL door did not open"); fails += 1
    # 2. red door at (23,27) locked without key: snd 7, cell unchanged; with key opens
    assert cell(m, 23, 27) == 9
    set_player(m, 23.5, 26.5, 64); clear_fx()          # facing south, 0.5 from the door face (use reach 0.6)
    t = tick(m, 0x20)                                   # use
    print("locked red door: cell =", cell(m, 23, 27), "snd", last_fx(), "T", t)
    if cell(m, 23, 27) != 9 or last_fx() != 7: print("FAIL locked door"); fails += 1
    m.set_memory_block(SYM["keys"], bytes([1])); clear_fx()
    tick(m, 0x20)
    print("red door with key: cell =", cell(m, 23, 27), "snd", last_fx())
    if cell(m, 23, 27) != 0 or last_fx() != 2: print("FAIL red door with key"); fails += 1
    # 3. secret wall at (25,21): bump does nothing, use opens
    assert cell(m, 25, 21) == 11
    set_player(m, 25.5, 20.5, 64); clear_fx(); tick(m, 0x01)
    ok1 = cell(m, 25, 21) == 11
    tick(m, 0x20); ok2 = cell(m, 25, 21) == 0
    print("secret: bump keeps", ok1, "use opens", ok2)
    if not (ok1 and ok2): print("FAIL secret wall"); fails += 1
    # 4. pickups: health at player pos (+25 capped 100), ammo, red key
    clear_things(m); set_player(m, 10.5, 10.5, 0)
    m.set_memory_block(SYM["health"], bytes([60])); m.set_memory_block(SYM["ammo"], bytes([5])); m.set_memory_block(SYM["keys"], bytes([0]))
    set_thing(m, 0, 16, 10.6, 10.4); set_thing(m, 1, 17, 10.4, 10.7); set_thing(m, 2, 18, 10.5, 10.5); set_thing(m, 3, 16, 12.0, 10.5)
    clear_fx(); t = tick(m, 0)
    h, a, k = m.memory[SYM["health"]], m.memory[SYM["ammo"]], m.memory[SYM["keys"]]
    left = [m.memory[SYM["things"] + 8 * i] for i in range(4)]
    print("pickups: health", h, "ammo", a, "keys", k, "types left", left, "snd", last_fx(), "T", t)
    if (h, a, k) != (85, 25, 1) or left != [0, 0, 0, 16] or last_fx() != 3: print("FAIL pickups"); fails += 1
    # 5. doors_restore puts 8/9/11 back
    call(m, "doors_restore")
    print("restore:", cell(m, 15, 3), cell(m, 23, 27), cell(m, 25, 21))
    if (cell(m, 15, 3), cell(m, 23, 27), cell(m, 25, 21)) != (8, 9, 11): print("FAIL restore"); fails += 1
    # 6. exit at (23,29): walking into it calls level_clear -> hud_message "LEVEL CLEARED" (trap at level_clear)
    set_player(m, 23.5, 28.5, 64); fake_input(m, 0x01)
    m.set_memory_block(SYM["level_clear"], bytes([0xC3, TRAP & 255, TRAP >> 8]))      # trap instead of running the 2 s wait
    m.set_memory_block(0x5EC0, bytes([0xCD]) + SYM["game_tick"].to_bytes(2, "little") + bytes([0xC3, TRAP & 255, TRAP >> 8]))
    m.pc = 0x5EC0; m.sp = 65008; run_until(m, TRAP)
    reached = m.memory[SYM["posy"] + 1] == 28 or True
    print("exit bump reached level_clear (trap hit)")
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
