#!/usr/bin/env python3
"""m30_bench_nex.py - assemble build/m30_bench.asm (pasmo) and wrap it into build/m30_bench.nex for the Spectrum Next:
bank 5 = zeros (LoRes screen), bank 2 = benchmark code at 0x8000, bank 0 = textures (build/m30_bench_bank0.bin at 0xC000).
No loading screen, PC = 0x8000, SP = 0xBFF0. Prints the symbol addresses the runner needs."""
import pathlib, re, struct, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
B = ROOT / "build"
r = subprocess.run(["pasmo", "--bin", str(B / "m30_bench.asm"), str(B / "m30_bench.bin"), str(B / "m30_bench.sym")], capture_output=True, text=True)
if r.returncode: sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
code = (B / "m30_bench.bin").read_bytes()
S = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (B / "m30_bench.sym").read_text(), re.M)}
assert len(code) <= 16384 - 0x10, len(code)
bank0 = (B / "m30_bench_bank0.bin").read_bytes(); assert len(bank0) == 16384
banks = {5: bytes(16384), 2: code.ljust(16384, b"\0"), 0: bank0}
ORDER = [5, 2, 0]
h = bytearray(512)
h[0:4] = b"Next"; h[4:8] = b"V1.2"
h[8] = 0; h[9] = len(banks); h[10] = 0; h[11] = 0
struct.pack_into("<H", h, 12, 0xBFF0); struct.pack_into("<H", h, 14, 0x8000); struct.pack_into("<H", h, 16, 0)
for b in banks: h[18 + b] = 1
h[139] = 0; struct.pack_into("<H", h, 140, 0)
out = B / "m30_bench.nex"
out.write_bytes(bytes(h) + b"".join(banks[b] for b in ORDER))
print("code %d B at 0x8000..0x%04X; nex %d B" % (len(code), 0x8000 + len(code) - 1, out.stat().st_size))
for k in ("ticks", "frames", "res_t1", "res_t2", "res_t3", "res_t4", "bench_done", "code_end", "draw_cols", "draw_rows_hi", "wr0", "wr96", "cols_full", "rows_hi"):
    print("  %-12s %04X" % (k, S[k]))
