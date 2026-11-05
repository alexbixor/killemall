#!/usr/bin/env python3
"""m24_preview.py - render enemy sprites exactly as the engine draws them (Python Z80 core, build/kea48.tap), as a PNG strip:
start corridor, player at (3.5, 7.5) facing east, one thing planted ahead at the given distances, every state (walk A / B,
attack, dead). BUF (16 byte columns x 96 rows) + ATTRWIN -> RGB (Spectrum non-bright palette), x4.
usage: m24_preview.py <out.png> [type=2] [dists=0.9,1.5,2.5]"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf
from test_game_doors import fake_input
from PIL import Image

PAL = {0: (0, 0, 0), 1: (0, 0, 215), 2: (215, 0, 0), 3: (215, 0, 215), 4: (0, 215, 0), 5: (0, 215, 215), 6: (215, 215, 0), 7: (215, 215, 215)}
ATTRWIN = 22568

def frame_rgb(m, scale=4):
    b = buf(m)
    img = Image.new("RGB", (128, 96))
    px = img.load()
    for bc in range(16):
        for r in range(96):
            a = m.memory[ATTRWIN + 32 * (r // 8) + bc]
            ink, paper = PAL[a & 7], PAL[(a >> 3) & 7]
            v = b[bc * 128 + r]
            for bit in range(8):
                px[bc * 8 + bit, r] = ink if v & (0x80 >> bit) else paper
    return img.resize((128 * scale, 96 * scale), Image.NEAREST)

def map_set(m, x, y, code):
    m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/m24_preview.png"
    typ = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    dists = [float(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "0.9,1.5,2.5").split(",")]
    m = machine()
    call(m, "init_game", "render"); fake_input(m, 0)
    for x in range(7, 12): map_set(m, x, 7, 0)
    set_player(m, 3.5, 7.5, 0)
    frames = []
    for state, name in ((0, "walk A"), (1, "walk B"), (2, "attack"), (3, "dead")):
        for d in dists:
            clear_things(m)
            x = 3.5 + d; ix, fx = int(x), int((x - int(x)) * 256)
            m.set_memory_block(SYM["things"], bytes([typ, fx, ix, 128, 7, state, 30, 0]))
            m.set_memory_block(SYM["frames"], bytes([0, 0]))     # walk A/B: chase state picks by frames bit 2
            if state == 1:
                m.set_memory_block(SYM["things"] + 5, bytes([1])); m.set_memory_block(SYM["frames"], bytes([4, 0]))
            call(m, "render")
            frames.append((frame_rgb(m), "%s d=%.1f" % (name, d)))
    n = len(dists)
    W, H = 128 * 4, 96 * 4
    strip = Image.new("RGB", (n * (W + 8) - 8, 4 * (H + 8) - 8), (40, 40, 40))
    for i, (im, lab) in enumerate(frames):
        strip.paste(im, ((i % n) * (W + 8), (i // n) * (H + 8)))
    strip.save(out); print("wrote", out, strip.size, [lab for _, lab in frames])

if __name__ == "__main__":
    main()
