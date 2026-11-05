#!/usr/bin/env python3
"""nx_level.py - build build/next/assets/level0.bin (+ level0.json) from the ASCII map in
docs/next_engine_spec_v0.1.md section 7 (lane R).  The spec is parsed, not copied, so the map and the
legend have exactly one home.

Cell format (spec section 7): 32 x 16 cells, 4 bytes per cell, row-major (offset = (my*32 + mx)*4):
  byte0 floor H32 (int8), byte1 ceil H32 (int8),
  byte2 = (solid << 7) | (ltex << 4) | wtex, byte3 = ftex | (ctex << 4).
  Solid cells: byte0 = byte1 = 0, byte3 = 0 (ltex of a solid cell is never read -> 0).

Usage:  .venv/bin/python tools/nx_level.py            (writes level0.bin, level0.json, prints a summary)
Importable: parse_spec(path) -> (rows, legend, wall_names, floor_names) ; encode(rows, legend) -> bytes
"""
import json, pathlib, re, struct, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs/next_engine_spec_v0.1.md"
OUT_BIN = ROOT / "build/next/assets/level0.bin"
OUT_JSON = ROOT / "build/next/assets/level0.json"
W, H = 32, 16

# legend entry: dict(floor, ceil, ftex, ctex, wtex, ltex, solid, name)
RE_OPEN = re.compile(r"'(.)' ([^(';]+?) \((-?\d+), (-?\d+), (\d+), (\d+), (\d+), (\d+)\)")
RE_SOLID = re.compile(r"'(.)' (\w+) (\d+)")


def section(text, number):
    """Text of '## <number>.' up to the next '## ' heading."""
    m = re.search(r"^## %d\..*?$" % number, text, re.M)
    if not m:
        raise ValueError("section %d not found in %s" % (number, SPEC))
    rest = text[m.end():]
    n = re.search(r"^## ", rest, re.M)
    return rest[: n.start()] if n else rest


def parse_names(sec, key):
    """'WALLS 0 stone, 1 brick, 2 moss (...), ...' -> {id: short name}."""
    m = re.search(key + r" (.*?)(?:\.\s*$|\.\s*\n\s*FLOORS|\.\n)", sec, re.S)
    if not m:
        return {}
    body = m.group(1)
    names = {}
    for item in re.split(r",\s*(?=\d+\s)", body):
        item = item.strip().rstrip(".")
        mm = re.match(r"(\d+)\s+(.*)", item, re.S)
        if not mm:
            continue
        name = re.sub(r"\s*\(.*", "", mm.group(2), flags=re.S).strip()
        names[int(mm.group(1))] = name
    return names


def parse_spec(path=SPEC):
    text = pathlib.Path(path).read_text()
    sec = section(text, 7)
    # the map: first fenced block in section 7
    fm = re.search(r"```\n(.*?)```", sec, re.S)
    if not fm:
        raise ValueError("no fenced map block in section 7")
    rows = [r for r in fm.group(1).split("\n") if r != ""]
    assert len(rows) == H, "map must have %d rows, got %d" % (H, len(rows))
    for i, r in enumerate(rows):
        assert len(r) == W, "map row %d must have %d columns, got %d: %r" % (i, W, len(r), r)
    # the legend
    lm = re.search(r"Legend \(floor H32, ceil H32, ftex, ctex, wtex, ltex\):(.*?)```", sec, re.S)
    if not lm:
        raise ValueError("legend not found in section 7")
    ltext = lm.group(1)
    open_part, solid_part = ltext.split("solid:")
    legend = {}
    for ch, name, fl, ce, ft, ct, wt, lt in RE_OPEN.findall(open_part):
        legend[ch] = dict(name=name.strip(), floor=int(fl), ceil=int(ce), ftex=int(ft), ctex=int(ct), wtex=int(wt), ltex=int(lt), solid=0)
    for ch, name, wt in RE_SOLID.findall(solid_part):
        legend[ch] = dict(name=name, floor=0, ceil=0, ftex=0, ctex=0, wtex=int(wt), ltex=0, solid=1)
    used = sorted(set("".join(rows)))
    missing = [ch for ch in used if ch not in legend]
    assert not missing, "map characters without legend entry: %r" % missing
    for ch, e in legend.items():
        assert -128 <= e["floor"] <= 127 and -128 <= e["ceil"] <= 127, ch
        assert 0 <= e["wtex"] <= 15 and 0 <= e["ltex"] <= 7 and 0 <= e["ftex"] <= 15 and 0 <= e["ctex"] <= 15, ch
        if not e["solid"]:
            assert e["ceil"] > e["floor"], "open cell %r has ceil <= floor" % ch
    wall_names = parse_names(sec, "WALLS")
    floor_names = parse_names(sec, "FLOORS")
    return rows, legend, wall_names, floor_names


def encode_cell(e):
    if e["solid"]:
        return bytes([0, 0, 0x80 | e["wtex"], 0])
    return struct.pack("<bb", e["floor"], e["ceil"]) + bytes([(e["ltex"] << 4) | e["wtex"], e["ftex"] | (e["ctex"] << 4)])


def encode(rows, legend):
    out = bytearray()
    for my in range(H):
        for mx in range(W):
            out += encode_cell(legend[rows[my][mx]])
    assert len(out) == W * H * 4 == 2048
    return bytes(out)


def main():
    rows, legend, wall_names, floor_names = parse_spec()
    blob = encode(rows, legend)
    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(blob)
    counts = {ch: "".join(rows).count(ch) for ch in sorted(legend) if ch in "".join(rows)}
    cells = []
    for my in range(H):
        for mx in range(W):
            e = legend[rows[my][mx]]
            cells.append([e["floor"], e["ceil"], e["solid"], e["wtex"], e["ltex"], e["ftex"], e["ctex"]])
    meta = {
        "source": str(SPEC.relative_to(ROOT)), "width": W, "height": H, "bytes_per_cell": 4, "size": len(blob),
        "cell_format": "byte0 floor H32 int8, byte1 ceil H32 int8, byte2 = solid<<7 | ltex<<4 | wtex, byte3 = ftex | ctex<<4; offset = (my*32+mx)*4",
        "rows": rows, "legend": legend, "char_counts": counts,
        "wall_textures": wall_names, "floor_textures": floor_names,
        "cells_fields": ["floor", "ceil", "solid", "wtex", "ltex", "ftex", "ctex"], "cells": cells,
    }
    OUT_JSON.write_text(json.dumps(meta, indent=1))
    solid = sum(1 for c in cells if c[2])
    print("wrote %s (%d bytes) and %s" % (OUT_BIN, len(blob), OUT_JSON))
    print("map %dx%d, %d solid cells, %d open cells; legend chars: %s" % (W, H, solid, W * H - solid, " ".join(sorted(legend))))
    print("char counts:", counts)
    print("wall names:", wall_names)
    print("floor names:", floor_names)
    # a few spot checks against the spec text
    assert rows[6][4] == "." and rows[6][11] == "a" and rows[6][12] == "H" and rows[7][19] == "w" and rows[2][15] == "U" and rows[11][3] == "L"
    assert blob[(6 * 32 + 4) * 4:(6 * 32 + 4) * 4 + 4] == bytes([0, 32, (6 << 4) | 5, 0 | (1 << 4)])
    assert blob[(7 * 32 + 19) * 4:(7 * 32 + 19) * 4 + 4] == bytes([256 - 24, 64, (6 << 4) | 0, 5 | (2 << 4)])
    assert blob[0:4] == bytes([0, 0, 0x81, 0])            # 'B' brick
    assert blob[(15 * 32 + 31) * 4:(15 * 32 + 31) * 4 + 4] == bytes([0, 0, 0x80, 0])   # '#' stone
    print("spot checks OK")


if __name__ == "__main__":
    main()
