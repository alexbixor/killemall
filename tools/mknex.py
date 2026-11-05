#!/usr/bin/env python3
"""mknex.py - M2.7 (3 Nov 2026): wrap the 128K edition into a Spectrum Next .nex file (NEX V1.2, wiki.specnext.dev/NEX_file_format).
The Next runs the 128K edition in its 128K compatibility mode until the Next engine (M3) exists: same memory layout as the 128K
tape (bank 5 = 0x4000..0x7FFF, bank 2 = 0x8000..0xBFFF, bank 0 = 0xC000..0xFFFF entry bank, bank 1 = AY player + music + levels,
paged at 0xC000 by shim128.asm through port 7FFD), so the raw 16K banks of the file are:
  bank 5 : title.scr at 0x4000 (keeps the loading screen on), zeros, the engine image part below 0x8000 (from 0x6C00)
  bank 2 : engine image 0x8000..0xBFFF
  bank 0 : engine image 0xC000..hi_end (stack and IM2 table are built by start)
  bank 1 : build/bank1.bin (what the tape's bank loader stub LD-BYTES into bank 1)
Header: ULA loading screen (title.scr), no palette, border 0, SP 65008, PC = ENTRY (below), entry bank 0, file closed.
ENTRY (0x6000, bank 5, spare RAM the engine's BUF reuses later - the same slot the 128K tape's bank loader stub uses): selects
ROM 3 = 48 BASIC (port 1FFD = 0x04 ROM high bit, port 7FFD = 0x10 ROM low bit + bank 0, BANKM 23388 = 0x10) and jumps to start
(32768). Needed because the engine prints its menu with the 48K ROM font at 0x3D00 and shim128.asm only ever writes port 7FFD:
on a +2A/+3/Next with 1FFD bit 2 clear, 7FFD bit 4 alone selects ROM 1 (128 syntax ROM), whose 0x3D00 is not a font.
usage: mknex.py build/kea128.tap build/bank1.bin build/title.scr build/killemall128.nex"""
import sys, struct, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mktap128 import code_block

BANK = 16384
ORDER = [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112))      # bank data order in the file
ENTRY = 0x6000
STUB = bytes([0xED, 0x91, 0x07, 0x03,                         # nextreg 7,3  (Z80N)                  CPU 28 MHz (M2.9, 4 Nov 2026): the game logic
                                                              #   is a fixed 10 steps/s from the 50 Hz counter now (kea48.asm steps), so speed no
                                                              #   longer depends on the frame rate; the display is capped at 10 frames/s by the
                                                              #   halt wait. M2.7 forced 3.5 MHz (nextreg 7,0) because 28 MHz gave 19 fps = 3x too fast.
              0x3E, 0x04, 0x01, 0xFD, 0x1F, 0xED, 0x79,       # ld a,4 / ld bc,1FFDh / out (c),a     ROM high bit, normal paging
              0x3E, 0x10, 0x01, 0xFD, 0x7F, 0xED, 0x79,       # ld a,10h / ld bc,7FFDh / out (c),a   ROM 3 (48 BASIC), bank 0
              0x32, 0x5C, 0x5B,                               # ld (23388),a                        BANKM
              0xC3, 0x00, 0x80])                              # jp 32768                            start

def main():
    start, code = code_block(pathlib.Path(sys.argv[1]).read_bytes())
    bank1 = pathlib.Path(sys.argv[2]).read_bytes(); scr = pathlib.Path(sys.argv[3]).read_bytes(); out = pathlib.Path(sys.argv[4])
    assert len(scr) == 6912 and 0x4000 <= start < 0x8000 and start + len(code) <= 65008 and len(bank1) <= BANK, (start, len(code))
    mem = bytearray(65536)
    mem[0x4000:0x4000 + 6912] = scr
    mem[ENTRY:ENTRY + len(STUB)] = STUB
    mem[start:start + len(code)] = code
    assert start >= ENTRY + len(STUB)
    banks = {5: bytes(mem[0x4000:0x8000]), 2: bytes(mem[0x8000:0xC000]), 0: bytes(mem[0xC000:0x10000]), 1: bank1.ljust(BANK, b"\0")}
    h = bytearray(512)
    h[0:4] = b"Next"; h[4:8] = b"V1.2"
    h[8] = 0                          # RAM required: 768K
    h[9] = len(banks)                 # banks to load
    h[10] = 2 | 128                   # ULA loading screen, no palette block
    h[11] = 0                         # border black
    struct.pack_into("<H", h, 12, 65008)          # SP (start sets it again)
    struct.pack_into("<H", h, 14, ENTRY)          # PC = ROM-select stub -> start
    struct.pack_into("<H", h, 16, 0)              # extra files
    for b in banks: h[18 + b] = 1
    h[130] = 0; h[131] = 0            # no Layer 2 loading bar
    h[132] = 0; h[133] = 0            # no per-bank / start delay
    h[134] = 0                        # reset Next registers (plain 128K machine state)
    h[135:138] = bytes([0, 0, 0])     # no core version requirement
    h[138] = 0
    h[139] = 0                        # entry bank 0 at 0xC000
    struct.pack_into("<H", h, 140, 0)             # loader closes the file
    data = bytes(h) + scr + b"".join(banks[b] for b in ORDER if b in banks)
    out.write_bytes(data)
    print("wrote %s: %d bytes = header 512 + ULA screen 6912 + %d banks x 16384 (%s); code %d B at 0x%04X..0x%04X, bank1 %d B, PC 0x%04X (ROM-3 stub) -> start 32768, SP 65008" % (
        out, len(data), len(banks), ",".join(str(b) for b in ORDER if b in banks), len(code), start, start + len(code) - 1, len(bank1), ENTRY))

if __name__ == "__main__":
    main()
