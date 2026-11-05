#!/usr/bin/env python3
"""mapc.py — Kill'em All level compiler (shared by all three editions).

Level source: assets/levels/NN_name.txt — 32 lines × 32 chars + optional '#' header lines.
  '#'  wall texture 1      'A'..'G' wall textures 1..7      '.'/' ' floor
  'D'  door (unlocked)     'R' door, red key   'B' door, blue key   'S' secret wall (texture 1, pushable)
  'X'  exit                '@' player start (facing east; append '@N','@S','@W' via header 'start=' to turn)
  'i' imp  'z' zombie  's' shotgunner  'c' cacodemon-like  'b' baron-like  'k' boss (edition-capped)
  'h' health  'a' ammo  'r' red key  'u' blue key  'm' armour  'o' barrel  'l' lamp (decor)
Output (binary, little-endian):
  u8 magic 'K' u8 version 1 u8 w u8 h u8 start_x u8 start_y u8 start_angle u8 n_things
  w*h bytes cell codes (0 floor, 1..7 wall tex, 8 door, 9 red door, 10 blue door, 11 secret, 12 exit)
  n_things × (u8 type, u8 x, u8 y)
Deterministic: same text in → same bytes out. Validates: outer wall closed, exactly one start, one exit,
keys exist for locked doors, thing counts ≤ edition caps.
"""
import sys, struct, pathlib

CELL = {'.': 0, ' ': 0, '#': 1, 'A': 1, 'B': 2, 'C': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7,
        'D': 8, 'R': 9, 'U': 10, 'S': 11, 'X': 12}
THING = {'i': 1, 'z': 2, 's': 3, 'c': 4, 'b': 5, 'k': 6, 'h': 16, 'a': 17, 'r': 18, 'u': 19, 'm': 20, 'o': 21, 'l': 22}
ENEMY_CAP = {'48k': 3, '128k': 6, 'next': 8}          # distinct enemy types allowed per edition
THING_CAP = {'48k': 24, '128k': 48, 'next': 96}
ANGLE = {'E': 0, 'N': 192, 'W': 128, 'S': 64}         # 256 units per turn, y grows downwards

def compile_level(path, edition):
    lines = pathlib.Path(path).read_text().splitlines()
    is_hdr = lambda l: l.startswith('#') and '=' in l and l[1:].split('=', 1)[0].strip().isalpha()
    header = {k.strip(): v.strip() for k, v in (l[1:].split('=', 1) for l in lines if is_hdr(l))}
    rows = [l for l in lines if not is_hdr(l)]
    rows = [r.ljust(32)[:32] for r in rows if r.strip() != ''][:32]
    assert len(rows) == 32, f"{path}: need 32 rows, got {len(rows)}"
    cells = bytearray(32 * 32); things = []; start = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == '@':
                assert start is None, f"{path}: two starts"; start = (x, y)
            elif ch in THING:
                things.append((THING[ch], x, y))
            else:
                assert ch in CELL, f"{path}: bad char {ch!r} at {x},{y}"
                cells[y * 32 + x] = CELL[ch]
    assert start, f"{path}: no start"
    assert sum(1 for c in cells if c == 12) >= 1, f"{path}: no exit"
    for x in range(32):
        assert 1 <= cells[x] <= 7 and 1 <= cells[31 * 32 + x] <= 7, f"{path}: top/bottom border open at x={x}"
    for y in range(32):
        assert 1 <= cells[y * 32] <= 7 and 1 <= cells[y * 32 + 31] <= 7, f"{path}: side border open at y={y}"
    types = {t for t, _, _ in things}
    if 9 in cells: assert 18 in types, f"{path}: red door without red key"
    if 10 in cells: assert 19 in types, f"{path}: blue door without blue key"
    enemies = sorted(t for t in types if t < 16)
    assert len(enemies) <= ENEMY_CAP[edition], f"{path}: {len(enemies)} enemy types > cap {ENEMY_CAP[edition]} for {edition}"
    assert len(things) <= THING_CAP[edition], f"{path}: {len(things)} things > cap {THING_CAP[edition]} for {edition}"
    things.sort()
    out = struct.pack('<ccBBBBBB', b'K', b'\x01', 32, 32, start[0], start[1], ANGLE[header.get('start', 'E')], len(things))
    return out + bytes(cells) + b''.join(struct.pack('<BBB', *t) for t in things), len(enemies), len(things)

def main():
    if len(sys.argv) < 4:
        print("usage: mapc.py <edition 48k|128k|next> <out.bin> <level.txt>..."); sys.exit(2)
    edition, out = sys.argv[1], sys.argv[2]; blobs = []
    for p in sys.argv[3:]:
        b, ne, nt = compile_level(p, edition); blobs.append(b)
        print(f"{pathlib.Path(p).name}: {len(b)} bytes, {ne} enemy types, {nt} things")
    pathlib.Path(out).write_bytes(struct.pack('<B', len(blobs)) + b''.join(blobs))
    print(f"-> {out}: {len(blobs)} levels, {sum(map(len, blobs)) + 1} bytes")

if __name__ == '__main__':
    main()
