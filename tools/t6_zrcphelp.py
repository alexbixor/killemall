#!/usr/bin/env python3
"""t6_zrcphelp.py - dump ZRCP 'help' (command list) and a few 'help <cmd>' entries to build/t6_zrcphelp.out"""
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from t6_zes import Zes
z = Zes("build/t6_test_C.tap", port=10152)
out = [z.cmd("help", 1.0)]
for c in sys.argv[1:]:
    out.append("=== help %s ===\n" % c + z.cmd("help " + c, 0.5))
z.close()
pathlib.Path("build/t6_zrcphelp.out").write_text("\n".join(out))
print("written", sum(len(o) for o in out), "chars")
