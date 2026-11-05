#!/usr/bin/env python3
"""m25b_shots.py (M2.5 step B) - stills of the textured ceiling (dots + mirrored lines) with the per-level tint from the real Z80 code on the Python Z80 core:
cls + hud_init, then for each level 1..3: level block copied into level_data, level byte set, init_game (win_tint), a zombie
planted 1.5 cells ahead, render; the 6912-byte screen is saved as build/m25b_l<N>.png (3x) and a strip
build/m25b_strip.png (full screens side by side, 2x). usage: m25b_shots.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, set_thing
from run48 import scr_to_png
from PIL import Image, ImageDraw

BLOCKS = {1: ROOT / "src/48k/gen/level48.bin", 2: ROOT / "build/level48_02.blk", 3: ROOT / "build/level48_03.blk"}
m = machine()
call(m, "cls", "hud_init")
shots = []
for lvl, blk in BLOCKS.items():
    data = blk.read_bytes(); assert len(data) == 1081 and data[0] == lvl, blk
    m.set_memory_block(SYM["level_data"], data)
    m.set_memory_block(SYM["level"], bytes([lvl - 1]))
    call(m, "init_game")
    sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
    clear_things(m)
    # zombie 1.5 cells ahead along the start heading (angle 0 east, 64 south, 128 west, 192 north)
    dx, dy = {0: (1.5, 0), 64: (0, 1.5), 128: (-1.5, 0), 192: (0, -1.5)}.get(ang, (1.5, 0))
    set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy)
    call(m, "render", "hud_update")
    scr = bytes(m.memory[16384:16384 + 6912])
    ink = m.memory[22568]
    p = ROOT / ("build/m25b_l%d.png" % lvl); scr_to_png(scr, str(p))
    print("level %d start (%d,%d) angle %d: window ink %d -> %s" % (lvl, sx, sy, ang, ink, p.name))
    shots.append((p, "level %d  ink %d" % (lvl, ink)))
imgs = [Image.open(p).resize((512, 384), Image.NEAREST) for p, _ in shots]
strip = Image.new("RGB", (len(imgs) * 512 + (len(imgs) - 1) * 8, 384 + 20), (40, 40, 40))
d = ImageDraw.Draw(strip)
for i, (im, (_, lab)) in enumerate(zip(imgs, shots)):
    strip.paste(im, (i * 520, 20)); d.text((i * 520 + 4, 4), lab, fill=(255, 255, 255))
out = ROOT / "build/m25b_strip.png"; strip.save(out); print("strip", out, strip.size)
