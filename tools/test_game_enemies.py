#!/usr/bin/env python3
"""test_game_enemies.py (T1, milestone C) - Z80-core test: chase, attack damage, pistol hitscan kill, ammo, kills."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, set_thing, SYM
from test_game_doors import fake_input

def thing(m, i):
    r = bytes(m.memory[SYM["things"] + 8 * i: SYM["things"] + 8 * i + 8])
    return dict(type=r[0], x=r[2] + r[1] / 256, y=r[4] + r[3] / 256, state=r[5], hp=r[6] & 31, flash=r[6] >> 6, t=r[7])

def main():
    fails = 0
    m = machine(); call(m, "init_game")
    m.set_memory_block(SYM["snd_fx"], bytes([0x32, 0xE0, 0x5E, 0xC9]))        # log last fx at 0x5EE0
    fx = lambda: m.memory[0x5EE0]
    # 1. imp 3 cells east with LOS -> chases: x decreases over 10 ticks
    clear_things(m); set_player(m, 3.5, 7.5, 0); set_thing(m, 0, 1, 6.5, 7.5)
    fake_input(m, 0)
    x0 = thing(m, 0)["x"]
    t = call(m, "game_tick")
    for _ in range(9): call(m, "game_tick")
    th = thing(m, 0)
    print("chase: x %.2f -> %.2f state %d  game_tick T %d" % (x0, th["x"], th["state"], t))
    if not (th["state"] == 1 and th["x"] < x0 - 0.5): print("FAIL chase"); fails += 1
    # 2. imp behind the wall (x = 8.5, wall at x = 7) -> stays idle
    clear_things(m); set_thing(m, 0, 1, 8.5, 7.5)
    for _ in range(5): call(m, "game_tick")
    th = thing(m, 0); print("no LOS: state", th["state"], "x %.2f" % th["x"])
    if th["state"] != 0 or abs(th["x"] - 8.5) > 0.01: print("FAIL LOS"); fails += 1
    # 3. zombie adjacent -> attack after 25 frames: health 100 -> 85, snd 4
    clear_things(m); set_thing(m, 1, 2, 4.0, 7.5); m.set_memory_block(SYM["health"], bytes([100])); m.set_memory_block(0x5EE0, bytes([0]))
    for _ in range(26): call(m, "game_tick")
    h = m.memory[SYM["health"]]; print("zombie attack: health", h, "state", thing(m, 1)["state"], "last snd", fx())
    if h != 85 or fx() != 4: print("FAIL attack"); fails += 1
    # 4. pistol: imp straight ahead at 2.5 cells, render (vis list) then fire x3 -> dead, kills 1, ammo 47, snd 5
    clear_things(m); set_thing(m, 0, 1, 6.0, 7.5); m.set_memory_block(SYM["ammo"], bytes([50])); m.set_memory_block(SYM["kills"], bytes([0]))
    m.set_memory_block(SYM["fire_cool"], bytes([0]))
    for shot in range(3):
        call(m, "render"); fake_input(m, 0x10); t_fire = call(m, "game_tick")
        m.set_memory_block(SYM["fire_cool"], bytes([0]))
        th = thing(m, 0); print(" shot %d: hp %d state %d ammo %d snd %d (tick T %d)" % (shot + 1, th["hp"], th["state"], m.memory[SYM["ammo"]], fx(), t_fire))
    th = thing(m, 0)
    if not (th["state"] == 3 and m.memory[SYM["kills"]] == 1 and m.memory[SYM["ammo"]] == 47 and fx() == 5): print("FAIL pistol"); fails += 1
    # 5. shot misses an imp off-centre (2 cells left of the ray) and does not fire with ammo 0
    clear_things(m); set_thing(m, 0, 1, 6.0, 5.5); call(m, "render"); fake_input(m, 0x10); call(m, "game_tick")
    th = thing(m, 0); print("off-centre: hp", th["hp"], "ammo", m.memory[SYM["ammo"]])
    if th["hp"] != 30: print("FAIL off-centre hit"); fails += 1
    m.set_memory_block(SYM["ammo"], bytes([0])); m.set_memory_block(SYM["fire_cool"], bytes([0])); m.set_memory_block(0x5EE0, bytes([0]))
    call(m, "game_tick"); print("ammo 0: snd", fx(), "(must be 0)")
    if fx() != 0: print("FAIL fired without ammo"); fails += 1
    # 6. frame cost with an imp chasing in view (2 sprites: imp + barrel)
    clear_things(m); set_thing(m, 0, 1, 5.5, 7.5); set_thing(m, 1, 21, 6.0, 8.2); fake_input(m, 0)
    t = call(m, "render") + call(m, "game_tick")
    print("render+tick with imp + barrel: T %d -> %.1f fps" % (t, 3_500_000 / t))
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
