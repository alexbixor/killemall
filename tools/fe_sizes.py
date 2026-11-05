#!/usr/bin/env python3
"""fe_sizes.py - report the RAM cost of the T2 lane from a pasmo symbol file: input.asm (in_begin..in_end) and
frontend.asm (fe_begin..fe_end), code+data, plus the in_keys alignment padding. usage: fe_sizes.py build/fe_test.sym"""
import sys, re, pathlib
sym = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", pathlib.Path(sys.argv[1]).read_text(), re.M)}
inp = sym["in_end"] - sym["in_begin"]; fe = sym["fe_end"] - sym["fe_begin"]
pad = sym["in_keys"] - (sym["kn_ok"] + 0)  # rough: bytes between the last code label and in_keys minus kn_ok's code
print("input.asm   %4d bytes  (in_begin %04X .. in_end %04X; in_keys at %04X, in_joytab %04X)" % (inp, sym["in_begin"], sym["in_end"], sym["in_keys"], sym["in_joytab"]))
print("frontend.asm %4d bytes (fe_begin %04X .. fe_end %04X; text from fe_s_items %04X to fe_font %04X = %d bytes, vars %d bytes)" % (
    fe, sym["fe_begin"], sym["fe_end"], sym["fe_s_items"], sym["fe_font"], sym["fe_font"] - sym["fe_s_items"], sym["fe_end"] - sym["fe_font"]))
print("T2 total    %4d bytes of %d budget (font: ROM at 15616, 0 bytes RAM)" % (inp + fe, 1536))
if inp + fe > 1536:
    print("OVER BUDGET by %d bytes" % (inp + fe - 1536))
