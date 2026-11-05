#!/usr/bin/env python3
"""_gen_levels.py - deterministic generator for levels 02 "Barracks" and 03 "Furnace" (lane T5)
and, since 5 Nov 2026 (lane L), levels 04 "Crypt" .. 08 "Throne" for the 128K and Next editions.
Writes assets/levels/NN_name.txt in the mapc.py grammar (32x32, header '#start=').
The .txt files are the assets consumed by tools/mapc.py; this script only exists so the layouts are
reproducible and easy to tweak.  Run: .venv/bin/python assets/levels/_gen_levels.py
Everything is hand-tuned coordinates - no random numbers anywhere, so the output is byte-identical on
every run.  02 and 03 are untouched by lane L (their functions are verbatim; diff proves it).
Check the result with: .venv/bin/python tools/levelcheck.py --png build/levels_NN.png assets/levels/0?_*.txt
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
    # ---- helpers added by lane L (not used by 02/03) ----
    def paint(self, x0, y0, x1, y1, tex):
        """re-texture plain '#' wall cells inside the rect that border a floor cell (corridor walls get a look)"""
        for y in range(max(y0, 0), min(y1, 31) + 1):
            for x in range(max(x0, 0), min(x1, 31) + 1):
                if self.g[y][x] == '#' and any(0 <= x + dx < 32 and 0 <= y + dy < 32 and self.g[y + dy][x + dx] == '.'
                                               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.g[y][x] = tex
    def start(self, x, y):
        assert self.g[y][x] == '.', f"start on wall at {x},{y}"
        self.g[y][x] = '@'
    def put(self, items):
        for x, y, c in items:
            self.set(x, y, c)

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

# ----------------------------------------------------------------------------------------------------
# Lane L, 5 Nov 2026: levels 04..08 (128K / Next only: <= 6 enemy types, <= 48 things).
# Enemy counts 8, 10, 12, 14, 16.  Textures: A stone, B brick, C iron, E blue stone, F moss, G crumbling, H vines.

def crypt():
    """04 - narrow 1-wide corridors in a cross, 12 doors, first shotgunners, red key in the north chapel,
    red door to the exit vault in the south, 1 secret closet (armour) above the start vestibule."""
    m = Map()
    m.room(2, 14, 5, 16, 'A')            # start vestibule (west end of the spine)
    m.room(2, 11, 3, 12, 'A')            # secret closet above the vestibule (armour)
    m.carve(6, 15, 26, 15)               # spine corridor east to the transept
    m.carve(26, 6, 26, 9); m.carve(26, 11, 26, 19); m.carve(26, 21, 26, 25)  # transept, two doors across it
    m.carve(19, 8, 24, 8)                # north alcove off the transept (ammo), door at (25, 8)
    m.carve(19, 22, 24, 22)              # south alcove off the transept (health), door at (25, 22)
    for x in (9, 15, 21):
        m.room(x, 11, x + 2, 13, 'G')    # north burial chambers, doors onto the spine
        m.room(x, 17, x + 2, 19, 'G')    # south burial chambers
    m.room(23, 2, 29, 4, 'H')            # red-key chapel at the north end
    m.room(23, 27, 29, 29, 'H')          # exit vault at the south end, behind the red door
    m.paint(5, 5, 27, 26, 'A')           # corridor walls: stone
    for x in (10, 16, 22):
        m.set(x, 14, 'D'); m.set(x, 16, 'D')
    m.set(26, 5, 'D'); m.set(26, 10, 'D'); m.set(26, 20, 'D'); m.set(25, 8, 'D'); m.set(25, 22, 'D'); m.set(26, 26, 'R')
    m.set(3, 13, 'S'); m.set(26, 28, 'X')
    m.start(3, 15)                                           # facing east down the spine
    m.put([(12, 15, 'i'), (26, 11, 'i'), (26, 19, 'i'),                 # imps in the corridors
           (16, 12, 'z'), (25, 3, 'z'),                                 # zombies: chamber N2, chapel
           (10, 12, 's'), (16, 18, 's'), (22, 18, 's'),                 # shotgunners wait behind chamber doors
           (27, 3, 'r'), (2, 11, 'm'),
           (10, 18, 'h'), (19, 22, 'h'), (22, 12, 'a'), (19, 8, 'a'), (4, 14, 'a'),
           (24, 15, 'o'), (22, 19, 'o'), (23, 2, 'l'), (2, 16, 'l')])
    return m.text('E')

def cistern():
    """05 - three big halls full of single-cell pillars, floaters first appear, blue key in the far corner of
    the iron hall, blue door down to the exit, barrels in groups of 2-3."""
    m = Map()
    m.room(2, 11, 13, 22, 'E')           # west cistern hall 12x12
    m.room(2, 2, 13, 9, 'F')             # north overflow basin 12x8 (shares its south wall with the hall)
    m.room(18, 4, 29, 17, 'C')           # east iron hall 12x14
    m.room(2, 24, 6, 28, 'E')            # start antechamber (SW), shares its north wall with the hall
    m.room(20, 25, 26, 29, 'F')          # exit room (SE)
    m.carve(14, 12, 17, 13)              # open 2-tall archway between the halls
    m.carve(14, 16, 14, 16); m.carve(16, 16, 17, 16)      # lower passage with a door in the middle
    m.carve(23, 19, 23, 23)              # corridor from the blue door down to the exit room
    for x, y in ((5, 14), (8, 14), (11, 14), (5, 17), (8, 17), (11, 17), (5, 20), (8, 20), (11, 20)):
        m.wall(x, y, x, y, 'E')          # west hall pillars
    for x, y in ((21, 7), (24, 7), (27, 7), (21, 10), (24, 10), (27, 10), (21, 13), (24, 13), (27, 13)):
        m.wall(x, y, x, y, 'C')          # east hall pillars
    for x, y in ((5, 4), (9, 4), (5, 7), (9, 7)):
        m.wall(x, y, x, y, 'F')          # basin pillars
    m.paint(13, 11, 18, 17, 'E'); m.paint(22, 18, 24, 24, 'C')
    m.set(4, 23, 'D'); m.set(7, 10, 'D'); m.set(15, 16, 'D'); m.set(23, 18, 'U'); m.set(23, 24, 'D')
    m.set(23, 27, 'X')
    m.start(4, 26)                                           # facing north at the antechamber door
    m.put([(7, 13, 'i'), (12, 19, 'i'), (5, 3, 'i'), (10, 16, 'z'), (9, 6, 'z'),
           (24, 8, 's'), (19, 12, 's'), (26, 5, 'c'), (22, 15, 'c'), (12, 12, 'c'),
           (28, 5, 'u'), (3, 3, 'h'), (28, 16, 'h'), (3, 22, 'h'),
           (3, 12, 'a'), (12, 8, 'a'), (18, 5, 'a'), (3, 25, 'a'), (13, 9, 'm'),
           (9, 21, 'o'), (10, 21, 'o'), (10, 22, 'o'),                 # barrel group, west hall
           (19, 16, 'o'), (20, 16, 'o'), (19, 17, 'o'),                # barrel group, east hall
           (12, 3, 'o'), (12, 4, 'o'),                                 # barrel pair, basin
           (2, 11, 'l'), (13, 22, 'l')])
    return m.text('N')

def armoury():
    """06 - 1-wide maze corridors (a ring around the central armoury hall with fingers, loops and dead ends),
    red key NW, red door to the blue-key vault NE, blue door to the exit SE, brutes guard the ammo, 2 secrets."""
    m = Map()
    m.room(12, 13, 19, 18, 'C')          # central armoury hall (ammo cache, brute)
    m.room(2, 26, 5, 29, 'B')            # start room (SW)
    m.room(7, 27, 8, 28, 'B')            # secret closet 1 east of the start room (armour)
    m.room(2, 2, 6, 5, 'B')              # red key store (NW)
    m.room(24, 2, 29, 6, 'G')            # blue key vault (NE) behind the red door
    m.room(24, 24, 29, 29, 'C')          # exit room (SE) behind the blue door
    m.room(15, 5, 16, 6, 'G')            # secret closet 2 inside the north loop (health + armour)
    m.carve(9, 8, 22, 8); m.carve(9, 23, 22, 23); m.carve(9, 8, 9, 23); m.carve(22, 8, 22, 23)   # ring
    m.carve(10, 15, 10, 15); m.carve(21, 16, 21, 16); m.carve(16, 9, 16, 11); m.carve(16, 20, 16, 22)  # hall door stubs
    m.carve(3, 21, 3, 24); m.carve(3, 21, 8, 21)          # start door -> finger to the ring
    m.carve(5, 7, 5, 17); m.carve(5, 17, 8, 17)           # long west passage + finger
    m.carve(2, 13, 8, 13)                                 # loop to the ring, dead end west (ammo)
    m.carve(2, 7, 9, 7)                                   # passage under the red key store to the ring corner
    m.carve(12, 2, 12, 7); m.carve(12, 2, 19, 2); m.carve(19, 2, 19, 7)   # north loop around secret closet 2
    m.carve(23, 11, 28, 11); m.carve(28, 8, 28, 10)       # east finger up to the red door
    m.carve(23, 15, 26, 15); m.carve(26, 15, 26, 22); m.carve(23, 20, 25, 20)   # east loop + dead end (ammo, brute)
    m.carve(12, 24, 12, 28); m.carve(12, 28, 21, 28); m.carve(21, 26, 21, 27); m.carve(22, 26, 22, 26)  # south gallery
    m.paint(1, 1, 11, 25, 'B'); m.paint(10, 1, 21, 9, 'G'); m.paint(20, 7, 30, 23, 'G'); m.paint(10, 19, 23, 30, 'A')
    m.set(3, 25, 'D'); m.set(4, 6, 'D'); m.set(6, 27, 'S'); m.set(15, 7, 'S')
    m.set(11, 15, 'D'); m.set(20, 16, 'D'); m.set(16, 12, 'D'); m.set(16, 19, 'D')
    m.set(28, 7, 'R'); m.set(23, 26, 'U'); m.set(27, 27, 'X')
    m.start(3, 28)                                           # facing north at the start room door
    m.put([(3, 22, 'i'), (9, 10, 'i'), (16, 10, 'i'), (5, 11, 'z'), (14, 28, 'z'),
           (14, 2, 's'), (19, 6, 's'), (22, 12, 's'), (18, 14, 'c'), (22, 21, 'c'),
           (17, 17, 'b'), (26, 19, 'b'),                                # brutes guard the ammo
           (3, 3, 'r'), (28, 3, 'u'),
           (13, 14, 'a'), (13, 17, 'a'), (18, 17, 'a'), (26, 22, 'a'), (2, 13, 'a'),
           (15, 5, 'h'), (25, 15, 'h'), (12, 26, 'h'), (8, 28, 'm'), (16, 6, 'm'),
           (15, 15, 'o'), (16, 15, 'o'), (9, 8, 'o'), (17, 28, 'o'), (12, 13, 'l'), (19, 18, 'l')])
    return m.text('N')

def gallery():
    """07 - a 22x3 gallery with a 25-cell sight line from the start to the red door, two 22-cell side corridors,
    six 4x4 ambush rooms behind doors, mixed enemies (no boss), red key in the NE ambush room, 1 secret."""
    m = Map()
    m.room(2, 14, 3, 16, 'H')            # start vestibule (west)
    m.room(5, 14, 26, 16, 'H')           # the gallery
    m.carve(4, 14, 4, 16)                # vestibule opens into the gallery
    m.room(28, 13, 30, 17, 'E')          # exit room behind the red door
    m.carve(5, 9, 26, 9); m.carve(5, 21, 26, 21)          # north / south corridors (22 cells)
    m.carve(5, 10, 5, 13); m.carve(26, 10, 26, 13); m.carve(5, 17, 5, 20); m.carve(26, 17, 26, 20)
    for x in (7, 13, 19):
        m.room(x, 4, x + 3, 7, 'F')      # north ambush rooms, doors at (x+1, 8)
        m.room(x, 23, x + 3, 26, 'G')    # south ambush rooms, doors at (x+1, 22)
    m.room(24, 23, 25, 24, 'G')          # secret closet off the south corridor
    m.paint(4, 8, 27, 22, 'E')
    for x in (8, 14, 20):
        m.set(x, 8, 'D'); m.set(x, 22, 'D')
    m.set(24, 22, 'S'); m.set(27, 15, 'R'); m.set(29, 15, 'X')
    m.start(2, 15)                                           # facing east: the whole gallery in view
    m.put([(12, 15, 'z'), (20, 15, 'z'), (8, 14, 'i'),                  # in the gallery
           (16, 9, 's'), (10, 9, 'c'),                                  # north corridor
           (8, 5, 'i'), (10, 6, 'z'), (14, 5, 's'), (16, 6, 'c'), (20, 5, 'b'), (22, 6, 's'),   # north ambush rooms
           (8, 25, 'i'), (14, 25, 'z'), (20, 24, 'b'),                  # south ambush rooms
           (21, 4, 'r'), (3, 14, 'h'), (15, 26, 'h'), (26, 21, 'h'), (24, 23, 'h'),
           (10, 4, 'a'), (10, 26, 'a'), (5, 16, 'a'), (26, 9, 'a'), (25, 24, 'a'), (22, 26, 'm'),
           (15, 14, 'o'), (15, 16, 'o'), (12, 21, 'o'), (6, 14, 'l'), (25, 16, 'l')])
    return m.text('E')

def throne():
    """08 - the finale: 15x14 arena with the boss, 3 brutes, 4 pillars and 4 barrels; the iron throne dais hides
    the exit pad; red door into the antechamber (health/ammo/armour caches), blue door into the arena;
    red key in the west wing, blue key in the east wing, both reached from the start room's side corridors."""
    m = Map()
    m.room(10, 2, 24, 15, 'H')           # arena, 15x14, axis x=17
    m.room(12, 17, 22, 23, 'A')          # antechamber with the caches (shares wall y=16 with the arena)
    m.room(14, 25, 20, 29, 'B')          # start room (shares wall y=24 with the antechamber)
    m.room(2, 8, 8, 14, 'G')             # west wing: red key
    m.room(26, 8, 29, 14, 'E')           # east wing: blue key (shares wall x=25 with the arena)
    m.room(9, 19, 10, 21, 'A')           # secret closet west of the antechamber (armour)
    m.wall(15, 3, 19, 3, 'C')            # the throne dais; the exit pad stands behind it
    for x, y in ((13, 6), (21, 6), (13, 12), (21, 12)):
        m.wall(x, y, x, y, 'C')          # arena pillars (cover)
    m.carve(3, 27, 12, 27); m.carve(4, 16, 4, 26)         # west corridor up to the west wing
    m.carve(22, 27, 28, 27); m.carve(27, 16, 27, 26)      # east corridor up to the east wing
    m.paint(2, 15, 29, 28, 'B')
    m.set(13, 27, 'D'); m.set(21, 27, 'D'); m.set(4, 15, 'D'); m.set(27, 15, 'D')
    m.set(17, 24, 'R'); m.set(17, 16, 'U'); m.set(11, 20, 'S'); m.set(17, 2, 'X')
    m.start(17, 27)                                          # facing north at the red door
    m.put([(17, 7, 'k'), (12, 9, 'b'), (22, 9, 'b'), (17, 12, 'b'),      # the arena
           (14, 20, 'i'), (20, 20, 'i'),                                # antechamber
           (4, 10, 'z'), (6, 12, 'z'), (3, 13, 's'),                    # west wing
           (27, 10, 'c'), (26, 13, 'c'), (28, 9, 's'),                  # east wing
           (4, 20, 'i'), (27, 20, 'i'), (10, 27, 'z'), (22, 27, 'c'),   # corridors
           (3, 9, 'r'), (28, 13, 'u'),
           (13, 18, 'h'), (21, 18, 'h'), (7, 8, 'h'), (27, 24, 'h'),
           (13, 22, 'a'), (21, 22, 'a'), (2, 14, 'a'), (6, 27, 'a'), (17, 20, 'm'), (9, 20, 'm'),
           (12, 5, 'o'), (22, 5, 'o'), (12, 13, 'o'), (22, 13, 'o'),
           (14, 4, 'l'), (20, 4, 'l'), (14, 25, 'l'), (20, 25, 'l')])
    return m.text('N')

LEVELS = (('02_barracks', barracks), ('03_furnace', furnace), ('04_crypt', crypt), ('05_cistern', cistern),
          ('06_armoury', armoury), ('07_gallery', gallery), ('08_throne', throne))

if __name__ == '__main__':
    for name, fn in LEVELS:
        t = fn(); (HERE / f'{name}.txt').write_text(t)
        print(name); print(t)
