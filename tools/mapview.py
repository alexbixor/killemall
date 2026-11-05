#!/usr/bin/env python3
"""mapview.py - render a Kill'em all level text map to PNG (overhead view) and print deterministic stats:
symbol counts, and a flood-fill reachability check from the player start (doors/secret walls passable)."""
import sys, pathlib
from collections import deque
from PIL import Image, ImageDraw, ImageFont

src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
lines = [l.rstrip('\n') for l in src.read_text().splitlines()]
is_hdr = lambda l: l.startswith('#') and '=' in l and l[1:].split('=', 1)[0].strip().isalpha()
hdr = dict(l[1:].split('=', 1) for l in lines if is_hdr(l))
rows = [l for l in lines if not is_hdr(l) and l.strip()]
assert len(rows) == 32 and all(len(r) == 32 for r in rows), (len(rows), [len(r) for r in rows])
grid = [list(r) for r in rows]

WALL = {'#': (150, 60, 50), 'A': (150, 60, 50), 'B': (105, 105, 115), 'C': (120, 95, 60), 'E': (70, 110, 70),
        'F': (90, 70, 120), 'G': (60, 100, 120), 'H': (130, 110, 50)}
DOOR = {'D': (215, 175, 60), 'R': (220, 50, 50), 'U': (60, 90, 230), 'S': (150, 60, 50)}
THING = {'i': ('imp', (255, 90, 60)), 'z': ('zombie', (170, 255, 90)), 's': ('shotgunner', (255, 170, 60)),
         'c': ('cacodemon', (255, 60, 200)), 'b': ('baron', (200, 60, 255)), 'k': ('boss', (255, 255, 60)),
         'h': ('health', (255, 255, 255)), 'a': ('ammo', (255, 215, 90)), 'r': ('red key', (255, 40, 40)),
         'u': ('blue key', (70, 110, 255)), 'm': ('armour', (90, 220, 90)), 'o': ('barrel', (200, 140, 90)),
         'l': ('lamp', (255, 250, 200))}
FLOOR = (40, 40, 48); FLOOR_UNREACH = (90, 30, 30); GRIDC = (28, 28, 34)

# reachability: floor, things, doors, secret walls and the exit are passable
passable = lambda ch: ch in '. @X' or ch in DOOR or ch in THING
start = next((x, y) for y in range(32) for x in range(32) if grid[y][x] == '@')
seen = {start}; q = deque([start])
while q:
    x, y = q.popleft()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < 32 and 0 <= ny < 32 and (nx, ny) not in seen and passable(grid[ny][nx]):
            seen.add((nx, ny)); q.append((nx, ny))

CS = 22; LEG = 250; W = 32 * CS + LEG; H = 32 * CS
img = Image.new('RGB', (W, H), (18, 18, 22)); d = ImageDraw.Draw(img)
font = ImageFont.load_default()
for y in range(32):
    for x in range(32):
        ch = grid[y][x]; x0, y0 = x * CS, y * CS; box = (x0, y0, x0 + CS - 1, y0 + CS - 1)
        if ch in WALL:
            d.rectangle(box, fill=WALL[ch], outline=GRIDC)
        elif ch == 'S':
            d.rectangle(box, fill=WALL['#'], outline=GRIDC)
            d.line((x0 + 3, y0 + 3, x0 + CS - 4, y0 + CS - 4), fill=(255, 255, 255), width=2)
            d.line((x0 + 3, y0 + CS - 4, x0 + CS - 4, y0 + 3), fill=(255, 255, 255), width=2)
        else:
            d.rectangle(box, fill=FLOOR if (x, y) in seen else FLOOR_UNREACH, outline=GRIDC)
            if ch in DOOR:
                d.rectangle((x0 + 2, y0 + 7, x0 + CS - 3, y0 + CS - 8), fill=DOOR[ch])
            elif ch == 'X':
                d.rectangle((x0 + 3, y0 + 3, x0 + CS - 4, y0 + CS - 4), fill=(60, 220, 90)); d.text((x0 + 5, y0 + 4), 'EXIT'[:2], fill=(0, 0, 0), font=font)
            elif ch == '@':
                d.ellipse((x0 + 4, y0 + 4, x0 + CS - 5, y0 + CS - 5), fill=(255, 255, 255))
                d.polygon([(x0 + CS - 2, y0 + CS // 2), (x0 + CS - 8, y0 + 4), (x0 + CS - 8, y0 + CS - 5)], fill=(255, 255, 255))
            elif ch in THING:
                name, col = THING[ch]
                if ch in 'izscbk': d.ellipse((x0 + 5, y0 + 5, x0 + CS - 6, y0 + CS - 6), fill=col)
                else: d.rectangle((x0 + 6, y0 + 6, x0 + CS - 7, y0 + CS - 7), fill=col)
                d.text((x0 + 8, y0 + 5), ch, fill=(0, 0, 0), font=font)
# legend
lx, ly = 32 * CS + 12, 8
def leg(col, text, shape='rect'):
    global ly
    if shape == 'rect': d.rectangle((lx, ly, lx + 14, ly + 14), fill=col)
    else: d.ellipse((lx, ly, lx + 14, ly + 14), fill=col)
    d.text((lx + 22, ly + 2), text, fill=(230, 230, 230), font=font); ly += 19
d.text((lx, ly), f"KILL'EM ALL - {src.stem}", fill=(255, 255, 255), font=font); ly += 22
for k, t in (('#', 'wall tex 1 (brick)'), ('B', 'wall tex 2'), ('C', 'wall tex 3'), ('E', 'wall tex 4'), ('F', 'wall tex 5'), ('G', 'wall tex 6'), ('H', 'wall tex 7')): leg(WALL[k], t)
leg(DOOR['D'], 'door'); leg(DOOR['R'], 'red-key door'); leg(DOOR['U'], 'blue-key door'); leg((255, 255, 255), 'secret wall (X mark)')
leg((60, 220, 90), 'exit'); leg((255, 255, 255), 'player start -> east', 'ell')
ly += 6
counts = {}
for r in rows:
    for ch in r: counts[ch] = counts.get(ch, 0) + 1
for ch, (name, col) in THING.items():
    if counts.get(ch): leg(col, f"{name} x{counts[ch]}", 'ell' if ch in 'izscbk' else 'rect')
ly += 6; leg(FLOOR, 'floor reachable from start'); leg(FLOOR_UNREACH, 'floor NOT reachable')
img.save(out)
print(f"png {out} {img.size[0]}x{img.size[1]}  start={start} facing {hdr.get('start','E')}")
print("counts:", ' '.join(f"{k}={v}" for k, v in sorted(counts.items()) if k not in '.# '))
floor_cells = [(x, y) for y in range(32) for x in range(32) if passable(grid[y][x])]
unreach = [(x, y, grid[y][x]) for (x, y) in floor_cells if (x, y) not in seen]
print(f"passable cells {len(floor_cells)}, reachable {len(seen)}, unreachable {len(unreach)}")
print("unreachable things/doors/exit:", [(c, x, y) for x, y, c in unreach if c != '.'])
print("doors:", [(grid[y][x], x, y) for y in range(32) for x in range(32) if grid[y][x] in DOOR])
