#!/usr/bin/env python3
"""nx_build.py - build a Spectrum Next engine program (.nex): assemble a src/next/*.asm with pasmo, check the code stays below
the palette block (PALETTE = 9E00h in main_vars.inc), poke <assets>/palette.bin at 9E00h and the level at LEVEL (0B800h) into
the 16K code image, and pack the .nex:
  16K banks: 5 = zero (screen + variables), 2 = code image, 4 = build/next/tables_bank4.bin (tables + IM1 ISR),
  8..11 = the four 16K quarters of <assets>/walls.bin (64 KB), 12 = <assets>/floors.bin padded to 16K.
  Entry PC 8000h, SP 5F00h (spec v0.1 section 8).

Usage: .venv/bin/python tools/nx_build.py [--src src/next/main.asm] [--out build/next/killemall_next.nex] [--bin-name main]
                                         [--assets build/next/assets] [--level <mapc .bin>] [--level-index n]
                                         [--level-txt assets/levels/NN_name.txt]
Defaults (option A, unchanged since lane M): src/next/main.asm, build/next/assets, the 2048-byte build/next/assets/level0.bin
(v0.1 4-byte cells) at LEVEL, no header pokes -> byte-identical build/next/killemall_next.nex.
Edition B options (lane N1A, docs/next_engine_spec_v0.2_flat.md section 1 and 6):
  --assets DIR        read palette.bin / walls.bin / floors.bin / manifest.json from DIR (e.g. build/next/assets_b)
  --level FILE        a tools/mapc.py output (edition "next"): u8 level count, then per level 8-byte header 'K',1,32,32,sx,sy,
                      start_angle,n_things + 1024 cells + n_things x 3 bytes. ONE level (header + cells + things, --level-index n,
                      default 0) is copied to LEVEL, zero-padded to 2048 bytes (a level must be <= 2048 bytes: 1032 + 3*338).
                      A FILE without the count byte (starts with 'K') is accepted too.
  --level-txt FILE    the level's .txt source: its `#ceil=`, `#ftex=`, `#ctex=` header lines (defaults 32, "flag", "plaster";
                      texture names resolved through <assets>/manifest.json "floors") give the bytes poked at the addresses of
                      the symbols CEIL_B, FTEX_B, CTEX_B of the assembled program (.sym). Missing symbols -> warning, no poke.
                      Without --level-txt the defaults (32, flag, plaster) are poked when the symbols exist.
  --sprites FILE      lane N2 (5 Nov 2026): a 16K image packed as 16K bank 13 (= 8K banks 26/27, software sprite data for
                      src/next/sprites_next.asm, built by tools/nx_sprites_b.py). Default absent -> no bank 13 -> the .nex is
                      byte-identical to the build without this option (proven in build/night/N2_build_identity.out).
Prints the code size, the symbols that matter, what was poked and the .nex path; exit code 0 only when everything was built."""
import argparse, json, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex

CODE_BASE = 0x8000
PALETTE_ADDR = 0x9E00
LEVEL_ADDR = 0xB800
LEVEL_SIZE = 2048
ASSETS = ROOT / "build/next/assets"
TABLES = ROOT / "build/next/tables_bank4.bin"
HEADER_DEFAULTS = {"ceil": 32, "ftex": "flag", "ctex": "plaster"}      # spec v0.2 section 1
HEADER_SYMS = {"ceil": "CEIL_B", "ftex": "FTEX_B", "ctex": "CTEX_B"}  # lane N1 defines them (walk_b_vars.inc / main_b_vars.inc)

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

def mapc_levels(data):
    """split a tools/mapc.py 'next' file into its levels: list of (header 8 bytes, cells 1024, things bytes); accepts a bare level"""
    if not data or data[0:1] == b"K":
        count, pos = None, 0
    else:
        count, pos = data[0], 1
    levels = []
    while pos < len(data):
        hdr = data[pos:pos + 8]
        if len(hdr) < 8 or hdr[0:2] != b"K\x01":
            sys.exit("ERROR: bad mapc level header at offset %d: %r (want 'K', 1, w, h, sx, sy, angle, n_things)" % (pos, hdr))
        w, h, n_things = hdr[2], hdr[3], hdr[7]
        size = 8 + w * h + 3 * n_things
        if pos + size > len(data):
            sys.exit("ERROR: mapc level at offset %d truncated (need %d bytes, file has %d)" % (pos, size, len(data) - pos))
        levels.append(data[pos:pos + size])
        pos += size
    if count is not None and count != len(levels):
        sys.exit("ERROR: mapc file says %d levels, found %d" % (count, len(levels)))
    return levels

def level_image(level_path, index):
    """ONE level of a mapc file as the 2048-byte LEVEL image (header + cells + things, zero padded)"""
    levels = mapc_levels(pathlib.Path(level_path).read_bytes())
    if not 0 <= index < len(levels):
        sys.exit("ERROR: --level-index %d out of range: %s holds %d level(s)" % (index, level_path, len(levels)))
    lv = levels[index]
    if len(lv) > LEVEL_SIZE:
        sys.exit("ERROR: level %d is %d bytes, LEVEL holds %d" % (index, len(lv), LEVEL_SIZE))
    hdr = lv[:8]
    print("level %d of %d from %s: %d bytes (w %d h %d start (%d, %d) angle %d things %d) -> LEVEL %04Xh, zero-padded to %d" % (
        index, len(levels), level_path, len(lv), hdr[2], hdr[3], hdr[4], hdr[5], hdr[6], hdr[7], LEVEL_ADDR, LEVEL_SIZE))
    return lv.ljust(LEVEL_SIZE, b"\0")

def level_header_options(txt_path):
    """the Next-only `#ceil=`, `#ftex=`, `#ctex=` header lines of a level .txt (spec v0.2 section 1), defaults where absent"""
    opts = dict(HEADER_DEFAULTS)
    if txt_path is None:
        return opts
    for line in pathlib.Path(txt_path).read_text().splitlines():
        if line.startswith("#") and "=" in line:
            key, _, val = line[1:].partition("=")
            key, val = key.strip().lower(), val.strip()
            if key in opts and key.isalpha():
                opts[key] = int(val, 0) if key == "ceil" else val
    if opts["ceil"] not in (32, 64):
        sys.exit("ERROR: #ceil=%r in %s: must be 32 or 64" % (opts["ceil"], txt_path))
    return opts

def header_bytes(opts, assets):
    """(name -> byte) for CEIL_B / FTEX_B / CTEX_B: ceil as is, texture names through <assets>/manifest.json 'floors'"""
    man_path = pathlib.Path(assets) / "manifest.json"
    floors = json.loads(man_path.read_text())["floors"] if man_path.exists() else {}
    out = {}
    for key in ("ftex", "ctex"):
        name = opts[key]
        if isinstance(name, str) and name.isdigit():
            out[key] = int(name)
        elif name in floors:
            out[key] = int(floors[name])
        else:
            sys.exit("ERROR: #%s=%r is not a floor texture of %s (known: %s)" % (key, name, man_path, sorted(floors)))
        if not 0 <= out[key] <= 7:
            sys.exit("ERROR: #%s=%r -> id %d, floors.bin has ids 0..7" % (key, name, out[key]))
    out["ceil"] = opts["ceil"]
    return out

def poke_header(img, syms, hb, opts):
    """poke the three bytes at the symbols' addresses (inside the 16K code image); warn for every missing symbol"""
    for key in ("ceil", "ftex", "ctex"):
        sym = HEADER_SYMS[key]
        if sym not in syms:
            print("WARNING: symbol %s not in the .sym: %s = %s (%d) NOT poked" % (sym, key, opts[key], hb[key]))
            continue
        addr = syms[sym]
        if not CODE_BASE <= addr < CODE_BASE + 16384:
            sys.exit("ERROR: %s = %04Xh is outside the code image 8000h..BFFFh (variables in bank 5 cannot be poked at build time)" % (sym, addr))
        img[addr - CODE_BASE] = hb[key]
        print("poked %s (%04Xh) = %d (%s = %s)" % (sym, addr, hb[key], key, opts[key]))

def build(src="src/next/main.asm", out="build/next/killemall_next.nex", bin_name="main", assets=None, level=None, level_index=0, level_txt=None, sprites=None):
    src = ROOT / src
    out = ROOT / out
    assets = ASSETS if assets is None else (ROOT / assets)
    bin_path, sym_path = ROOT / ("build/next/%s.bin" % bin_name), ROOT / ("build/next/%s.sym" % bin_name)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    code = assemble(src, bin_path, sym_path)
    syms = read_syms(sym_path)
    code_end = CODE_BASE + len(code)
    print("assembled %s -> %s: %d bytes, 8000h..%04Xh (code_end sym %04Xh)" % (src.relative_to(ROOT), bin_path.relative_to(ROOT), len(code), code_end, syms.get("code_end", -1)))
    if code_end > PALETTE_ADDR:
        sys.exit("ERROR: code ends at %04Xh, above the palette block at %04Xh" % (code_end, PALETTE_ADDR))
    for name in ("start", "main_loop", "tick", "read_keys", "can_move", "setup_camera", "walk_frame", "walk_frame_b", "draw_piece", "plane_add", "void_fill", "fill_col", "code_end"):
        if name in syms: print("  %-13s %04Xh" % (name, syms[name]))
    pal = (assets / "palette.bin").read_bytes()
    if level is None:
        lv = (assets / "level0.bin").read_bytes()
        assert len(lv) == 2048, "level0.bin must be 2048 bytes (got %d)" % len(lv)
    else:
        lv = level_image(ROOT / level, level_index)
    walls = (assets / "walls.bin").read_bytes()
    floors = (assets / "floors.bin").read_bytes()
    assert len(pal) == 512, "palette.bin must be 512 bytes (got %d)" % len(pal)
    assert len(walls) == 65536, "walls.bin must be 65536 bytes (got %d)" % len(walls)
    assert len(floors) == 8192, "floors.bin must be 8192 bytes (got %d)" % len(floors)
    if not TABLES.exists(): sys.exit("ERROR: %s missing (run tools/nx_tables.py)" % TABLES)
    img = bytearray(code.ljust(16384, b"\0"))
    img[PALETTE_ADDR - CODE_BASE:PALETTE_ADDR - CODE_BASE + 512] = pal
    img[LEVEL_ADDR - CODE_BASE:LEVEL_ADDR - CODE_BASE + 2048] = lv
    if level is not None or level_txt is not None or any(s in syms for s in HEADER_SYMS.values()):
        opts = level_header_options(None if level_txt is None else ROOT / level_txt)
        poke_header(img, syms, header_bytes(opts, assets), opts)
    banks = {5: bytes(16384), 2: bytes(img), 4: TABLES.read_bytes(), 12: floors.ljust(16384, b"\0")}
    for q in range(4):
        banks[8 + q] = walls[q * 16384:(q + 1) * 16384]
    if sprites is not None:
        spr = (ROOT / sprites).read_bytes()
        assert len(spr) <= 16384, "--sprites image must be <= 16384 bytes (got %d)" % len(spr)
        banks[13] = spr.ljust(16384, b"\0")
        print("sprites %s: %d bytes -> 16K bank 13 (8K banks 26/27)" % (sprites, len(spr)))
    build_nex(out, banks, pc=0x8000, sp=0x5F00)
    print("wrote %s (%d bytes; banks %s; PC 8000h SP 5F00h; palette at %04Xh, level at %04Xh; assets %s)" % (
        out.relative_to(ROOT), out.stat().st_size, sorted(banks), PALETTE_ADDR, LEVEL_ADDR, assets.relative_to(ROOT) if assets.is_relative_to(ROOT) else assets))
    return out, syms

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="src/next/main.asm")
    ap.add_argument("--out", default="build/next/killemall_next.nex")
    ap.add_argument("--bin-name", default="main")
    ap.add_argument("--assets", default=None, help="asset directory (default build/next/assets)")
    ap.add_argument("--level", default=None, help="tools/mapc.py 'next' .bin; default: <assets>/level0.bin (option A layout)")
    ap.add_argument("--level-index", type=int, default=0, help="which level of a multi-level mapc file (default 0)")
    ap.add_argument("--level-txt", default=None, help="level .txt whose #ceil= #ftex= #ctex= header lines are poked at CEIL_B/FTEX_B/CTEX_B")
    ap.add_argument("--sprites", default=None, help="lane N2: 16K sprite image packed as 16K bank 13 (default: no bank 13, output unchanged)")
    a = ap.parse_args()
    build(a.src, a.out, a.bin_name, a.assets, a.level, a.level_index, a.level_txt, a.sprites)
