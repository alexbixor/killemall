#!/usr/bin/env python3
"""m23_edit_keys.py - M2.3 step 1: SPACE = fire, M = use/open (defaults only; REDEFINE KEYS untouched).
Edits: src/common/input.asm (in_keys + header comment), tools/test_frontend.py (default table + in_read cases),
tools/deck/launch-killemall.sh (pad A -> SPACE 32, X -> M 109, comment), tools/m22_pad_test.py (expectations),
tools/t6_demo.py + tools/t6_playthrough.py (fire key M -> SPACE). Idempotent: exits 2 if a pattern is not found."""
import pathlib, sys, re
ROOT = pathlib.Path.home() / "work/killemall"
def sub(path, pairs):
    p = ROOT / path; t = p.read_text()
    for old, new in pairs:
        if old not in t:
            if new in t: continue                      # already applied
            print("NOT FOUND in %s: %r" % (path, old[:60])); sys.exit(2)
        t = t.replace(old, new, 1)
    p.write_text(t); print("edited", path)
sub("src/common/input.asm", [
    ("in action-bit order, defaults Q A O P M SPACE Z X.", "in action-bit order, defaults Q A O P SPACE M Z X (M2.3: SPACE fires, M opens)."),
    ("        defb 0x7F,0x04         ; M  fire\n        defb 0x7F,0x01         ; SPACE use/open\n",
     "        defb 0x7F,0x01         ; SPACE fire (M2.3; was M)\n        defb 0x7F,0x04         ; M  use/open (M2.3; was SPACE)\n"),
])
sub("tools/test_frontend.py", [
    ('check(keys0 == bytes([0xFB, 1, 0xFD, 1, 0xDF, 2, 0xDF, 1, 0x7F, 4, 0x7F, 1, 0xFE, 2, 0xFE, 4]), "default in_keys Q A O P M SPACE Z X")',
     'check(keys0 == bytes([0xFB, 1, 0xFD, 1, 0xDF, 2, 0xDF, 1, 0x7F, 1, 0x7F, 4, 0xFE, 2, 0xFE, 4]), "default in_keys Q A O P SPACE M Z X (M2.3)")'),
    ('(("M",), 0x10), (("SPACE",), 0x20),', '(("SPACE",), 0x10), (("M",), 0x20),'),
    ('(("Q", "P", "M"), 0x19), (("CAPS", "SPACE"), 0x20)]', '(("Q", "P", "SPACE"), 0x19), (("CAPS", "SPACE"), 0x10)]'),
])
sub("tools/deck/launch-killemall.sh", [
    ("# keys (Q A O P M SPACE Z X, CONTROLS = KEYBOARD)", "# keys (Q A O P SPACE M Z X, CONTROLS = KEYBOARD)"),
    ("# keys: 113 q fwd, 97 a back, 111 o left, 112 p right, 109 m fire, 32 space open,", "# keys: 113 q fwd, 97 a back, 111 o left, 112 p right, 32 space fire, 109 m open (M2.3),"),
    ("--joystickkeybt 0 109 --joystickkeybt 2 32", "--joystickkeybt 0 32 --joystickkeybt 2 109"),
    ('(Up=Q Down=A Left=O Right=P Fire=SPACE)', '(Up=Q Down=A Left=O Right=P Fire=SPACE = game fire since M2.3)'),
])
sub("tools/m22_pad_test.py", [
    ('("A              -> M (fire)",       btn(e.BTN_A, 1), btn(e.BTN_A, 0), (["M"], 0)),',
     '("A              -> SPACE (fire)",   btn(e.BTN_A, 1), btn(e.BTN_A, 0), (["SPACE"], 0)),'),
    ('("B              -> joy Fire (=SPACE)", btn(e.BTN_B, 1), btn(e.BTN_B, 0), ([], 0x10)),',
     '("B              -> joy Fire (=SPACE, fire too)", btn(e.BTN_B, 1), btn(e.BTN_B, 0), ([], 0x10)),'),
    ('("X              -> SPACE (open)",   btn(e.BTN_X, 1), btn(e.BTN_X, 0), (["SPACE"], 0)),',
     '("X              -> M (open)",       btn(e.BTN_X, 1), btn(e.BTN_X, 0), (["M"], 0)),'),
    ("# A = M = fire", "# A = SPACE = fire"),
])
sub("tools/t6_demo.py", [('act(["M"], 0.3, 2); shot(2); act(["M"], 0.3, 2); shot(2)      # fire twice',
                          'act(["SPACE"], 0.3, 2); shot(2); act(["SPACE"], 0.3, 2); shot(2)      # fire twice (M2.3: SPACE)')])
sub("tools/t6_playthrough.py", [('if aim_ok or abs(dl) <= tol: keys_now.append("M")', 'if aim_ok or abs(dl) <= tol: keys_now.append("SPACE")')])
print("keys step done")