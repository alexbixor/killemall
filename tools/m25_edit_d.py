#!/usr/bin/env python3
"""m25_edit_d.py - M2.5 step D: two-tone 3D window (user 1 Nov 10:2xZ: "Split at horizon on both tapes: ceiling keeps the level
tint (white/cyan/yellow), floor gets its own ink - 48K floor green, 128K floor red").
Idempotent source edits (each step has a marker; re-running is a no-op):
 1. src/48k/kea48.asm  win_tint: attribute rows 1..6 (window rows 0..47 = ceiling) <- TINTTAB[level] as before;
                                 attribute rows 7..12 (window rows 48..95 = floor) <- FLOORINK (equ 4 = green on the 48K).
                                 The horizon is window row 48 = exactly the attribute row 6/7 boundary, so this is still one ink
                                 per 8x8 cell and render still never writes attributes (0 fps cost, same code path).
 2. tools/make128.py   anchor A6: the `FLOORINK equ 4` line becomes `FLOORINK equ 2` (red) in the generated 128K source.
 3. tools/test_tint.py oracle: ceiling cells == TINTTAB[level], floor cells == FLOORINK, FLOORINK == 4 (48K) / 2 (KEA128=1).
 5. tools/test_128.py: make128 anchor census 5/8 -> 6/9 (A6).
 4. tools/m25c_shots.py: label both inks, stills -> build/m25d_l<N>.png + build/m25d_strip.png (step C stills kept).
usage: .venv/bin/python tools/m25_edit_d.py"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
K = ROOT / "src/48k/kea48.asm"
M = ROOT / "tools/make128.py"
T = ROOT / "tools/test_tint.py"
S = ROOT / "tools/m25c_shots.py"
T128 = ROOT / "tools/test_128.py"

def edit(path, pairs, marker):
    s = path.read_text()
    if marker in s:
        print("%s: step D already applied" % path.name); return
    for old, new in pairs:
        assert s.count(old) == 1, "anchor not unique/found in %s: %r" % (path.name, old[:70])
        s = s.replace(old, new)
    path.write_text(s); print("%s: step D applied" % path.name)

# ---- 1. kea48.asm
k_pairs = [
 ("; M2.5 win_tint: the whole 3D window has ONE ink (zero attribute clash); it is chosen per level from TINTTAB and written once\n"
  "; into the window attribute cells (12 rows x 24 cells, rows 1..12 cols 4..27). Frame cells (cols 3 / 28) and the HUD stay as they are.\n",
  "; M2.5 win_tint: the 3D window has ONE ink per 8x8 cell and render never writes attributes. M2.5D: two tones split at the horizon\n"
  "; (window row 48 = attribute row 6/7 boundary): ceiling cells (attr rows 1..6) take the level ink from TINTTAB, floor cells\n"
  "; (attr rows 7..12) take FLOORINK (48K green, 128K red via make128.py anchor A6). Written once per level start / restart into\n"
  "; the 12 rows x 24 cells (cols 4..27). Frame cells (cols 3 / 28) and the HUD stay as they are.\n"),
 ("        ld a,(hl)              ; ink 0..7, paper black, no bright\n"
  "        ld hl,ATTRWIN\n"
  "        ld c,12\n"
  "wt1:    ld b,24\n",
  "        ld a,(hl)              ; ceiling ink 0..7, paper black, no bright\n"
  "        ld hl,ATTRWIN\n"
  "        ld c,6                 ; M2.5D: attribute rows 1..6 = window rows 0..47 = ceiling -> level tint\n"
  "        call wt_rows\n"
  "        ld a,FLOORINK          ; M2.5D: attribute rows 7..12 = window rows 48..95 = floor -> FLOORINK; HL is already at row 7 col 4\n"
  "        ld c,6                 ; falls into wt_rows; its ret returns to the caller of win_tint\n"
  "wt_rows:\n"
  "wt1:    ld b,24\n"),
 ("TINTTAB: defb 7,5,6,7          ; level 1 Entry white, 2 Barracks cyan, 3 Furnace yellow, (spare) white\n",
  "TINTTAB: defb 7,5,6,7          ; level 1 Entry white, 2 Barracks cyan, 3 Furnace yellow, (spare) white (ceiling ink)\n"
  "FLOORINK equ 4                 ; M2.5D floor ink: 48K green; make128.py anchor A6 rewrites this line to `equ 2` (red) for the 128K\n"),
]

# ---- 2. make128.py anchor A6
m_pairs = [
 ('        m = re.match(r"^load_level:(.*)$", l)\n',
  '        m = re.match(r"^FLOORINK\\s+equ\\s+4\\b.*$", l)\n'
  '        if m:\n'
  '            out.append("FLOORINK equ 2                 ; T4 128K anchor A6 (M2.5D): red floor on the 128K, green on the 48K")\n'
  '            notes.append("A6 floor ink"); i += 1; continue\n'
  '        m = re.match(r"^load_level:(.*)$", l)\n'),
 ('    missing = [a for a in ("A1 start", "A2 isr", "A3 shim include", "A3 beeper removed", "A4 load_level", "A5 game track")\n',
  '    missing = [a for a in ("A1 start", "A2 isr", "A3 shim include", "A3 beeper removed", "A4 load_level", "A5 game track", "A6 floor ink")\n'),
]

# ---- 3. test_tint.py
t_pairs = [
 ('For level 0/1/2 (+ a stale value 5, masked to 1): init_game must leave all 12 x 16 window attribute cells equal to TINTTAB[level],\n',
  'For level 0/1/2 (+ a stale value 5, masked to 1): init_game must leave the 6 x 24 ceiling cells equal to TINTTAB[level] and the\n'
  '6 x 24 floor cells equal to FLOORINK (M2.5D: 4 green on the 48K image, 2 red with KEA128=1),\n'),
 ('import sys, pathlib\n', 'import sys, os, pathlib\n'),
 ('def win(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(12) for c in range(24)]\n',
  'def ceil(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(6) for c in range(24)]            # attr rows 1..6 = ceiling\n'
  'def floor(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(6, 12) for c in range(24)]       # attr rows 7..12 = floor\n'),
 ('    if tab[:3] != bytes([7, 5, 6]): print("   FAIL: expected white, cyan, yellow"); fails += 1\n',
  '    if tab[:3] != bytes([7, 5, 6]): print("   FAIL: expected white, cyan, yellow"); fails += 1\n'
  '    fink = SYM["FLOORINK"]; want_f = 2 if os.environ.get("KEA128") else 4\n'
  '    print("FLOORINK", fink, "(M2.5D: 48K green 4 / 128K red 2; this image expects %d)" % want_f)\n'
  '    if fink != want_f: print("   FAIL: FLOORINK"); fails += 1\n'),
 ('        want = tab[lvl & 3]\n        w = win(m)\n        bad = [i for i, v in enumerate(w) if v != want]\n',
  '        want = tab[lvl & 3]\n'
  '        bad = [i for i, v in enumerate(ceil(m)) if v != want] + [i for i, v in enumerate(floor(m)) if v != fink]\n'),
 ('        w2 = win(m); bad2 = [i for i, v in enumerate(w2) if v != want]\n',
  '        bad2 = [i for i, v in enumerate(ceil(m)) if v != want] + [i for i, v in enumerate(floor(m)) if v != fink]\n'),
 ('        print("level byte %d -> ink %d: window cells wrong after init_game %d, after render %d, frame+HUD unchanged %s" % (lvl, want, len(bad), len(bad2), hud_ok))\n',
  '        print("level byte %d -> ceiling ink %d floor ink %d: window cells wrong after init_game %d, after render %d, frame+HUD unchanged %s" % (lvl, want, fink, len(bad), len(bad2), hud_ok))\n'),
]

# ---- 5. test_128.py: anchor census 5 removed / 8 added -> 6 / 9 (A6 FLOORINK line)
t128_pairs = [
 ('exp = [r"^start:\\s+di\\b", r"^\\s*xor a\\s*$", r"^load_level:", r"^isr:\\s+push hl\\b", r\'^\\s*include "../common/beeper.asm"\']\n',
  'exp = [r"^start:\\s+di\\b", r"^\\s*xor a\\s*$", r"^load_level:", r"^isr:\\s+push hl\\b", r\'^\\s*include "../common/beeper.asm"\',\n'
  '       r"^FLOORINK\\s+equ\\s+4\\b"]          # M2.5D anchor A6: the 128K floor ink line\n'),
 ('check(len(removed) == 5 and all(any(re.match(p, l) for p in exp) for l in removed), "make128: removed lines = 5 anchored originals %r" % removed)\n',
  'check(len(removed) == 6 and all(any(re.match(p, l) for p in exp) for l in removed), "make128: removed lines = 6 anchored originals %r" % removed)\n'),
 ('check(all("T4 128K anchor" in l or l.strip() in ("di", "push hl") for l in added) and len(added) == 8, "make128: %d added lines all anchor-marked" % len(added))\n',
  'check(all("T4 128K anchor" in l or l.strip() in ("di", "push hl") for l in added) and len(added) == 9, "make128: %d added lines all anchor-marked" % len(added))\n'),
]

# ---- 4. m25c_shots.py
s_pairs = [
 ('    ink = m.memory[22564]\n    p = ROOT / ("build/m25c_l%d.png" % lvl); scr_to_png(scr, str(p))\n'
  '    print("level %d start (%d,%d) angle %d: window ink %d -> %s" % (lvl, sx, sy, ang, ink, p.name))\n'
  '    shots.append((p, "level %d  ink %d" % (lvl, ink)))\n',
  '    ink, fink = m.memory[22564], m.memory[22564 + 6 * 32]          # M2.5D: ceiling ink (attr row 1), floor ink (attr row 7)\n'
  '    p = ROOT / ("build/m25d_l%d.png" % lvl); scr_to_png(scr, str(p))\n'
  '    print("level %d start (%d,%d) angle %d: ceiling ink %d floor ink %d -> %s" % (lvl, sx, sy, ang, ink, fink, p.name))\n'
  '    shots.append((p, "level %d  ceiling %d floor %d" % (lvl, ink, fink)))\n'),
 ('out = ROOT / "build/m25c_strip.png"', 'out = ROOT / "build/m25d_strip.png"'),
]

if __name__ == "__main__":
    edit(K, k_pairs, "FLOORINK")
    edit(M, m_pairs, "A6 floor ink")
    edit(T, t_pairs, "FLOORINK")
    edit(S, s_pairs, "m25d_strip")
    edit(T128, t128_pairs, "M2.5D anchor A6")
