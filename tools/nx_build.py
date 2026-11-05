#!/usr/bin/env python3
"""nx_build.py - build the Spectrum Next engine program (lane M): assemble src/next/main.asm with pasmo, check the code
stays below the palette block (PALETTE = 9E00h in main_vars.inc), poke build/next/assets/palette.bin at 9E00h and
build/next/assets/level0.bin at LEVEL (0B800h) into the 16K code image, and pack build/next/killemall_next.nex:
  16K banks: 5 = zero (screen + variables), 2 = code image, 4 = build/next/tables_bank4.bin (tables + IM1 ISR),
  8..11 = the four 16K quarters of build/next/assets/walls.bin (64 KB), 12 = build/next/assets/floors.bin padded to 16K.
  Entry PC 8000h, SP 5F00h (spec section 8).
Usage: .venv/bin/python tools/nx_build.py [--src src/next/main.asm] [--out build/next/killemall_next.nex]
Prints the code size, the symbols that matter and the .nex path; exit code 0 only when everything was built."""
import argparse, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex

CODE_BASE = 0x8000
PALETTE_ADDR = 0x9E00
LEVEL_ADDR = 0xB800
ASSETS = ROOT / "build/next/assets"
TABLES = ROOT / "build/next/tables_bank4.bin"

def read_syms(path):
    syms = {}
    for line in pathlib.Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1].upper() == "EQU":
            try: syms[parts[0]] = int(parts[2].rstrip("Hh"), 16)
            except ValueError: pass
    return syms

def assemble(src, bin_path, sym_path):
    src = pathlib.Path(src).resolve()
    r = subprocess.run(["pasmo", "--bin", src.name, str(bin_path), str(sym_path)], cwd=src.parent, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed (%d):\n%s%s" % (r.returncode, r.stdout, r.stderr))
    return pathlib.Path(bin_path).read_bytes()

def build(src="src/next/main.asm", out="build/next/killemall_next.nex", bin_name="main"):
    src = ROOT / src
    out = ROOT / out
    bin_path, sym_path = ROOT / ("build/next/%s.bin" % bin_name), ROOT / ("build/next/%s.sym" % bin_name)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    code = assemble(src, bin_path, sym_path)
    syms = read_syms(sym_path)
    code_end = CODE_BASE + len(code)
    print("assembled %s -> %s: %d bytes, 8000h..%04Xh (code_end sym %04Xh)" % (src.relative_to(ROOT), bin_path.relative_to(ROOT), len(code), code_end, syms.get("code_end", -1)))
    if code_end > PALETTE_ADDR:
        sys.exit("ERROR: code ends at %04Xh, above the palette block at %04Xh" % (code_end, PALETTE_ADDR))
    for name in ("start", "main_loop", "tick", "read_keys", "can_move", "setup_camera", "walk_frame", "draw_piece", "plane_add", "void_fill", "fill_col", "code_end"):
        if name in syms: print("  %-13s %04Xh" % (name, syms[name]))
    pal = (ASSETS / "palette.bin").read_bytes()
    lv = (ASSETS / "level0.bin").read_bytes()
    walls = (ASSETS / "walls.bin").read_bytes()
    floors = (ASSETS / "floors.bin").read_bytes()
    assert len(pal) == 512, "palette.bin must be 512 bytes (got %d)" % len(pal)
    assert len(lv) == 2048, "level0.bin must be 2048 bytes (got %d)" % len(lv)
    assert len(walls) == 65536, "walls.bin must be 65536 bytes (got %d)" % len(walls)
    assert len(floors) == 8192, "floors.bin must be 8192 bytes (got %d)" % len(floors)
    if not TABLES.exists(): sys.exit("ERROR: %s missing (run tools/nx_tables.py)" % TABLES)
    img = bytearray(code.ljust(16384, b"\0"))
    img[PALETTE_ADDR - CODE_BASE:PALETTE_ADDR - CODE_BASE + 512] = pal
    img[LEVEL_ADDR - CODE_BASE:LEVEL_ADDR - CODE_BASE + 2048] = lv
    banks = {5: bytes(16384), 2: bytes(img), 4: TABLES.read_bytes(), 12: floors.ljust(16384, b"\0")}
    for q in range(4):
        banks[8 + q] = walls[q * 16384:(q + 1) * 16384]
    build_nex(out, banks, pc=0x8000, sp=0x5F00)
    print("wrote %s (%d bytes; banks %s; PC 8000h SP 5F00h; palette at %04Xh, level at %04Xh)" % (out.relative_to(ROOT), out.stat().st_size, sorted(banks), PALETTE_ADDR, LEVEL_ADDR))
    return out, syms

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="src/next/main.asm")
    ap.add_argument("--out", default="build/next/killemall_next.nex")
    ap.add_argument("--bin-name", default="main")
    a = ap.parse_args()
    build(a.src, a.out, a.bin_name)
