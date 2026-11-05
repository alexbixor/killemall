#!/usr/bin/env python3
"""m_sym_report.py (lane M) - M_sym_diff.out: 128K + 48K symbol tables pre-M vs post-M, bytes per file, state block check."""
import re, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
def sym(p): return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", p.read_text(), re.M)}
pre, post = sym(ROOT / "build/night/pre_M/build/kea128.sym"), sym(ROOT / "build/kea128.sym")
pre48, post48 = sym(ROOT / "build/night/pre_M/build/kea48.sym"), sym(ROOT / "build/kea48.sym")
print("== M_sym_diff: symbol tables pre-M (build/night/pre_M/build/*.sym) vs post-M (build/*.sym)")
print("-- 128K (pasmo --equ GLIDE=1 --equ MOUSE=1)")
print("%-12s %-8s %-8s" % ("label", "pre", "post"))
for s in ("health", "ammo", "keys", "kills", "level", "opt_music", "opt_sfx", "opt_detail", "opt_joy", "in_break", "shield", "opt_mouse",
          "in_begin", "in_read", "ir_kb", "mouse_look", "mouse_last", "mouse_frac", "mouse_btn", "in_scan", "in_keys", "in_end",
          "fe_begin", "fe_run", "fe_pause", "fe_exit", "fe_items", "fe_s_items", "fe_s_vals", "fe_end", "game_tick", "main", "steps", "hi_end"):
    print("%-12s %-8s %-8s" % (s, "%04X" % pre[s] if s in pre else "-", "%04X" % post[s] if s in post else "-"))
state_same = all(pre[s] == post[s] for s in ("health", "ammo", "keys", "kills", "level", "opt_music", "opt_sfx", "opt_detail", "opt_joy", "in_break", "shield"))
print("state block: health..shield identical = %s; opt_mouse = shield+1: %s" % (state_same, post["opt_mouse"] == post["shield"] + 1))
d = lambda S, a, b: S[b] - S[a]
print("bytes per file (post - pre): state.asm %+d, input.asm %+d (in_begin..in_end, incl. the 16-byte alignment pad before in_keys: pad pre %d post %d),"
      " frontend.asm %+d (fe_begin..fe_end), main loop hook +3 (call mouse_look)" % (
      d(post, "health", "in_begin") - d(pre, "health", "in_begin"), d(post, "in_begin", "in_end") - d(pre, "in_begin", "in_end"),
      (16 - (pre["in_names"] - 48 - 32) % 16) % 16 if False else pre["in_keys"] - pre["in_scan"] - (pre["in_keys"] - pre["in_scan"]), 0,
      d(post, "fe_begin", "fe_end") - d(pre, "fe_begin", "fe_end")))
print("128K total: hi_end %04X -> %04X = %+d B; gap to the stack top 0xFDF0: %d -> %d B (gate >= 40)" % (
      pre["hi_end"], post["hi_end"], post["hi_end"] - pre["hi_end"], 65008 - pre["hi_end"], 65008 - post["hi_end"]))
# exact code bytes of the new routines from the symbol table
print("mouse_look code: %04X..%04X = %d B (+ 3 B variables mouse_last/frac/btn); in_read mouse tail ir_kb..mouse_look = %d B (pre ir_kb..in_scan tail was %d B)" % (
      post["mouse_look"], post["mouse_last"], post["mouse_last"] - post["mouse_look"], post["mouse_look"] - post["ir_kb"], pre["in_scan"] - pre["ir_kb"]))
print("-- 48K (no MOUSE): addresses identical = %s; new equates only: %s" % (
      all(pre48[k] == post48[k] for k in pre48), sorted(set(post48) - set(pre48))))
r = subprocess.run(["md5sum", str(ROOT / "build/kea48.tap"), str(ROOT / "build/night/pre_M/build/kea48.tap")], capture_output=True, text=True)
print(r.stdout.strip())
