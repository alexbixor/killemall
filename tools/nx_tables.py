#!/usr/bin/env python3
"""nx_tables.py - the engine's lookup tables (spec docs/next_engine_spec_v0.1.md sections 2, 3, 5, 8).
Writes build/next/tables_bank4.bin = 16 KB for 16K bank 4 (= 8K banks 8 and 9):
  0x0000  jp 8000h (3 bytes)          0x0038  IM1 ISR (spec section 8)        0x0800 SIN  0x1000 COS  0x1800 RD  0x1A00 ZBUF (zeros)
  0x2000  RECIP (4096 words)
Also importable: SIN, COS, RD, RECIP lists."""
import math, pathlib, struct
ROOT = pathlib.Path(__file__).resolve().parent.parent
SIN = [int(round(256 * math.sin(2 * math.pi * a / 1024))) for a in range(1024)]
COS = [int(round(256 * math.cos(2 * math.pi * a / 1024))) for a in range(1024)]
RD = [65535] + [min(65535, 65536 // k) for k in range(1, 256)]
RECIP = [65535] + [min(65535, 65536 // i) for i in range(1, 4096)]
# ISR exactly as in the spec: ld (isr_sp),sp ; ld sp,ISR_STACK ; push hl ; ld hl,(ticks) ; inc hl ; ld (ticks),hl ; pop hl ; ld sp,(isr_sp) ; ei ; reti
TICKS, ISR_SP, ISR_STACK = 0x5808, 0x580C, 0x5FF0
ISR = (bytes([0xED, 0x73]) + struct.pack("<H", ISR_SP) + bytes([0x31]) + struct.pack("<H", ISR_STACK) + bytes([0xE5, 0x2A]) + struct.pack("<H", TICKS)
       + bytes([0x23, 0x22]) + struct.pack("<H", TICKS) + bytes([0xE1, 0xED, 0x7B]) + struct.pack("<H", ISR_SP) + bytes([0xFB, 0xED, 0x4D]))

def bank():
    b = bytearray(16384)
    b[0:3] = bytes([0xC3, 0x00, 0x80])
    b[0x38:0x38 + len(ISR)] = ISR
    for i, v in enumerate(SIN): struct.pack_into("<h", b, 0x0800 + 2 * i, v)
    for i, v in enumerate(COS): struct.pack_into("<h", b, 0x1000 + 2 * i, v)
    for i, v in enumerate(RD): struct.pack_into("<H", b, 0x1800 + 2 * i, v)
    for i, v in enumerate(RECIP): struct.pack_into("<H", b, 0x2000 + 2 * i, v)
    return bytes(b)

if __name__ == "__main__":
    out = ROOT / "build/next/tables_bank4.bin"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bank())
    print("wrote %s (%d bytes); SIN[256]=%d COS[0]=%d RD[1]=%d RD[255]=%d RECIP[1]=%d RECIP[4095]=%d ISR %d bytes" % (out, out.stat().st_size, SIN[256], COS[0], RD[1], RD[255], RECIP[1], RECIP[4095], len(ISR)))
