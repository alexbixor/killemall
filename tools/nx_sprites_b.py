#!/usr/bin/env python3
"""nx_sprites_b.py - lane N2: convert the 1-bit sprite art of assets/sprites_m4 (16x8..16x24 enemies/items, 32x24 weapons) into
the edition B software-sprite bank: build/next/assets_b/sprites_b.bin = ONE 16K bank (bank 13 = 8K banks 26 + 27) of 8bpp
column data. Format (src/next/sprites_next.asm reads it):
  - a 16-wide sprite = 16 columns x 32 bytes (rows 0..23 used, 24..31 zero) = 512 bytes, column-major: byte[col*32 + row];
    0 = transparent, otherwise the palette index to write. Art shorter than 24 rows is bottom-aligned (feet on the floor).
    '#' (lit) -> the type's colour INK[id] (one fixed palette index per sprite id, below); 'o' (opaque black) -> DARK (225 =
    material 14 "dark", level 1); '.' -> 0.
  - 8K bank 26 (first 8192 bytes): sprite ids 0..13 at id*512 (imp 0-3, zombie 4-7, health 8, ammo 9, red key 10, blue key 11,
    barrel 12, lamp 13); 7168..8191 unused.
  - 8K bank 27 (bytes 8192..16383): pistol idle (id 14) at +0 and pistol fire (id 15) at +1024 as 32 columns x 32 bytes
    (1024 bytes each, rows 0..23); ids 18..29 (shotgunner, floater, brute) at +2048 + (id-18)*512. Ids 16/17 (shotgun),
    30..34 (boss) and 35/36 (chaingun) are NOT in the bank (no level of this lane places type 6; filed in N2_QUESTIONS.md).
Also adds "sprites_b" to <assets>/manifest.json (backed up to build/night/pre_N2/ first) and prints a size report.
Deterministic. Usage: .venv/bin/python tools/nx_sprites_b.py [--src assets/sprites_m4] [--out build/next/assets_b/sprites_b.bin]"""
import argparse, hashlib, json, pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent

DARK = 14 * 16 + 1          # 'o' pixels: material "dark" level 1 (near black, distinct from 0 = transparent)
# palette index per sprite id: material*16 + level (build/next/assets_b/manifest.json materials); written in N2_result.out
INK = {}
for i in range(0, 4):   INK[i] = 10 * 16 + 14    # imp: blood 174 (the 48K's magenta has no material; red is the nearest)
for i in range(4, 8):   INK[i] = 5 * 16 + 14     # zombie: moss 94 (green)
INK[8] = 10 * 16 + 15                            # health: blood 175
INK[9] = 8 * 16 + 15                             # ammo: gold 143
INK[10] = 10 * 16 + 15                           # red key: blood 175
INK[11] = 15 * 16 + 14                           # blue key: bluestone 254
INK[12] = 3 * 16 + 14                            # barrel: wood 62
INK[13] = 9 * 16 + 15                            # lamp: flame 159
INK[14] = INK[15] = 4 * 16 + 14                  # pistol: iron 78
for i in range(18, 22): INK[i] = 8 * 16 + 14     # shotgunner: gold 142 (yellow)
for i in range(22, 26): INK[i] = 11 * 16 + 14    # floater: water 190 (cyan)
for i in range(26, 30): INK[i] = 12 * 16 + 14    # brute: rust 206 (red-brown)
BANK26 = list(range(0, 14))
BANK27 = {14: 0, 15: 1024}
for i in range(18, 30): BANK27[i] = 2048 + (i - 18) * 512


def load(path):
    rows = [l.rstrip("\n") for l in pathlib.Path(path).read_text().splitlines() if not l.startswith(";") and l.strip() != ""]
    return rows


def convert(rows, ink, width):
    h = len(rows)
    assert 1 <= h <= 24, "sprite height %d" % h
    out = bytearray(width * 32)
    top = 24 - h
    for r, row in enumerate(rows):
        row = row.ljust(width)[:width]
        for c, ch in enumerate(row):
            v = ink if ch == "#" else (DARK if ch == "o" else 0)
            out[c * 32 + top + r] = v
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="assets/sprites_m4")
    ap.add_argument("--out", default="build/next/assets_b/sprites_b.bin")
    ap.add_argument("--no-manifest", action="store_true")
    a = ap.parse_args()
    src = ROOT / a.src
    files = {int(p.name[:2]): p for p in sorted(src.glob("[0-9][0-9]_*.txt"))}
    bank = bytearray(16384)
    report = []
    for i in BANK26:
        rows = load(files[i]); data = convert(rows, INK[i], 16)
        bank[i * 512:i * 512 + 512] = data
        report.append("id %2d %-22s %2d rows ink %3d -> bank 26 +%04X" % (i, files[i].stem, len(rows), INK[i], i * 512))
    for i, off in sorted(BANK27.items()):
        rows = load(files[i]); w = 32 if i in (14, 15) else 16
        data = convert(rows, INK[i], w)
        bank[8192 + off:8192 + off + len(data)] = data
        report.append("id %2d %-22s %2d rows ink %3d -> bank 27 +%04X (%d cols)" % (i, files[i].stem, len(rows), INK[i], off, w))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(bank))
    md5 = hashlib.md5(bank).hexdigest()
    print("\n".join(report))
    print("wrote %s: %d bytes md5 %s; lit pixels %d" % (out.relative_to(ROOT), len(bank), md5, sum(1 for b in bank if b)))
    if not a.no_manifest:
        man = out.parent / "manifest.json"
        txt = man.read_text()
        obj = json.loads(txt)
        if json.dumps(obj, indent=1) + "\n" != txt and json.dumps(obj, indent=1) != txt:
            print("WARNING: manifest.json is not json.dumps(indent=1) formatted; leaving it untouched")
            return
        bak = ROOT / "build/night/pre_N2" / man.relative_to(ROOT)
        if not bak.exists():
            bak.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(man, bak)
        obj["sprites_b"] = {"file": "sprites_b.bin", "bank16k": 13, "format": "16 cols x 32 B column-major 8bpp, 0 = transparent; "
                            "8K bank 26: ids 0..13 at id*512; 8K bank 27: pistol idle +0, pistol fire +1024 (32 cols), ids 18..29 at 2048+(id-18)*512",
                            "ink": {str(k): v for k, v in sorted(INK.items())}, "dark": DARK, "md5": md5, "generator": "tools/nx_sprites_b.py (lane N2)"}
        man.write_text(json.dumps(obj, indent=1) + ("\n" if txt.endswith("\n") else ""))
        print("manifest entry sprites_b written to %s" % man.relative_to(ROOT))


if __name__ == "__main__":
    main()
