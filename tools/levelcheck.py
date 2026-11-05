#!/usr/bin/env python3
"""levelcheck.py - Kill'em All level checker + map renderer (lane L, 5 Nov 2026).

usage: levelcheck.py [--png OUT.png] <level.txt>...
  For every level:
   * compiles it with tools/mapc.py for the editions 48k, 128k and next (a 48k failure on the thing/enemy caps is
     INFORMATION only: levels 04..08 are 128K/Next content; any other compile error is a failure);
   * proves reachability: flood fill from '@' through floor/things/exit, 'D' and 'S' count as open, 'R'/'U' open
     only once the matching key cell ('r'/'u') has been reached (iterated until nothing changes);
   * reports exit reachable, every thing reachable, counts per thing letter, enemy types used, floor cells,
     longest straight run of open cells (the longest sight line, doors and walls end a run) and the number of
     rooms (connected open regions with every door/secret closed).
  One line per level ending in PASS/FAIL, then a RESULT line; exit code 0 only if every level passes.
  --png OUT.png renders each level at 8 px per cell (walls grey by texture, D brown, R red, U blue, S dashed,
     exit green, start white arrow, things as coloured letters). 'NN' in OUT.png is replaced by the two-digit
     level number taken from the file name (04_crypt.txt -> 04), so one pattern serves many levels.
Deterministic, read-only on the level files, needs only Pillow for --png.
"""
import sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mapc

EDITIONS = ('48k', '128k', 'next')
ENEMIES = 'izscbk'
ITEMS = 'hurmoal'
LETTERS = ENEMIES + ITEMS
WALLS = set('#ABCEFGH')
DOORS = {'D': 'door', 'R': 'red', 'U': 'blue', 'S': 'secret'}
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

def load(path):
    """rows exactly as mapc sees them (header lines removed, padded to 32x32)"""
    lines = pathlib.Path(path).read_text().splitlines()
    is_hdr = lambda l: l.startswith('#') and '=' in l and l[1:].split('=', 1)[0].strip().isalpha()
    header = {k.strip(): v.strip() for k, v in (l[1:].split('=', 1) for l in lines if is_hdr(l))}
    rows = [r.ljust(32)[:32] for r in lines if not is_hdr(r) and r.strip() != ''][:32]
    return header, rows

def is_open(ch):
    """cells the player can stand on (or touch, for the exit): floor, things, start, exit"""
    return ch in '. @X' or ch in LETTERS

def flood(rows, start, passable):
    seen = {start}; todo = collections.deque([start])
    while todo:
        x, y = todo.popleft()
        for dx, dy in N4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 32 and 0 <= ny < 32 and (nx, ny) not in seen and passable(rows[ny][nx]):
                seen.add((nx, ny)); todo.append((nx, ny))
    return seen

def reachability(rows):
    start = next(((x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == '@'), None)
    if start is None:
        return None
    keys = set()
    while True:
        reached = flood(rows, start, lambda ch: is_open(ch) or ch in 'DS' or (ch == 'R' and 'r' in keys)
                        or (ch == 'U' and 'u' in keys))
        found = {rows[y][x] for x, y in reached if rows[y][x] in 'ru'}
        if found <= keys:
            return reached, keys
        keys |= found

def rooms(rows):
    """connected regions of open cells with all doors (D/R/U/S) closed"""
    seen, n = set(), 0
    for y in range(32):
        for x in range(32):
            if (x, y) not in seen and is_open(rows[y][x]):
                seen |= flood(rows, (x, y), is_open); n += 1
    return n

def longest_run(rows):
    best = 0
    for y in range(32):
        run = 0
        for x in range(32):
            run = run + 1 if is_open(rows[y][x]) else 0; best = max(best, run)
    for x in range(32):
        run = 0
        for y in range(32):
            run = run + 1 if is_open(rows[y][x]) else 0; best = max(best, run)
    return best

def check(path):
    name = pathlib.Path(path).name
    comp, hard_fail = [], False
    for ed in EDITIONS:
        try:
            blob, ne, nt = mapc.compile_level(path, ed)
            comp.append(f'{ed}:ok({len(blob)}B)')
        except AssertionError as e:
            msg = str(e)
            if ed == '48k' and '> cap' in msg:
                comp.append('48k:FAIL(caps,info)')
            else:
                comp.append(f'{ed}:FAIL({msg.split(": ", 1)[-1]})'); hard_fail = True
    header, rows = load(path)
    if len(rows) != 32:
        return f'{name} {" ".join(comp)} | FAIL (need 32 rows, got {len(rows)})', False
    counts = collections.Counter(ch for r in rows for ch in r if ch in LETTERS)
    things = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch in LETTERS]
    exits = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == 'X']
    floor = sum(1 for r in rows for ch in r if ch in '. @' or ch in LETTERS)
    res = reachability(rows)
    if res is None:
        return f'{name} {" ".join(comp)} | FAIL (no start)', False
    reached, keys = res
    exit_ok = any(e in reached for e in exits)
    unreached = [(x, y, rows[y][x]) for x, y in things if (x, y) not in reached]
    doors = collections.Counter(ch for r in rows for ch in r if ch in DOORS)
    etypes = [c for c in ENEMIES if counts[c]]
    en = ' '.join(f'{c}{counts[c]}' for c in ENEMIES if counts[c]) or '-'
    it = ' '.join(f'{c}{counts[c]}' for c in ITEMS if counts[c]) or '-'
    dr = ' '.join(f'{c}{doors[c]}' for c in 'DRUS' if doors[c]) or '-'
    ok = not hard_fail and exit_ok and not unreached and len(exits) == 1
    line = (f'{name:16} {" ".join(comp)} | exit:{"yes" if exit_ok else "NO"} things:{len(things) - len(unreached)}/{len(things)} '
            f'reachable keys:{"".join(sorted(keys)) or "-"} | enemies {sum(counts[c] for c in ENEMIES)} [{en}] types={len(etypes)} '
            f'| items [{it}] doors [{dr}] | floor={floor} rooms={rooms(rows)} longest={longest_run(rows)} '
            f'| {"PASS" if ok else "FAIL"}')
    if unreached:
        line += f' unreachable={unreached}'
    return line, ok

# ------------------------------------------------------------------------------------------------ PNG
TEX_GREY = {'#': 150, 'A': 150, 'B': 120, 'C': 95, 'E': 110, 'F': 135, 'G': 80, 'H': 165}
TEX_TINT = {'#': (0, 0, 0), 'A': (0, 0, 0), 'B': (25, 5, -10), 'C': (-10, -10, 0), 'E': (-20, -15, 35),
            'F': (-15, 20, -15), 'G': (10, 0, -5), 'H': (-10, 25, -5)}
THING_RGB = {'i': (255, 140, 0), 'z': (90, 230, 90), 's': (255, 60, 60), 'c': (200, 80, 255), 'b': (255, 0, 120),
             'k': (255, 255, 0), 'h': (255, 90, 90), 'a': (255, 220, 60), 'r': (255, 40, 40), 'u': (60, 120, 255),
             'm': (60, 220, 220), 'o': (200, 120, 40), 'l': (240, 240, 170)}
DOOR_RGB = {'D': (150, 95, 40), 'R': (220, 30, 30), 'U': (40, 80, 230)}

def render(path, out, line):
    from PIL import Image, ImageDraw, ImageFont
    header, rows = load(path)
    S, FOOT = 8, 36
    img = Image.new('RGB', (32 * S, 32 * S + FOOT), (12, 12, 16))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=8); foot = ImageFont.load_default(size=9)
    except TypeError:
        font = foot = ImageFont.load_default()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            x0, y0 = x * S, y * S
            if ch in WALLS:
                g = TEX_GREY[ch]; t = TEX_TINT[ch]
                col = tuple(max(0, min(255, g + t[i])) for i in range(3))
                if not any(0 <= x + dx < 32 and 0 <= y + dy < 32 and rows[y + dy][x + dx] not in WALLS for dx, dy in N4):
                    col = (44, 44, 50)                       # solid rock no player can ever see: flat dark
                d.rectangle((x0, y0, x0 + S - 1, y0 + S - 1), fill=col, outline=tuple(max(0, c - 30) for c in col))
            elif ch in DOOR_RGB:
                d.rectangle((x0, y0, x0 + S - 1, y0 + S - 1), fill=(30, 30, 36))
                if any(0 <= x + dx < 32 and (rows[y][x + dx] in WALLS or rows[y][x + dx] in DOORS) for dx in (1, -1)) and not \
                   any(0 <= y + dy < 32 and (rows[y + dy][x] in WALLS or rows[y + dy][x] in DOORS) for dy in (1, -1)):
                    d.rectangle((x0, y0 + 2, x0 + S - 1, y0 + S - 3), fill=DOOR_RGB[ch])     # door in a horizontal wall
                else:
                    d.rectangle((x0 + 2, y0, x0 + S - 3, y0 + S - 1), fill=DOOR_RGB[ch])     # door in a vertical wall
            elif ch == 'S':
                d.rectangle((x0, y0, x0 + S - 1, y0 + S - 1), fill=(150, 150, 150))
                for i in range(0, S, 2):                                                 # dashed yellow outline
                    d.point((x0 + i, y0), (255, 230, 0)); d.point((x0 + i, y0 + S - 1), (255, 230, 0))
                    d.point((x0, y0 + i), (255, 230, 0)); d.point((x0 + S - 1, y0 + i), (255, 230, 0))
            elif ch == 'X':
                d.rectangle((x0, y0, x0 + S - 1, y0 + S - 1), fill=(0, 140, 40))
                d.text((x0 + 2, y0 - 1), 'X', fill=(255, 255, 255), font=font)
            elif ch == '@':
                a = header.get('start', 'E'); x1, y1 = x0 + S - 1, y0 + S - 1       # white triangle = start, points the way
                tri = {'E': ((x0, y0), (x1, y0 + S // 2), (x0, y1)), 'W': ((x1, y0), (x0, y0 + S // 2), (x1, y1)),
                       'N': ((x0, y1), (x0 + S // 2, y0), (x1, y1)), 'S': ((x0, y0), (x0 + S // 2, y1), (x1, y0))}[a]
                d.polygon(tri, fill=(255, 255, 255))
            else:
                if ch in LETTERS:
                    d.text((x0 + 2, y0 - 1), ch, fill=THING_RGB[ch], font=font)
    parts = line.split(' | ')                                                        # footer: name, reach, enemies, items
    d.text((2, 32 * S + 1), f'{pathlib.Path(path).stem}  start={header.get("start", "E")}  {parts[-1]}', fill=(230, 230, 230), font=foot)
    d.text((2, 32 * S + 12), parts[1][:60] if len(parts) > 1 else '', fill=(170, 170, 170), font=foot)
    d.text((2, 32 * S + 23), parts[2][:60] if len(parts) > 2 else '', fill=(170, 170, 170), font=foot)
    img.save(out)

def main(argv):
    png = None
    if '--png' in argv:
        i = argv.index('--png'); png = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__); return 2
    print('# levelcheck: 48k:FAIL(caps,info) = exceeds the 48K caps only (levels 04..08 are 128K/Next content); '
          'longest = longest straight run of open cells; rooms = open regions with all doors closed')
    results = []
    for p in argv:
        line, ok = check(p); results.append(ok); print(line)
        if png:
            stem = pathlib.Path(p).stem; nn = stem.split('_')[0] if stem[:2].isdigit() else stem
            out = png.replace('NN', nn) if 'NN' in png else (png if len(argv) == 1 else str(pathlib.Path(png).with_name(
                pathlib.Path(png).stem + '_' + stem + pathlib.Path(png).suffix)))
            render(p, out, line); print(f'  -> {out}')
    print(f'RESULT {"PASS" if all(results) else "FAIL"} {sum(results)}/{len(results)} levels pass')
    return 0 if all(results) else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
