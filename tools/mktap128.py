#!/usr/bin/env python3
"""mktap128.py - build the 128K tape build/killemall128_m2.tap (lane T4):
  BASIC autostart (CLEAR of the 48K tape, POKE 23610,255, black screen) -> LOAD ""SCREEN$ (build/title.scr)
  -> LOAD ""CODE 24576 (34-byte bank loader stub, see STUB) -> RANDOMIZE USR 24576 (pages bank 1, LD-BYTES the
     headerless bank1.bin block to 49152, pages bank 0 back)
  -> LOAD ""CODE 27904 (engine image = the 128K code block) -> RANDOMIZE USR 32768.
The stub changes ONLY bits 0..2 of port 7FFDh (bits 3..5 = screen/ROM come from BANKM 23388, which it keeps updated).
It sits at 24576 (spare RAM between the BASIC workspace and the stack under RAMTOP 27903; the engine's BUF reuses the
area later) and NOT at 23296: the 128K editor ROM keeps its paging routines/variables at 5B00h..5BFFh.
usage: mktap128.py kea128.tap(pasmo --tap) bank1.bin title.scr out.tap"""
import sys, struct, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tapdump import TOKENS
T = {name: code for code, name in TOKENS.items()}
CLEAR = 27903          # overwritten in main(): code start - 1 (M2.5C: the image starts at 0x6C00)
STUB_AT = 24576
# Bank loader stub (never returns to BASIC with bank 1 paged - the 128 ROM/editor resets if it does, build/dbg128.out):
#   ld a,11h / ld bc,7FFDh / di / out (c),a      page bank 1 at 49152 (ROM 1, screen 0: fixed, see shim128.asm PAGEN)
#   ld ix,C000h / ld de,LEN / ld a,FFh / scf / call 0556h   LD-BYTES: next headerless block (bank1.bin) -> bank 1
#   ld a,10h / ld bc,7FFDh / di / out (c),a / xor a / out (FEh),a / ei / ret   bank 0 back, border black
STUB = bytes([0x3E, 0x11, 0x01, 0xFD, 0x7F, 0xF3, 0xED, 0x79,
              0xDD, 0x21, 0x00, 0xC0, 0x11, 0x00, 0x00, 0x3E, 0xFF, 0x37, 0xCD, 0x56, 0x05,
              0x3E, 0x10, 0x01, 0xFD, 0x7F, 0xF3, 0xED, 0x79, 0xAF, 0xD3, 0xFE, 0xFB, 0xC9])
STUB_LEN_AT = 13                      # offset of the `ld de,LEN` operand

def num(v):
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
    return tap_block(0, bytes([typ]) + name.encode("latin1")[:10].ljust(10) + struct.pack("<HHH", length, p1, p2))

def tok(*names):
    return bytes(T[n] for n in names)

def basic_loader():
    L = []
    L.append(line(10, tok("CLEAR") + num(CLEAR)))
    L.append(line(20, tok("POKE") + num(23610) + b"," + num(255)))
    L.append(line(30, tok("BORDER") + num(0) + b":" + tok("PAPER") + num(0) + b":" + tok("INK") + num(0) + b":" + tok("CLS")
                  + b":" + tok("POKE") + num(23624) + b"," + num(0)))
    L.append(line(40, tok("LOAD") + b'""' + tok("SCREEN$")))
    ln = 50
    def load_code():
        nonlocal ln
        L.append(line(ln, tok("PRINT", "AT") + num(20) + b"," + num(0) + b";")); ln += 10   # "Bytes:" lands on a black row
        L.append(line(ln, tok("LOAD") + b'""' + tok("CODE"))); ln += 10
    def page(bank):
        nonlocal ln
        L.append(line(ln, tok("POKE") + num(STUB_BANK_BYTE) + b"," + num(0x10 + bank) + b":" + tok("RANDOMIZE", "USR") + num(STUB_AT))); ln += 10
    load_code()            # stub -> 24576
    L.append(line(ln, tok("RANDOMIZE", "USR") + num(STUB_AT))); ln += 10      # stub loads bank1.bin into bank 1 itself
    load_code()            # engine image -> 27904.. (bank 0 above 49152)
    L.append(line(ln, tok("RANDOMIZE", "USR") + num(32768)))
    return b"".join(L)

def code_block(tap):
    """(start, bytes) of the single CODE block of a pasmo --tap / --tapbas tape (last CODE header wins)."""
    from tapdump import blocks
    bl = blocks(tap); res = None
    for i, b in enumerate(bl):
        if b[0] == 0 and len(b) == 19 and b[1] == 3:
            length, start = struct.unpack_from("<HH", b, 12)
            res = (start, bytes(bl[i + 1][1:1 + length]))
    assert res, "no CODE block in %s" % tap
    return res

def main():
    global CLEAR
    start, code = code_block(pathlib.Path(sys.argv[1]).read_bytes())
    CLEAR = start - 1                                   # M2.5C: RAMTOP just below the first loaded byte
    bank1 = pathlib.Path(sys.argv[2]).read_bytes(); scr = pathlib.Path(sys.argv[3]).read_bytes(); out = pathlib.Path(sys.argv[4])
    # lane G (5 Nov 2026): the image ends at 0FFF0h now (ETAB + enemy step code at 0FF01h, above the IM2 table): the bytes it
    # loads over the stack / TABLE area (hi_end..0FF00h = zeros) are rewritten by start; the loader's own stack is below RAMTOP.
    assert len(scr) == 6912 and start > CLEAR and start + len(code) <= 65536 and len(bank1) <= 16384
    prog = basic_loader()
    tape = header(0, "killemall", len(prog), 10, len(prog)) + tap_block(0xFF, prog)
    tape += header(3, "title", 6912, 16384, 32768) + tap_block(0xFF, scr)
    stub = bytearray(STUB); stub[STUB_LEN_AT:STUB_LEN_AT + 2] = struct.pack("<H", len(bank1))
    tape += header(3, "page", len(stub), STUB_AT, 32768) + tap_block(0xFF, bytes(stub))
    tape += tap_block(0xFF, bank1)                                   # headerless, loaded by the stub (LD-BYTES)
    tape += header(3, "killemall", len(code), start, 32768) + tap_block(0xFF, code)
    out.write_bytes(tape)
    print("wrote %s: %d bytes (BASIC %d, stub %d @%d, bank1 %d @49152, code %d @%d..%d)" % (
        out, len(tape), len(prog), len(STUB), STUB_AT, len(bank1), len(code), start, start + len(code) - 1))

if __name__ == "__main__":
    main()
