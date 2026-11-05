#!/usr/bin/env python3
"""m24_edit_tests.py - M2.4 oracle updates for the cell card (one-shot, idempotent):
 test_game_sprites.py : changed pixels must lie inside the sprite's BYTE-column span (card = whole 8x8 cells), not the
                        ray-column span; a cell whose attribute is the sprite ink must hold no wall pixel -> whole cell black.
 test_sprite_scale.py : silhouette = ink pass only (black pass now measures the card); expected top row uses the asset's
                        first ink row (new art has blank top rows: hunched heads; items start at row 1); the column-span check
                        uses the byte-column span."""
import pathlib, re
T = pathlib.Path.home() / "work/killemall/tools"

def edit(path, pairs):
    s = path.read_text(); n = 0
    for old, new in pairs:
        if new in s and old not in s:
            continue
        assert old in s, (path.name, old[:60])
        s = s.replace(old, new, 1); n += 1
    path.write_text(s); print(path.name, "edits", n)

edit(T / "test_game_sprites.py", [
    ("        span = set(range(max(c0, 0), min(c0 + nc, 64)))\n",
     "        # M2.4 card: the sprite blackens whole 8x8 cells (attribute = sprite ink -> no wall pixel may stay in the cell),\n"
     "        # so changed pixels may lie anywhere in the BYTE columns spanned by the sprite's ray columns (c/4), not only in the\n"
     "        # ray columns themselves.\n"
     "        span = set(range(max(c0 // 4 * 4, 0), min((c0 + nc - 1) // 4 * 4 + 4, 64)))\n"),
])

edit(T / "test_sprite_scale.py", [
    ("    rows = [r for c, r in p1 + p2]\n    return (min(rows), max(rows), c1 | c2) if rows else (None, None, c1 | c2)\n",
     "    # M2.4: the black pass now measures the cell card (whole cells, up to 7 rows above/below the ink); the figure = ink pass\n"
     "    rows = [r for c, r in p1]\n    return (min(rows), max(rows), c1 | c2) if rows else (None, None, c1 | c2)\n"),
    ("    cases = [(1, \"imp\", 24), (21, \"barrel\", 12), (16, \"health\", 12)]\n",
     "    cases = [(1, \"imp\", 24), (21, \"barrel\", 12), (16, \"health\", 12)]\n"
     "    # M2.4: first ink row of each asset (art is bottom-aligned in the 24-row box; blank top rows = hunched heads / items)\n"
     "    first_ink = {}\n"
     "    for typ, name, asset_h in cases:\n"
     "        f = {1: \"00_imp_walk_a.txt\", 21: \"12_barrel.txt\", 16: \"08_health.txt\"}[typ]\n"
     "        art = [r for r in (ROOT / \"assets/sprites\" / f).read_text().splitlines() if r and not r.startswith(\";\")]\n"
     "        assert len(art) == asset_h, (f, len(art), asset_h)\n"
     "        first_ink[typ] = next(i for i, r in enumerate(art) if \"#\" in r)\n"),
    ("            exp_top = base - hd * asset_h // 24\n            if top is None or abs(top - exp_top) > 1: ok = False\n            if asset_h == 12 and (top is None or abs(top - 48) > 1): ok = False\n",
     "            exp_top = base - hd + hd * (24 - asset_h + first_ink[typ]) // 24     # ROWTAB[v_first], v_first = box row of the first ink\n"
     "            if top is None or abs(top - exp_top) > 1: ok = False\n"
     "            if asset_h == 12 and (top is None or abs(top - (48 + hd * first_ink[typ] // 24)) > 1): ok = False\n"),
    ("            if cols and (min(cols) < max(c0, 0) or max(cols) >= min(c0 + nc, 64)): ok = False\n",
     "            if cols and (min(cols) < max(c0 // 4 * 4, 0) or max(cols) >= min((c0 + nc - 1) // 4 * 4 + 4, 64)): ok = False   # M2.4 card: byte-column span\n"),
])
