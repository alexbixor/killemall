#!/usr/bin/env python3
"""m23_deadcode.py - READ-ONLY: labels defined in kea48.asm + common/*.asm that nothing references (candidates to free bytes).
Size = distance to the next symbol in build/kea48.sym (upper bound of the routine/data size)."""
import re, pathlib
ROOT = pathlib.Path.home() / "work/killemall"
srcs = [ROOT / "src/48k/kea48.asm"] + sorted((ROOT / "src/common").glob("*.asm")) + sorted((ROOT / "src/48k/gen").glob("*.asm"))
text = {p: p.read_text(errors="replace") for p in srcs}
alltext = "\n".join(text.values())
sym = {}
for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48.sym").read_text(), re.M):
    sym[m.group(1)] = int(m.group(2), 16)
addrs = sorted(set(sym.values()))
def size_of(lbl):
    a = sym.get(lbl)
    if a is None: return -1
    nxt = [x for x in addrs if x > a]
    return (nxt[0] - a) if nxt else -1
defs = []
for p in srcs[:1] + srcs[1:len(srcs) - len(list((ROOT / "src/48k/gen").glob("*.asm")))]:
    for m in re.finditer(r"^(\w+):", text[p], re.M):
        defs.append((m.group(1), p.name))
dead = []
for lbl, fn in defs:
    refs = len(re.findall(r"\b" + re.escape(lbl) + r"\b", alltext)) - 1   # minus the definition
    if refs <= 0:
        dead.append((size_of(lbl), lbl, fn))
for sz, lbl, fn in sorted(dead, reverse=True):
    print("%5d B  %-16s %s" % (sz, lbl, fn))
print("unreferenced labels:", len(dead), " total upper-bound bytes:", sum(s for s, _, _ in dead if s > 0))