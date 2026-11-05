#!/usr/bin/env python3
"""mktap48.py - build the final 48K tape: BASIC autostart loader + SCREEN$ (title) + pasmo code block(s) [+ raw blocks].
usage: mktap48.py in.tap title.scr out.tap [--raw file.bin ...]
 * the BASIC of in.tap (pasmo --tapbas) is reproduced: its CLEAR value is kept, POKE 23610,255 kept, a LOAD ""SCREEN$
   line is inserted before the LOAD ""CODE line(s), last line RANDOMIZE USR 32768
 * block 2 = title.scr as a SCREEN$ (header type 3, start 16384, len 6912)
 * then every Code header+data block of in.tap copied verbatim
 * --raw: extra headerless blocks (flag 0xFF) appended in order (e.g. levels 02/03 loaded with LD-BYTES)
All TAP checksums = XOR of flag + data."""
import sys, struct, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tapdump import blocks, detok

from tapdump import TOKENS
T = {name: code for code, name in TOKENS.items()}      # keyword -> token byte (BORDER, PAPER, INK, CLS, PRINT, AT, ...)

def num(v):
    """ASCII digits + hidden 5-byte integer form (0x0E 00 00 lo hi 00)"""
    return str(v).encode() + bytes([0x0E, 0, 0, v & 255, v >> 8, 0])

def line(ln, body):
    body = body + b"\r"
    return bytes([ln >> 8, ln & 255]) + struct.pack("<H", len(body)) + body

def tap_block(flag, payload):
    chk = flag
    for x in payload: chk ^= x
    b = bytes([flag]) + payload + bytes([chk])
    return struct.pack("<H", len(b)) + b

def header(typ, name, length, p1, p2):
    nm = name.encode("latin1")[:10].ljust(10)
    return tap_block(0, bytes([typ]) + nm + struct.pack("<HHH", length, p1, p2))

def basic_loader(clear_value, n_code_blocks):
    prog = line(10, bytes([T["CLEAR"]]) + num(clear_value))
    prog += line(20, bytes([T["POKE"]]) + num(23610) + b"," + num(255))
    # black on black everywhere (upper screen ATTR_P and lower screen BORDCR) so the ROM "Bytes: name" messages are invisible
    prog += line(30, bytes([T["BORDER"]]) + num(0) + b":" + bytes([T["PAPER"]]) + num(0) + b":" + bytes([T["INK"]]) + num(0)
                 + b":" + bytes([T["CLS"]]) + b":" + bytes([T["POKE"]]) + num(23624) + b"," + num(0))
    prog += line(40, bytes([T["LOAD"]]) + b'""' + bytes([T["SCREEN$"]]))
    ln = 50
    for _ in range(n_code_blocks):
        prog += line(ln, bytes([T["PRINT"], T["AT"]]) + num(20) + b"," + num(0) + b";"); ln += 10   # ROM prints CR + "Bytes: name" -> lands on row 21 (black band, ink 0)
        prog += line(ln, bytes([T["LOAD"]]) + b'""' + bytes([T["CODE"]])); ln += 10
    prog += line(ln, bytes([T["RANDOMIZE"], T["USR"]]) + num(32768))
    return prog

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raws = sys.argv[sys.argv.index("--raw") + 1:] if "--raw" in sys.argv else []
    src = pathlib.Path(args[0]).read_bytes(); scr = pathlib.Path(args[1]).read_bytes(); out = pathlib.Path(args[2])
    assert len(scr) == 6912, "title.scr must be 6912 bytes"
    blks = blocks(src)
    # find the BASIC block and its CLEAR value
    clear_value = None; code = []; i = 0
    while i < len(blks):
        b = blks[i]
        if b[0] == 0 and len(b) == 19:
            typ = b[1]; ln = struct.unpack_from("<H", b, 12)[0]
            data = blks[i + 1]
            if typ == 0:
                for l in detok(data[1:1 + ln]):
                    if "CLEAR" in l: clear_value = int(l.split("CLEAR")[1].split()[0])
            elif typ == 3:
                code.append((b, data))
            i += 2
        else:
            i += 1
    assert clear_value is not None and code, "need a BASIC block with CLEAR and >=1 Code block"
    prog = basic_loader(clear_value, len(code))
    tape = header(0, "killemall", len(prog), 10, len(prog)) + tap_block(0xFF, prog)
    tape += header(3, "title", 6912, 16384, 32768) + tap_block(0xFF, scr)
    for h, d in code:
        length, p1, p2 = struct.unpack_from("<HHH", h, 12)
        tape += header(3, "killemall", length, p1, p2)          # pasmo names the block after the output path: rename
        tape += struct.pack("<H", len(d)) + bytes(d)
    for r in raws:
        tape += tap_block(0xFF, pathlib.Path(r).read_bytes())
    out.write_bytes(tape)
    print("wrote %s: %d bytes, CLEAR %d, %d code block(s), %d raw block(s)" % (out, len(tape), clear_value, len(code), len(raws)))

if __name__ == "__main__":
    main()
