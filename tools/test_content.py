#!/usr/bin/env python3
"""test_content.py - lane T5 content tests for Kill'em all (exit 0 = all good).

Checks:
  1. build/title.scr is exactly 6912 bytes; every 8x8 cell is two-colour-valid (attribute flash bit clear, bright-black
     consistency); attribute rows 16..23 are dark (paper black, no ink pixels) so the menu can be overlaid; the PNG
     preview re-renders byte-identically from the .scr (truthful preview) and the source PNG round-trips with 0 violations.
  2. src/gen/sprites_data.asm assembles with pasmo through build/sprites_wrap.asm; the binary size equals the sum of
     the per-sprite sizes (1 + cols*2*H); spr_table has 18 entries with ids/heights/widths per ARCH_M2.md; total <= 2048.
  3. Levels 01..03 compile with tools/mapc.py for 48k (<= 16 things, <= 3 enemy types, only imp/zombie) and are fully
     reachable (mapview flood fill) - AND key-aware: with locked doors closed the matching key must be reachable first
     (red before R doors, blue before U doors), the exit must be reachable after collecting the keys, every secret
     closet is enterable, and no thing stands on a wall/door cell.
Usage: .venv/bin/python tools/test_content.py      (prints a line per check; non-zero exit on failure)
"""
import sys, re, pathlib, subprocess, struct
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(ROOT / 'tools'))
import scrconv  # noqa: E402

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

# ------------------------------------------------------------------ 1. title screen
scr_path = ROOT / 'build/title.scr'
scr = scr_path.read_bytes() if scr_path.exists() else b''
check(len(scr) == 6912, f"title.scr size {len(scr)} == 6912")
if len(scr) == 6912:
    problems = scrconv.check(scr_path)
    check(not problems, f"title.scr attribute rules (flash clear, rows 16..23 dark): {len(problems)} problems" + (f" e.g. {problems[0]}" if problems else ''))
    # two colours per cell is structural in .scr; verify the decode->re-encode is lossless (every cell representable)
    img = scrconv.decode(scr)
    tmp_png = ROOT / 'build/title_roundtrip.png'; img.save(tmp_png)
    tmp_scr = ROOT / 'build/title_roundtrip.scr'
    viol = scrconv.png2scr(tmp_png, tmp_scr, quiet=True)
    check(viol == [], f"decode->encode round trip: {len(viol)} cells with >2 colours")
    rt = tmp_scr.read_bytes()
    # pixel area must match exactly; attributes may differ only for cells with a single colour (ink==paper is ambiguous)
    check(rt[:6144] == scr[:6144], "round-trip pixel bytes identical")
    bright_cells = sum(1 for a in scr[6144:] if a & 0x40)
    used = sorted({(a & 7, (a >> 3) & 7, (a >> 6) & 1) for a in scr[6144:]})
    print(f"info  title.scr: {bright_cells} BRIGHT cells, {len(used)} distinct attribute combos, "
          f"lit rows {min(y for y in range(192) if any(scr[scrconv.pix_offset(x, y)] for x in range(0, 256, 8)))}.."
          f"{max(y for y in range(192) if any(scr[scrconv.pix_offset(x, y)] for x in range(0, 256, 8)))}")
    prev = ROOT / 'build/title_preview.png'
    if prev.exists():
        from PIL import Image
        check(Image.open(prev).convert('RGB').tobytes() == img.tobytes(), "build/title_preview.png == render of title.scr")
    src_png = ROOT / 'build/title_src.png'
    if src_png.exists():
        v2 = scrconv.png2scr(src_png, ROOT / 'build/title_roundtrip2.scr', quiet=True)
        check(v2 == [], f"title_src.png -> scr: {len(v2)} violating cells")
        check((ROOT / 'build/title_roundtrip2.scr').read_bytes() == scr, "title.scr is the deterministic output of title_src.png")

# ------------------------------------------------------------------ 2. sprites
asm = ROOT / 'src/gen/sprites_data.asm'
check(asm.exists(), f"{asm.relative_to(ROOT)} exists")
if asm.exists():
    text = asm.read_text()
    m = re.search(r'^spr_table:\s*\n\s*dw\s+([^\n]+)', text, re.M)
    entries = [e.strip() for e in m.group(1).split(',')] if m else []
    check(entries == [f'spr_{i:02d}' for i in range(18)], f"spr_table has 18 entries in id order ({len(entries)} found)")
    heads = re.findall(r'^spr_(\d\d):[^\n]*\n\s*db\s+(\d+)', text, re.M)
    hdict = {int(i): int(h) for i, h in heads}
    check(sorted(hdict) == list(range(18)), f"18 sprite blocks with db H headers ({len(hdict)} found)")
    for i in range(14):
        check(8 <= hdict.get(i, 0) <= 24, f"sprite {i} height {hdict.get(i)} in 8..24")
    for i in range(14, 18):
        check(hdict.get(i) == 24, f"weapon {i} height {hdict.get(i)} == 24")
    expected = 36 + sum(1 + (4 if i >= 14 else 2) * 2 * hdict.get(i, 0) for i in range(18))
    wrap = ROOT / 'build/sprites_wrap.asm'
    wrap.write_text('; sprites_wrap.asm - minimal wrapper to assemble src/gen/sprites_data.asm standalone with pasmo (lane T5 test).\n'
                    '    org 40000\n    include "../src/gen/sprites_data.asm"\n    end\n')
    r = subprocess.run(['pasmo', '--bin', 'sprites_wrap.asm', 'sprites_wrap.bin', 'sprites_wrap.sym'], cwd=ROOT / 'build',
                       capture_output=True, text=True)
    check(r.returncode == 0, f"pasmo assembles sprites_data.asm via build/sprites_wrap.asm (rc={r.returncode}) {r.stderr.strip()[:200]}")
    if r.returncode == 0:
        binsz = (ROOT / 'build/sprites_wrap.bin').stat().st_size
        check(binsz == expected, f"assembled size {binsz} == expected from headers {expected}")
        check(binsz <= 2048, f"sprite+weapon data {binsz} bytes <= 2048")
        syms = dict(re.findall(r'^(\w+)\s+EQU\s+([0-9A-F]+)H', (ROOT / 'build/sprites_wrap.sym').read_text(), re.M))
        base = int(syms['spr_table'], 16)
        binb = (ROOT / 'build/sprites_wrap.bin').read_bytes()
        ok = True
        for i in range(18):
            addr = struct.unpack_from('<H', binb, 2 * i)[0]
            ok &= addr == int(syms[f'spr_{i:02d}'], 16) and binb[addr - base] == hdict[i]
        check(ok, "spr_table addresses point at each sprite's db H header")
        print(f"info  sprites: total {binsz} B = table 36 + " + ' + '.join(f"{1 + (4 if i >= 14 else 2) * 2 * hdict[i]}" for i in range(18)))
    # no trademark words anywhere in assets / generated data
    bad_words = re.compile(r'\b(' + '|'.join(w[::-1] for w in ('mood', 'nomedocac', 'erawtfos di')) + r')\b', re.I)  # 3rd-party names, reversed
    hits = [p.relative_to(ROOT) for p in list((ROOT / 'assets').rglob('*')) + [asm] if p.is_file() and bad_words.search(p.read_text(errors='ignore'))]
    check(not hits, f"no third-party trademark words in assets/ or sprites_data.asm {hits}")

# ------------------------------------------------------------------ 3. levels
def load_level(path):
    lines = path.read_text().splitlines()
    is_hdr = lambda l: l.startswith('#') and '=' in l and l[1:].split('=', 1)[0].strip().isalpha()
    rows = [l.ljust(32)[:32] for l in lines if not is_hdr(l) and l.strip()]
    assert len(rows) == 32
    return [list(r) for r in rows]

def flood(grid, start, passable):
    seen = {start}; q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 32 and 0 <= ny < 32 and (nx, ny) not in seen and passable(grid[ny][nx]):
                seen.add((nx, ny)); q.append((nx, ny))
    return seen

THINGS = 'izscbkharumol'
levels = sorted((ROOT / 'assets/levels').glob('0[0-9]_*.txt'))
check([p.name[:2] for p in levels] == ['01', '02', '03'], f"levels present: {[p.name for p in levels]}")
for lvl in levels:
    r = subprocess.run([PY, str(ROOT / 'tools/mapc.py'), '48k', str(ROOT / 'build/level_check.bin'), str(lvl)], capture_output=True, text=True)
    check(r.returncode == 0, f"{lvl.name}: mapc 48k compiles  {r.stdout.strip().splitlines()[0] if r.stdout.strip() else r.stderr.strip()[-200:]}")
    g = load_level(lvl)
    cells = [(x, y, g[y][x]) for y in range(32) for x in range(32)]
    things = [(x, y, c) for x, y, c in cells if c in THINGS]
    check(len(things) <= 16, f"{lvl.name}: {len(things)} things <= 16")
    enemy_types = {c for _, _, c in things if c in 'izscbk'}
    check(enemy_types <= {'i', 'z'}, f"{lvl.name}: enemy types {sorted(enemy_types)} subset of imp/zombie")
    start = next((x, y) for x, y, c in cells if c == '@')
    # mapview-style reachability (everything but walls passable)
    all_pass = lambda ch: ch in '. @X' or ch in 'DRUS' or ch in THINGS
    seen = flood(g, start, all_pass)
    unreach = [(c, x, y) for x, y, c in cells if all_pass(c) and (x, y) not in seen and c != '.']
    check(not unreach, f"{lvl.name}: unreachable things/doors/exit = {unreach}")
    # key-aware progression: locked doors closed until the key is collected
    have = set()
    def passable_keys(ch):
        if ch == 'R': return 'r' in have
        if ch == 'U': return 'u' in have
        return all_pass(ch)
    order = []
    for _ in range(3):
        reach = flood(g, start, passable_keys)
        got = {g[y][x] for (x, y) in reach if g[y][x] in 'ru'} - have
        if not got: break
        have |= got; order.append(''.join(sorted(got)))
    reach = flood(g, start, passable_keys)
    exit_cell = next((x, y) for x, y, c in cells if c == 'X')
    locked = {c for _, _, c in cells if c in 'RU'}
    need = {'R': 'r', 'U': 'u'}
    check(all(need[d] in have for d in locked), f"{lvl.name}: keys for locked doors {sorted(locked)} collected in order {order}")
    check(exit_cell in reach, f"{lvl.name}: exit {exit_cell} reachable after keys")
    # exit must not be reachable without the keys the level has
    reach0 = flood(g, start, lambda ch: all_pass(ch) and ch not in 'RU')
    check(not locked or exit_cell not in reach0, f"{lvl.name}: exit gated by locked door(s) {sorted(locked)}")
    # each secret wall must separate a closet that is only reachable through it
    for x, y, c in cells:
        if c == 'S':
            reach_noS = flood(g, start, lambda ch: all_pass(ch) and ch != 'S')
            check(any((x + dx, y + dy) not in reach_noS and g[y + dy][x + dx] in '.' + THINGS for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))),
                  f"{lvl.name}: secret wall at {(x, y)} hides a closet")
    print(f"info  {lvl.name}: things={len(things)} " + ' '.join(f"{c}={sum(1 for _, _, t in things if t == c)}" for c in THINGS if any(t == c for _, _, t in things))
          + f" doors={''.join(sorted(c for _, _, c in cells if c in 'DRUS'))} start={start} exit={exit_cell}")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}")
sys.exit(1 if fails else 0)
