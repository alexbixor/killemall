#!/usr/bin/env python3
"""t6_patch_d.py - mktap48.py: BASIC loader hides the ROM 'Bytes:' messages (BORDER 0 / PAPER 0 / INK 0 / CLS, lower-screen
attr 0 via POKE 23624,0, PRINT AT 21,0; before the code LOAD so the message lands in the black band under the title),
and the pasmo code header is renamed 'killemall'."""
import pathlib
P = pathlib.Path("tools/mktap48.py"); s = P.read_text()
old = 'T = {"CLEAR": 0xFD, "POKE": 0xF4, "LOAD": 0xEF, "CODE": 0xAF, "SCREEN$": 0xAA, "RANDOMIZE": 0xF9, "USR": 0xC0}\n'
new = ('from tapdump import TOKENS\n'
       'T = {name: code for code, name in TOKENS.items()}      # keyword -> token byte (BORDER, PAPER, INK, CLS, PRINT, AT, ...)\n')
assert s.count(old) == 1; s = s.replace(old, new)
old = s[s.index("def basic_loader(clear_value, n_code_blocks):"):s.index("def main():")]
new = '''def basic_loader(clear_value, n_code_blocks):
    prog = line(10, bytes([T["CLEAR"]]) + num(clear_value))
    prog += line(20, bytes([T["POKE"]]) + num(23610) + b"," + num(255))
    # black on black everywhere (upper screen ATTR_P and lower screen BORDCR) so the ROM "Bytes: name" messages are invisible
    prog += line(30, bytes([T["BORDER"]]) + num(0) + b":" + bytes([T["PAPER"]]) + num(0) + b":" + bytes([T["INK"]]) + num(0)
                 + b":" + bytes([T["CLS"]]) + b":" + bytes([T["POKE"]]) + num(23624) + b"," + num(0))
    prog += line(40, bytes([T["LOAD"]]) + b'""' + bytes([T["SCREEN$"]]))
    ln = 50
    for _ in range(n_code_blocks):
        prog += line(ln, bytes([T["PRINT"], T["AT"]]) + num(21) + b"," + num(0) + b";"); ln += 10   # message row 21 (black band)
        prog += line(ln, bytes([T["LOAD"]]) + b'""' + bytes([T["CODE"]])); ln += 10
    prog += line(ln, bytes([T["RANDOMIZE"], T["USR"]]) + num(32768))
    return prog

'''
s = s.replace(old, new)
old = '''    for h, d in code:
        tape += struct.pack("<H", len(h)) + bytes(h) + struct.pack("<H", len(d)) + bytes(d)
'''
new = '''    for h, d in code:
        length, p1, p2 = struct.unpack_from("<HHH", h, 12)
        tape += header(3, "killemall", length, p1, p2)          # pasmo names the block after the output path: rename
        tape += struct.pack("<H", len(d)) + bytes(d)
'''
assert s.count(old) == 1; s = s.replace(old, new)
P.write_text(s); print("patched mktap48.py")
