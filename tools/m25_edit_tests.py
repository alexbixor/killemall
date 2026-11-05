#!/usr/bin/env python3
"""m25_edit_tests.py - M2.5 step A oracle updates (idempotent):
 test_game_sprites.py : changed pixels back to the sprite's own ray columns (no card -> no whole-byte-column blackening).
 test_sprite_scale.py : (1) silhouette rows = white pass + black pass again (the halo is black, part of the figure);
                        (2) column span = ray columns; (3) attribute check (f) replaced by the one-ink rule: every window
                        attribute cell is 0x07 before and after the sprite (no cell ever changes).
 test_sprite_card.py  : superseded (card removed) -> replaced by test_one_ink.py in m25_gates.sh (file left in place)."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
done = []

def rep(path, old, new, marker):
    p = ROOT / path; s = p.read_text()
    if marker in s and old not in s: return
    assert old in s, "%s anchor missing: %s" % (path, old[:120])
    p.write_text(s.replace(old, new, 1)); done.append("%s: %s" % (path, marker))

rep("tools/test_game_sprites.py",
    "        # M2.4 card: the sprite blackens whole 8x8 cells (attribute = sprite ink -> no wall pixel may stay in the cell),\n"
    "        # so changed pixels may lie anywhere in the BYTE columns spanned by the sprite's ray columns (c/4), not only in the\n"
    "        # ray columns themselves.\n"
    "        span = set(range(max(c0 // 4 * 4, 0), min((c0 + nc - 1) // 4 * 4 + 4, 64)))\n",
    "        span = set(range(max(c0, 0), min(c0 + nc, 64)))      # M2.5: masked blit, only the sprite's own ray columns change\n",
    "M2.5: masked blit")

rep("tools/test_sprite_scale.py",
    "    # M2.4: the black pass now measures the cell card (whole cells, up to 7 rows above/below the ink); the figure = ink pass\n"
    "    rows = [r for c, r in p1]\n",
    "    rows = [r for c, r in p1 + p2]        # M2.5: white runs + black runs (halo) = the figure\n",
    "M2.5: white runs + black runs")
rep("tools/test_sprite_scale.py",
    "            if cols and (min(cols) < max(c0 // 4 * 4, 0) or max(cols) >= min((c0 + nc - 1) // 4 * 4 + 4, 64)): ok = False   # M2.4 card: byte-column span\n",
    "            if cols and (min(cols) < max(c0, 0) or max(cols) >= min(c0 + nc, 64)): ok = False   # M2.5: ray-column span\n",
    "M2.5: ray-column span")
rep("tools/test_sprite_scale.py",
    "            at = attrs(m)\n"
    "            m.set_memory_block(0x6000, bytes(2048)); call(m, \"draw_things\"); spr = buf(m)\n"
    "            cells_with_ink = {(bc, r // 8) for bc in range(16) for r in range(96) if spr[bc * 128 + r]}\n"
    "            touched = set()\n"
    "            for bc in range(16):\n"
    "                rows = [r for r in range(96) if spr[bc * 128 + r]]\n"
    "                if rows: touched |= {(bc, k) for k in range(min(rows) // 8, max(rows) // 8 + 1)}\n"
    "            ink = TYPEINK[typ]\n"
    "            bad = [(bc, r) for (bc, r) in cells_with_ink if at[r][bc] != ink]\n"
    "            stray = [(bc, r) for r in range(12) for bc in range(16) if (bc, r) not in touched and at[r][bc] != a0[r][bc]]\n"
    "            if bad or stray:\n"
    "                print(\"      attr FAIL: cells with ink but wrong attr %s, changed attr without ink %s\" % (bad[:4], stray[:4])); fails += 1\n",
    "            # M2.5 one-ink rule: the sprite changes no window attribute cell (the value itself, 0x07 after cls, is checked by\n"
    "            # test_one_ink.py; the oracle machine never ran cls)\n"
    "            at = attrs(m)\n"
    "            bad = [(bc, r) for r in range(12) for bc in range(16) if at[r][bc] != a0[r][bc]]\n"
    "            if bad:\n"
    "                print(\"      attr FAIL: window cells changed by the sprite %s\" % bad[:6]); fails += 1\n",
    "M2.5 one-ink rule")
rep("tools/test_sprite_scale.py",
    "        first_ink[typ] = next(i for i, r in enumerate(art) if \"#\" in r)\n",
    "        first_ink[typ] = next(i for i, r in enumerate(art) if \"#\" in r)\n"
    "        if typ < 16: first_ink[typ] = max(0, first_ink[typ] - 1)      # M2.5: enemies carry a 1-px black halo above the head\n",
    "M2.5: enemies carry a 1-px black halo")
print("m25_edit_tests:", "; ".join(done) if done else "already applied")
