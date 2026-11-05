#!/usr/bin/env python3
"""m26_splat.py - 2 Nov 'Show me now the splatter': blood effect 2 = a splatter SPRITE drawn by the real engine at the hit enemy's
chest for 3 frames (frames 1-2 burst, frame 3 drip), painted BRIGHT red by the cell writer.
Mock mechanics (no source change): the two 16x24 splat frames go through tools/spritec.py (T5 bytes) and tools/gen48.py runs16
(the engine's real run-list format, with the 1-px black halo like the enemies), are written into the free gap above the code
(hi_end 0xFD03.., 237 B minus the 18 B the stack uses), and the two sprite ids this scene does not use (12 barrel, 13 lamp) are
repointed to them, so a thing of type 22 / 23 (decor: no AI, no pickup, shots pass through) IS the splat. It is spawned
0.15 cell nearer the player than the enemy so it sorts after the enemy in the vis list and is drawn on top. The art lives in
rows 7..17 of the 24-row box; an enemy is drawn 0.8 x hv tall and an item hv tall on the same floor line, so box row 12 of
the item sits at the enemy's chest/shoulder for any distance."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from spritec import compile_sprite
from gen48 import runs16
from m26_colour_mock import SYM, set_thing

SPLAT_A = [  # burst: blob with spikes ('#' ink, 'o' opaque black, '.' see-through; runs16 adds the 1-px black halo)
    "................", "................", "................", "................", "................", "................",
    "................",
    "......#.#.......",
    "....#.###.#.....",
    ".....#####......",
    "....#######.....",
    "...#########....",
    "....#######.....",
    ".....#####......",
    "....#.###.#.....",
    "......#.#.......",
    "................",
    "................", "................", "................", "................", "................", "................",
    "................"]
SPLAT_B = [  # drip: smaller blob, drops falling
    "................", "................", "................", "................", "................", "................",
    "................", "................", "................",
    "......#.#.......",
    ".....#####......",
    "....#######.....",
    ".....#####......",
    "......###.......",
    "....#..#..#.....",
    "...##..#..##....",
    "....#..#...#....",
    ".......#........",
    ".......#........",
    "................",
    "................", "................", "................", "................"]
SPLAT_TYPES = (22, 23)          # type 22 -> sprite id 12 (THSPR), 23 -> 13
SPLAT_SLOTS = (8, 9, 10, 11)    # thing slots used for splats (scene uses 0..4)
SPLAT_ATTR = 0x42               # BRIGHT red ink
LIFE = 4                        # 3 rendered frames (burst, burst, drip): the spawn frame's tick eats one count

def encode(rows):
    """art rows -> (bytes in the engine's run-list layout: 16 column offset words + 16 run lists)"""
    W, H, t5 = compile_sprite(12, list(rows), "splat")       # id 12: a 16-wide sprite; T5 = db H + per byte col masks + pixels
    cols = runs16(H, t5[1:], halo_on=True)
    off = 32; body = bytearray(); offs = []
    for c in cols:
        offs.append(off + len(body)); body += bytes(c)
    head = b"".join(bytes([o & 255, o >> 8]) for o in offs)   # offsets relative to the sprite start (fixed below)
    return head, bytes(body)

def install(m, where="decor"):
    """Mock placement. where='decor': overwrite the barrel (spr_12, 154 B of room) and lamp (spr_13, 130 B) run lists in place -
    the scene has no barrel/lamp, and this keeps the stack gap untouched. where='gap': above hi_end (0xFD03.., stack from 0xFDE2).
    Returns [(addr, bytes)] per frame."""
    out = []
    if where == "decor":
        slots = [(SYM["spr_12"], SYM["spr_13"] - SYM["spr_12"]), (SYM["spr_13"], SYM["spr_14"] - SYM["spr_13"])]
    else:
        slots = [(SYM["hi_end"], 110), (SYM["hi_end"] + 110, 0xFDE2 - SYM["hi_end"] - 110)]
    for i, rows in enumerate((SPLAT_A, SPLAT_B)):
        head, body = encode(rows); n = 32 + len(body); addr, room = slots[i]
        assert n <= room, "frame %d needs %d B, only %d B of room at %04X" % (i, n, room, addr)
        offs = [int.from_bytes(head[2 * k:2 * k + 2], "little") for k in range(16)]      # relative to the sprite start
        abs_head = b"".join(bytes([(addr + o) & 255, (addr + o) >> 8]) for o in offs)
        m.set_memory_block(addr, abs_head + body)
        m.set_memory_block(SYM["spr_table"] + 2 * (12 + i), bytes([addr & 255, addr >> 8]))
        out.append((addr, n))
    return out

class Splats:
    def __init__(self): self.live = {}      # slot -> frames left
    def spawn(self, m, ex, ey, px, py):
        free = [s for s in SPLAT_SLOTS if s not in self.live]
        if not free: return None
        slot = free[0]
        d = max(1e-6, ((ex - px) ** 2 + (ey - py) ** 2) ** 0.5); k = min(0.15, d * 0.5) / d
        set_thing(m, slot, SPLAT_TYPES[0], ex + (px - ex) * k, ey + (py - ey) * k)
        self.live[slot] = LIFE
        return slot
    def tick(self, m):
        """call once per rendered frame AFTER the render: burst, burst, drip, gone."""
        for slot in list(self.live):
            self.live[slot] -= 1
            left = self.live[slot]
            if left <= 0: m.set_memory_block(SYM["things"] + 8 * slot, bytes(8)); del self.live[slot]
            elif left == 1: m.set_memory_block(SYM["things"] + 8 * slot, bytes([SPLAT_TYPES[1]]))
    def hide(self, m):
        saved = {s: m.memory[SYM["things"] + 8 * s] for s in self.live}
        for s in saved: m.set_memory_block(SYM["things"] + 8 * s, bytes([0]))
        return saved
    def show(self, m, saved):
        for s, t in saved.items(): m.set_memory_block(SYM["things"] + 8 * s, bytes([t]))

if __name__ == "__main__":
    for rows in (SPLAT_A, SPLAT_B):
        head, body = encode(rows); print("frame bytes:", 32 + len(body))
