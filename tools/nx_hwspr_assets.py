#!/usr/bin/env python3
"""nx_hwspr_assets.py - lane N6 (8 Nov 2026): the Next hardware-sprite pattern packer of edition B, the Python twin of
hwspr_init's pattern loop (src/next/hwspr_next.asm) used by the oracle tools/nx_test_hwspr.py (C3: byte compare of the
pattern RAM against this packer, 0 diff).

Weapon: the pistol art of build/next/assets_b/sprites_b.bin (tools/nx_sprites_b.py layout: 8K bank 27 at image offset
8192 = idle, +1024 = fire; 32 columns x 32 bytes column-major, rows 24..31 zero pad, 0 = transparent) -> 8 patterns of
16x16 8-bit pixels (row-major, 256 B): pattern e = quadrant (e & 1: right half, e & 2: lower half) of frame (e & 4: fire).
    pattern e, row y, pixel x = art[base(e) + x*32 + y0(e) + y],  base(e) = 8192 + (e & 4)*256 + (e & 1)*512,  y0 = (e & 2)*8
Band: the HUD band is painted at run time (hud_next.asm into HW_PBUF, a 128-byte-stride copy of LoRes rows 88..95) and
re-packed by hw_band_upload: pattern 8+i, row r (0..7 and again 8..15), pixel x = pbuf[r*128 + 16*i + x].

CLI: .venv/bin/python tools/nx_hwspr_assets.py [--sprites build/next/assets_b/sprites_b.bin] [--out build/next/hwspr_weapon.bin]
writes the 8 x 256 B weapon pattern image (2048 B; informational: the program generates it at start from bank 27) and
prints per-pattern opaque pixel counts."""
import argparse, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
WEAPON_OFF = 8192           # pistol idle at 8K bank 27 offset 0 = image offset 8192 (sprites_next.asm: E000h)
FIRE_OFF = 1024

def weapon_pattern(art, e):
    base = WEAPON_OFF + (e & 4) * 256 + (e & 1) * 512
    y0 = (e & 2) * 8
    return bytes(art[base + x * 32 + y0 + y] for y in range(16) for x in range(16))

def weapon_patterns(art):
    return [weapon_pattern(art, e) for e in range(8)]

def band_pattern(pbuf, i):
    """pattern 8+i from a 1024-byte HW_PBUF image (rows 88..95, 128-byte stride): rows 0..7, then the same 8 rows again"""
    half = bytes(pbuf[r * 128 + 16 * i + x] for r in range(8) for x in range(16))
    return half + half

def sprite_xy(col, row):
    """LoRes pixel (col, row) -> hardware sprite coordinates (x, y) in the 320x256 sprite space (32-px border origin)"""
    return 32 + 2 * col, 32 + 2 * row

# the 12 sprites as hwspr_init programs them: (x, y, pattern, attr4) ; attr3 = 0C0h | pattern when visible
WEAPON_SPRITES = [(sprite_xy(48 + 16 * (e & 1), 64 + 16 * ((e >> 1) & 1)), e) for e in range(4)]
BAND_SPRITES = [(sprite_xy(16 * i, 88), 8 + i) for i in range(8)]
ATTR4 = 0x0A                # 8-bit anchor, X scale 2x (bits 4:3 = 01), Y scale 2x (bits 2:1 = 01)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sprites", default="build/next/assets_b/sprites_b.bin")
    ap.add_argument("--out", default="build/next/hwspr_weapon.bin")
    a = ap.parse_args()
    art = (ROOT / a.sprites).read_bytes()
    pats = weapon_patterns(art)
    (ROOT / a.out).write_bytes(b"".join(pats))
    for e, p in enumerate(pats):
        print("pattern %d (%s %s%s): %d opaque of 256" % (e, "fire" if e & 4 else "idle", "right" if e & 1 else "left", " lower" if e & 2 else " upper", sum(1 for b in p if b)))
    print("sprites:", [(xy, "pat %d" % p) for xy, p in WEAPON_SPRITES + BAND_SPRITES], "attr4 %02Xh" % ATTR4)
    print("wrote %s (%d bytes)" % (a.out, 256 * 8))
