#!/usr/bin/env python3
"""sym_equs.py (lane K1, 6 Nov 2026) - print `--equ NAME=value` pasmo arguments for the named symbols of a pasmo .sym file.
usage: sym_equs.py build/kea128_hires.sym isr zbuf BUF ...   (replaces the heredoc in tools/build128_hires.sh: the sandbox
the night lanes run in rejects heredocs on a command line). Exits 1 when a symbol is missing."""
import re, sys, pathlib
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(sys.argv[1]).read_text(), re.M)}
missing = [k for k in sys.argv[2:] if k not in S]
if missing:
    sys.exit("sym_equs: missing symbols in %s: %s" % (sys.argv[1], missing))
print(" ".join("--equ %s=%d" % (k, S[k]) for k in sys.argv[2:]))
