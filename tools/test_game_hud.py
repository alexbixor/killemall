#!/usr/bin/env python3
"""test_game_hud.py (T1 milestone D, M2.2 dashboard) - Z80-core test of the dashboard below the 3D window.
Checks (all on the real screen bytes written by the Z80 code, ROM font faked):
  static: red rail y 104 full width, frame top line y 7 x 63..192, frame sides x 63 / x 192 rows 1..12, dividers x 83 /
          x 171 y 105..167, label cells red (AMMO/HEALTH/KEYS/SHIELD/KILLS), pill cells red/blue, bar cells cyan;
          every attribute cell of rows 13..23 is non-bright (bit 6 clear)
  dynamic: health 100 -> bar fully filled (70 px), white cells; 25 -> 17 px fill + checker trough, red cells and value;
           ammo 50 -> 5 lit pips, 0 -> 0, 99 -> 10; shield bar; key pills switch from outline to filled; kills value;
           hud_update redraws only on change (T-states tiny when nothing changed)
  message: hud_message shows on row 22, clears after 100 hud_update calls; weapon graphic in BUF; death path.
exit 0 on success."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, set_thing, SYM, TRAP
from test_game_doors import fake_input
from test48 import run_until

ROMFONT = 15616
def load_font(m):
    # the Python core has no ROM: give it a recognisable fake font (char code pattern) so text rows can be checked
    font = bytes()
    for ch in range(32, 128):
        font += bytes([ch & 0xFF] + [(ch * 3 + i) & 0xFF for i in range(1, 7)] + [0])
    m.set_memory_block(ROMFONT, font)

def pix_addr(y, col):
    return 0x4000 + (y & 0xC0) * 32 + (y & 7) * 256 + (y & 0x38) * 4 + col
def line(m, y, c0=0, n=32):
    return bytes(m.memory[pix_addr(y, c0): pix_addr(y, c0) + n])
def attr(m, row, col, n=1):
    return bytes(m.memory[22528 + 32 * row + col: 22528 + 32 * row + col + n])
def row_text(m, row, col, n):
    base = 0x4000 + ((row & 0x18) << 8) + ((row & 7) << 5)
    return bytes(m.memory[base + col: base + col + n])
def pixel(m, x, y):
    return (m.memory[pix_addr(y, x // 8)] >> (7 - (x & 7))) & 1
def bar_fill(m, y0, x0=88):
    """solid fill width in px: pixels ink on BOTH of the first two fill lines (the checker trough is ink on only one)"""
    n = 0
    while pixel(m, x0 + 1 + n, y0 + 1) and pixel(m, x0 + 1 + n, y0 + 2) and n < 70:
        n += 1
    return n
def fake_digits(m, row, col):
    """value printed with the fake font: byte 0 of each cell = char code"""
    return row_text(m, row, col, 3).decode("latin1")

def main():
    fails = 0
    def check(cond, what):
        nonlocal fails
        if not cond:
            print("FAIL", what); fails += 1
    m = machine(); load_font(m); call(m, "init_game")
    m.set_memory_block(SYM["snd_fx"], bytes([0x32, 0xE0, 0x5E, 0xC9]))
    t = call(m, "hud_init")
    print("hud_init T", t)
    # ---- static geometry
    check(line(m, 104) == bytes([0xFF]) * 32, "rail y 104 full width")
    check(line(m, 7, 3, 26) == bytes([0x01]) + bytes([0xFF]) * 24 + bytes([0x80]), "frame top line y 7 x 31..224 (M2.5C)")
    check(all(pixel(m, 31, y) and pixel(m, 224, y) for y in range(8, 104)), "frame sides x 31 / x 224 rows 8..103")
    check(all(pixel(m, 83, y) and pixel(m, 171, y) for y in range(105, 168)), "dividers x 83 / x 171 y 105..167")
    check(attr(m, 13, 0, 32) == bytes([2]) * 32, "rail cells red")
    check(attr(m, 0, 3, 26) == bytes([2]) * 26, "frame top cells red")
    check(all(attr(m, r, 3) == b"\x02" and attr(m, r, 28) == b"\x02" for r in range(1, 13)), "frame side cells red")
    check(all(attr(m, r, 10) == b"\x02" and attr(m, r, 21) == b"\x02" for r in range(14, 21)), "divider cells red")
    check(attr(m, 14, 0, 4) == b"\x02" * 4 and attr(m, 14, 11, 6) == b"\x02" * 6 and attr(m, 14, 22, 4) == b"\x02" * 4, "row 14 labels red")
    check(attr(m, 18, 11, 6) == b"\x02" * 6 and attr(m, 18, 22, 5) == b"\x02" * 5, "row 18 labels red")
    check(attr(m, 16, 22, 2) == b"\x02\x02" and attr(m, 16, 25, 2) == b"\x01\x01", "pill cells red / blue")
    check(attr(m, 20, 11, 9) == b"\x05" * 9 and attr(m, 21, 11, 9) == b"\x05" * 9, "shield bar cells cyan")
    check(attr(m, 17, 0, 10) == b"\x06" * 10, "pip case cells yellow")
    allattr = bytes(m.memory[22528 + 13 * 32: 22528 + 24 * 32])
    check(not any(a & 0x40 for a in allattr), "no BRIGHT in rows 13..23")
    # bold print: byte0 of the fake font = char code c -> printed c | c >> 1
    def bold(c): return bytes([c | (c >> 1)])
    check(row_text(m, 14, 0, 1) == bold(ord("A")) and row_text(m, 14, 11, 1) == bold(ord("H")) and row_text(m, 14, 22, 1) == bold(ord("K")), "row 14 labels AMMO/HEALTH/KEYS")
    check(row_text(m, 18, 11, 1) == bold(ord("S")) and row_text(m, 18, 22, 1) == bold(ord("K")), "row 18 labels SHIELD/KILLS")
    check(row_text(m, 19, 0, 1) == bold(ord("P")), "weapon name PISTOL row 19")
    # ---- dynamic: initial values health 100 ammo 50 keys 0 kills 0 shield 0
    f100 = bar_fill(m, 128)
    print("health bar fill at 100:", f100, "px; cells", attr(m, 16, 11, 9).hex(), "value", fake_digits(m, 14, 18))
    check(f100 == 70, "health 100 -> 70 px fill")
    check(attr(m, 16, 11, 9) == b"\x07" * 9 and attr(m, 17, 11, 9) == b"\x07" * 9 and attr(m, 14, 18, 3) == b"\x07" * 3, "health 100 -> white bar/value cells")
    check(fake_digits(m, 14, 18) == "100", "health value 100")
    check(fake_digits(m, 18, 18) == "000" and bar_fill(m, 160) == 0, "shield 0 -> value 000, empty bar")
    check(pixel(m, 89, 161) or pixel(m, 90, 161), "shield empty bar shows the checker trough")
    check(row_text(m, 14, 8, 2) == b"50", "ammo value 50")
    def lit_pips(mm):
        # pip k at col k: full case row y 137 = 0x7C (all 5 px), empty case = 0x44 (sides only)
        return sum(1 for k in range(10) if mm.memory[pix_addr(137, k)] == 0x7C)
    def pip_rows_ok(mm):
        return all(mm.memory[pix_addr(136, k)] == 0x7C and mm.memory[pix_addr(142, k)] == 0x7C and mm.memory[pix_addr(130, k)] == 0x10 for k in range(10))
    print("pips lit at ammo 50:", lit_pips(m), "| frames ok", pip_rows_ok(m))
    check(lit_pips(m) == 5 and pip_rows_ok(m), "ammo 50 -> 5 lit pips, 10 drawn")
    # pills: both outline (keys 0) -> row 3 of pill R (y 131) has gaps inside
    pr = bytes(m.memory[pix_addr(128, 22): pix_addr(128, 22) + 2]); check(pr == bytes([63, 252]), "pill R top row")
    held_before = bytes(m.memory[pix_addr(131, 22): pix_addr(131, 22) + 2])
    check(fake_digits(m, 18, 28) == "000", "kills 000")
    t_same = call(m, "hud_update"); print("hud_update (no change) T", t_same)
    check(t_same < 400, "hud_update without changes stays cheap")
    # ---- changes
    m.set_memory_block(SYM["health"], bytes([25])); m.set_memory_block(SYM["ammo"], bytes([0])); m.set_memory_block(SYM["keys"], bytes([3]))
    m.set_memory_block(SYM["kills"], bytes([7])); m.set_memory_block(SYM["shield"], bytes([50]))
    t_ch = call(m, "hud_update"); print("hud_update (all changed) T", t_ch)
    f25 = bar_fill(m, 128)
    print("health 25: fill", f25, "px, cells", attr(m, 16, 11, 9).hex(), "value", fake_digits(m, 14, 18), "| shield 50 fill", bar_fill(m, 160), "value", fake_digits(m, 18, 18))
    check(f25 == 17, "health 25 -> 17 px")
    check(attr(m, 16, 11, 9) == b"\x02" * 9 and attr(m, 14, 18, 3) == b"\x02" * 3, "health <= 33 -> red bar and value")
    check(fake_digits(m, 14, 18) == "025", "health value 025")
    check(pixel(m, 88 + 1 + 17 + 1, 129) ^ pixel(m, 88 + 1 + 17 + 2, 129) == 1, "checker trough after the fill (alternating)")
    check(bar_fill(m, 160) == 35 and fake_digits(m, 18, 18) == "050", "shield 50 -> 35 px, value 050")
    check(lit_pips(m) == 0 and pip_rows_ok(m), "ammo 0 -> no lit pips, outlines drawn")
    check(row_text(m, 14, 8, 2) == b"00", "ammo value 00")
    held_after = bytes(m.memory[pix_addr(131, 22): pix_addr(131, 22) + 2])
    # held pill: row 3 (y 131) = full rounded body with the black letter cut out: left 5 px solid (0xF8 mask)
    check(held_after != held_before and held_after[0] & 0xF8 == 0xF8 and held_before[0] & 0x78 == 0, "pill R switched from outline to held")
    check(bytes(m.memory[pix_addr(128, 25): pix_addr(128, 25) + 2]) == bytes([63, 252]), "pill B drawn")
    check(fake_digits(m, 18, 28) == "007", "kills 007")
    m.set_memory_block(SYM["ammo"], bytes([99])); call(m, "hud_update")
    check(lit_pips(m) == 10, "ammo 99 -> 10 lit pips")
    m.set_memory_block(SYM["ammo"], bytes([41])); call(m, "hud_update")
    check(lit_pips(m) == 5, "ammo 41 -> 5 lit pips")
    # frame/edges untouched by the instruments
    check(all(pixel(m, 83, y) and pixel(m, 171, y) for y in range(105, 168)), "dividers intact after updates")
    check(line(m, 104) == bytes([0xFF]) * 32, "rail intact after updates")
    # ---- message line row 22
    m.set_memory_block(0x5EC0, bytes([0x21]) + SYM["msg_key"].to_bytes(2, "little") + bytes([0xCD]) + SYM["hud_message"].to_bytes(2, "little") + bytes([0xC3, TRAP & 255, TRAP >> 8]))
    m.pc = 0x5EC0; m.sp = 65008; t_msg = run_until(m, TRAP)
    r22 = row_text(m, 22, 2, 10)
    print("hud_message T", t_msg, "row22", r22.decode("latin1"))
    check(r22 == b"NEED A KEY", "message on row 22")
    for _ in range(99): call(m, "hud_update")
    still = row_text(m, 22, 2, 4); call(m, "hud_update"); gone = row_text(m, 22, 2, 4)
    check(still == b"NEED" and gone == b"    ", "message auto-clear after 100 updates")
    # ---- weapon graphic: render -> BUF byte columns 6..9 rows 72..95 contain the pistol (non-zero, differs between idle/fire)
    set_player(m, 3.5, 7.5, 0); clear_things(m)
    W = 0x6100 + 10 * 96                                      # M2.5C: weapon at BUF byte columns 10..13, stride 96
    call(m, "render"); idle = bytes(m.memory[W + 72: W + 96]) + bytes(m.memory[W + 96 + 72: W + 96 + 96])
    m.set_memory_block(SYM["weapon_frame"], bytes([1])); t_w = call(m, "draw_weapon")
    fire = bytes(m.memory[W + 72: W + 96]) + bytes(m.memory[W + 96 + 72: W + 96 + 96])
    print("draw_weapon T", t_w, "idle bytes nonzero", sum(1 for b in idle if b), "fire differs", idle != fire)
    check(idle != fire and any(idle), "weapon graphic")
    # ---- shield absorbs damage: et_attack on an imp (type 1, damage 10) with its timer at 24 -> the hit lands this call.
    #      shield 30, health 100 -> shield 20, health 100. Then shield 0 -> health 90 (the shield path is really taken).
    TH = SYM["things"]
    m.set_memory_block(TH, bytes([1, 0, 0, 0, 0, 2, 0, 24]))        # type 1 imp, state 2 attack, timer 24
    m.set_memory_block(SYM["shield"], bytes([30])); m.set_memory_block(SYM["health"], bytes([100]))
    m.set_memory_block(0x5EC0, bytes([0xDD, 0x21]) + TH.to_bytes(2, "little") + bytes([0xCD]) + SYM["et_attack"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x00]))
    m.pc = 0x5EC0; m.sp = 65008; run_until(m, 0x0000)
    sh, hp = m.memory[SYM["shield"]], m.memory[SYM["health"]]
    print("shield hit: shield 30 -> %d, health 100 -> %d" % (sh, hp))
    check(sh == 20 and hp == 100, "shield absorbs the imp hit (shield 20, health 100)")
    m.set_memory_block(TH + 7, bytes([24])); m.set_memory_block(SYM["shield"], bytes([0]))
    m.pc = 0x5EC0; m.sp = 65008; run_until(m, 0x0000)
    sh, hp = m.memory[SYM["shield"]], m.memory[SYM["health"]]
    print("no shield: shield %d, health 100 -> %d" % (sh, hp))
    check(sh == 0 and hp == 90, "without shield the imp hit reaches health (90)")
    m.set_memory_block(TH, bytes(8))
    # ---- death: health 0 -> game_tick reaches player_dead (trap it)
    m.set_memory_block(SYM["health"], bytes([0])); fake_input(m, 0)
    m.set_memory_block(SYM["player_dead"], bytes([0xC3, TRAP & 255, TRAP >> 8]))
    m.set_memory_block(0x5EC0, bytes([0xCD]) + SYM["game_tick"].to_bytes(2, "little") + bytes([0xC3, 0x00, 0x00]))
    m.pc = 0x5EC0; m.sp = 65008; run_until(m, TRAP); print("health 0 -> player_dead reached")
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
