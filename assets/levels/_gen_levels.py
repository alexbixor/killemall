#!/usr/bin/env python3
"""_gen_levels.py - deterministic generator for levels 02 "Barracks" and 03 "Furnace" (lane T5).
Writes assets/levels/02_barracks.txt and 03_furnace.txt in the mapc.py grammar (32x32, header '#start=').
The .txt files are the assets consumed by tools/mapc.py; this script only exists so the layouts are
reproducible and easy to tweak.  Run: .venv/bin/python assets/levels/_gen_levels.py
"""
import pathlib
HERE = pathlib.Path(__file__).parent

class Map:
    def __init__(self):
        self.g = [['#'] * 32 for _ in range(32)]
        self.things = []
    def room(self, x0, y0, x1, y1, tex):
        """carve interior (x0..x1, y0..y1) and paint the surrounding wall ring with texture tex where it is wall"""
        for y in range(y0 - 1, y1 + 2):
            for x in range(x0 - 1, x1 + 2):
                if 0 <= x < 32 and 0 <= y < 32:
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        self.g[y][x] = '.'
                    elif self.g[y][x] not in '.':
                        self.g[y][x] = tex
    def carve(self, x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.g[y][x] = '.'
    def wall(self, x0, y0, x1, y1, tex):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.g[y][x] = tex
    def set(self, x, y, ch):
        assert self.g[y][x] not in '@', (x, y)
        if ch in 'DRUS':
            assert self.g[y][x] != '.', f"door on floor at {x},{y}"
        elif ch == 'X':
            assert self.g[y][x] == '.', f"exit must stand on floor at {x},{y}"   # like 01_entry: exit pad inside the room
        else:
            assert self.g[y][x] == '.', f"thing on wall at {x},{y} ({self.g[y][x]})"
            self.things.append(ch)
        self.g[y][x] = ch
    def text(self, start):
        rows = [''.join(r) for r in self.g]
        assert all(len(r) == 32 for r in rows) and len(rows) == 32
        return f'#start={start}\n' + '\n'.join(rows) + '\n'

def barracks():
    m = Map()
    m.room(12, 13, 19, 18, 'A')          # hub
    m.room(9, 4, 22, 11, 'B')            # north dorm
    m.wall(12, 7, 13, 7, 'B'); m.wall(18, 7, 19, 7, 'B')   # bunk blocks
    m.room(3, 13, 10, 19, 'C')           # west armoury
    m.room(21, 13, 29, 20, 'E')          # east mess hall (blue key)
    m.room(12, 20, 19, 26, 'H')          # south exit room (blue door)
    m.room(5, 21, 7, 23, 'C')            # secret closet under the armoury
    m.carve(24, 6, 28, 8); m.carve(27, 9, 28, 11)          # service corridor dorm -> mess hall
    m.set(15, 12, 'D'); m.set(11, 15, 'D'); m.set(20, 15, 'D'); m.set(15, 19, 'U')
    m.set(23, 7, 'D'); m.set(27, 12, 'D'); m.set(6, 20, 'S'); m.set(15, 24, 'X')
    m.g[15][16] = '@'                                       # start in the hub, facing east (mess hall door)
    for x, y, c in [(11, 5, 'i'), (20, 9, 'i'), (27, 19, 'i'), (23, 14, 'z'), (5, 17, 'z'),
                    (10, 10, 'h'), (6, 22, 'h'), (21, 5, 'a'), (9, 14, 'a'), (22, 20, 'a'),
                    (28, 19, 'u'), (25, 16, 'o'), (3, 19, 'o'), (16, 8, 'l'), (12, 20, 'l')]:
        m.set(x, y, c)
    return m.text('E')

def furnace():
    m = Map()
    m.room(2, 24, 7, 29, 'A')            # start room (stokehold)
    m.carve(8, 27, 23, 28)               # corridor C1 east
    m.room(25, 23, 29, 29, 'C')          # coal store
    m.carve(5, 20, 26, 21)               # corridor C2 west (above the coal store)
    m.carve(5, 18, 5, 19)                # connector up to the guard post door
    m.room(2, 10, 8, 16, 'E')            # guard post (red key)
    m.room(10, 11, 18, 13, 'B')          # corridor C3 east to the red door
    m.room(20, 9, 29, 15, 'F')           # furnace hall (blue key) behind the red door
    m.carve(23, 6, 25, 7)                # stub north of the furnace hall
    m.room(9, 3, 26, 5, 'A')             # corridor C4 west along the top
    m.room(2, 2, 7, 6, 'H')              # exit room behind the blue door
    m.room(2, 21, 3, 22, 'A')            # secret closet 1 above the start room (armour)
    m.room(23, 17, 25, 18, 'F')          # secret closet 2 under the furnace hall (health)
    m.set(24, 27, 'D'); m.set(26, 22, 'D'); m.set(5, 17, 'D'); m.set(9, 12, 'D')
    m.set(19, 12, 'R'); m.set(24, 8, 'D'); m.set(8, 4, 'U')
    m.set(3, 23, 'S'); m.set(24, 16, 'S'); m.set(4, 4, 'X')
    m.g[27][4] = '@'                                        # start facing east down corridor C1
    for x, y, c in [(22, 10, 'i'), (27, 14, 'i'), (6, 15, 'i'), (27, 25, 'i'),
                    (16, 4, 'z'), (5, 12, 'z'), (14, 28, 'z'),
                    (28, 28, 'h'), (24, 17, 'h'), (6, 25, 'a'), (21, 14, 'a'), (12, 5, 'a'),
                    (2, 22, 'm'), (3, 11, 'r'), (28, 10, 'u'), (20, 27, 'o')]:
        m.set(x, y, c)
    return m.text('E')

if __name__ == '__main__':
    for name, fn in (('02_barracks', barracks), ('03_furnace', furnace)):
        t = fn(); (HERE / f'{name}.txt').write_text(t)
        print(name); print(t)
