#!/usr/bin/env python3
"""m24_imp_art.py - M2.4: the second enemy type (type 1, magenta, files 00..03) becomes a 'bloater' zombie: the green
zombie body MIRRORED (facing left) with a fat belly and its own skull sunk INTO the shoulder hump (3-px neck), two sockets,
hanging jaw. v3: skull one row deeper in walk A, attack jaw = real 2-px gap, corpse keeps the belly mass.
Same 16 x 24 box so card/scale behave like the green zombie. Reads assets/sprites/04..07 for the legs, writes 00..03."""
import pathlib
R = pathlib.Path.home() / "work/killemall/assets/sprites"

TOP_A = [
    "................",
    "................",
    "....####........",
    "...######.......",
    "...#.##.#.......",
    "...######.##....",
    "....#.##.####...",
    "..##.#########..",
    ".#.##########...",
    "#.#.##########..",
    ".....#########..",
    "...############.",
    ".##.##########..",
    "#.#..#########..",
]
TOP_B = [
    "................",
    "................",
    "...####.........",
    "..######........",
    "..#.##.#........",
    "..######..##....",
    "...#.##..####...",
    "....##.#######..",
    ".#.##########...",
    "#.#.##########..",
    ".....#########..",
    "...############.",
    ".##.##########..",
    "#.#..#########..",
]
TOP_ATK = [
    "................",
    "................",
    "...##.#.........",
    "..######........",
    "..###.##........",
    "..######.##.....",
    "...#..#.####....",
    "....##.#######..",
    ".##.##########..",
    "#.#.##########..",
    "....##########..",
    "...############.",
    ".##.##########..",
    "#.#..#########..",
]

ATK_FULL = [  # bloater attack drawn in full: lunge LEFT - skull dropped over the arms (two sockets, jaw gap), both arms straight
    # left to the edge with claws, fat belly behind them, legs braced wide with the rear leg right
    "................",
    "................",
    "...##.#.........",
    "..######........",
    "..#.##.#........",
    "..######.##.....",
    "...#..#.#####...",
    "....##.#######..",
    ".##############.",
    "#.#..#########.#",
    ".#....########..",
    "......#########.",
    ".#####.########.",
    "#.#....#######..",
    ".#.....#######..",
    ".......######...",
    "......##.#.#....",
    ".....##....##...",
    ".....##....##...",
    "....##......##..",
    "....##......##..",
    "...##........##.",
    "..###........##.",
    "..###........###",
]

def mirrored(name):
    rows = [r for r in (R / name).read_text().splitlines() if r and not r.startswith(";")]
    return [r[::-1] for r in rows]

def splice(top, body):
    out = top + body[len(top):]
    assert len(out) == len(body) == 24, (len(top), len(body))
    return out

a = splice(TOP_A, mirrored("04_zombie_walk_a.txt"))
b = splice(TOP_B, mirrored("05_zombie_walk_b.txt"))
atk = ATK_FULL
dead = [  # belly mass in the middle, knee arch left, skull right with socket + open jaw, claw on the floor at the far right
    "................",
    "................",
    "................",
    "................",
    "................",
    "...##...........",
    "..####..#####...",
    ".##..##.#######.",
    ".##..##.######..",
    "#.#############.",
    "##.#########.##.",
    "##..##.####.#.#.",
]

OUT = {
    "00_imp_walk_a.txt": ("; bloater walk A (M2.4 v3) - mirrored zombie body (shambles left), skull sunk into the hump, two sockets, fat belly", a),
    "01_imp_walk_b.txt": ("; bloater walk B (M2.4 v3) - lurch frame", b),
    "02_imp_attack.txt": ("; bloater attack (M2.4 v3) - lunge, jaw wide open (2-px gap)", atk),
    "03_imp_dead.txt": ("; bloater dead (M2.4 v3) - corpse: knee arch left, belly mass, skull right (12 rows)", dead),
}
for name, (hdr, rows) in OUT.items():
    for i, r in enumerate(rows):
        assert len(r) == 16 and set(r) <= set("#o."), (name, i, r)
    (R / name).write_text(hdr + "\n" + "\n".join(rows) + "\n")
    print("%-20s h %2d ink %3d" % (name, len(rows), sum(r.count("#") for r in rows)))
