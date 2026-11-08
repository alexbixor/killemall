#!/usr/bin/env python3
"""gen_hires.py - lane S (6 Nov 2026, 128K HIRES spike): 32x48 zombie art + scale tables for the bank-3 hi-res blitter
(src/128k/bank3.asm). Writes src/128k/gen/hires_art.asm. Frame 0 (walk A) = assets/sprites_hires/04_zombie_walk_a.txt
(hand-drawn 32x48); frames 1..3 (walk B, attack, dead) = assets/sprites_hires/05..07 (hand-drawn 32x48, lane A2 6 Nov 2026)
when HIRES_ALL is True (default), or the 16x24 originals in assets/sprites/ upscaled 2x when HIRES_ALL is False (the lane S
spike placeholders). Column format (2-px columns of the blitter): per frame 32
pointer words, then the run lists; run byte = (v_end << 2) | code, code 0 transparent / 1 black / 3 white, v_end = source row
1..48 where the run ends, 0 ends the list. 1-px black halo round the ink as tools/gen48.py runs16 does for the 16x24 art.
Tables: NC2[hd] (hd 0..128) = 2-px columns = round(hd/3) (same 2:3 aspect as 3 px x NCTAB), USTEP2[n] (n 0..48) = floor(8192/n)
8.8 u step (u = uacc >> 8 never reaches 32), VSTEP2[hd/2] (hd 0..128 even) = round(hd*256/48) 8.8 row step.
lane M2 (7 Nov 2026, BANK3 on the default 128K tape): also writes src/128k/gen/hires_art2.asm (org 0E000h in bank3.asm) with the
frames of enemy types 3..6 from assets/sprites_m4 (shotgunner 18,19,20,21; floater 22,23,24,25; brute 26,27,28,29; boss 30,31,32,34 -
33 "fall" is not used), pixel-doubled 16xN -> 32x48 bottom-aligned (grid_up2), plus HRFRM2 (5 rows x 4 frame pointers: type 2 =
the zombie frames of hires_art.asm, types 3..6) and art2_end. Identical column run lists within a frame are emitted once (generic
dedupe: pixel doubling makes columns 2u and 2u+1 identical, so a doubled frame needs 16 lists, not 32); the 32 pointer words of a
frame still address every column, so the blitter and the Python model (model_frames / model_type_frames) see 32 lists per frame."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "src/128k/gen/hires_art.asm"
OUT2 = ROOT / "src/128k/gen/hires_art2.asm"
W, H = 32, 48
HIRES_ALL = True   # lane A2: frames 1..3 from assets/sprites_hires/ (False = lane S pixel-doubled 16x24 placeholders)
# lane M2: enemy types 3..6 -> the four 16xN frames (walk A, walk B, attack, dead) in assets/sprites_m4
TYPE_SRC = {3: ("18_shotgunner_walk_a", "19_shotgunner_walk_b", "20_shotgunner_attack", "21_shotgunner_dead"),
            4: ("22_floater_a", "23_floater_b", "24_floater_attack", "25_floater_dead"),
            5: ("26_brute_walk_a", "27_brute_walk_b", "28_brute_attack", "29_brute_dead"),
            6: ("30_boss_walk_a", "31_boss_walk_b", "32_boss_attack", "34_boss_dead")}

def frame_grids():
    """The 4 zombie frames as 32x48 grids (walk A, walk B, attack, dead); the single source for main() and model_frames()."""
    names = ("04_zombie_walk_a", "05_zombie_walk_b", "06_zombie_attack", "07_zombie_dead")
    grids = [grid_hires(ROOT / "assets/sprites_hires" / (names[0] + ".txt"))]
    for n in names[1:]:
        grids.append(grid_hires(ROOT / "assets/sprites_hires" / (n + ".txt")) if HIRES_ALL else grid_up2(ROOT / "assets/sprites" / (n + ".txt")))
    return grids

HIRES_TYPES = True   # lane A3 (7 Nov 2026): types 3..6 from hand-drawn assets/sprites_hires/<name>.txt when the file exists
                     # (False, or a missing file = lane M2 pixel-doubled grid_up2 of the assets/sprites_m4 original)

def type_grids(t):
    """lane M2: the 4 frames of enemy type t (3..6) as 32x48 grids, pixel-doubled from assets/sprites_m4.
    lane A3: when HIRES_TYPES is True and assets/sprites_hires/<name>.txt exists, that hand-drawn 32x48 frame is used instead
    (per frame, so a half-finished set still builds)."""
    out = []
    for n in TYPE_SRC[t]:
        hp = ROOT / "assets/sprites_hires" / (n + ".txt")
        out.append(grid_hires(hp) if HIRES_TYPES and hp.exists() else grid_up2(ROOT / "assets/sprites_m4" / (n + ".txt")))
    return out

def type_frames(t):
    """lane A3: alias of type_grids(t) (the name used in the A3 brief)."""
    return type_grids(t)

def load_txt(path):
    rows = [l.rstrip("\n") for l in pathlib.Path(path).read_text().splitlines() if l and not l.startswith(";")]
    return rows

def grid_hires(path):
    rows = load_txt(path)
    assert len(rows) == H and all(len(r) == W for r in rows), (path, len(rows), [len(r) for r in rows][:3])
    return rows

def grid_up2(path):
    """16xh art (bottom-aligned in the 24 box) -> 32x48 by 2x pixel doubling, bottom-aligned."""
    rows = load_txt(path)
    assert all(len(r) == 16 for r in rows) and len(rows) <= 24, path
    box = ["." * W for _ in range(H - 2 * len(rows))]
    for r in rows:
        d = "".join(ch * 2 for ch in r)
        box += [d, d]
    return box

def runs(grid):
    """grid of '#' ink / 'o' opaque black / '.' transparent -> 32 run lists (bytes) with the 1-px halo."""
    ink = [[ch == "#" for ch in row] for row in grid]
    opaque = [[ch != "." for ch in row] for row in grid]
    def ink_at(u, v): return 0 <= u < W and 0 <= v < H and ink[v][u]
    halo = [[any(ink_at(u + du, v + dv) for du in (-1, 0, 1) for dv in (-1, 0, 1) if du or dv) for u in range(W)] for v in range(H)]
    cols = []
    for u in range(W):
        codes = [3 if ink[v][u] else (1 if (opaque[v][u] or halo[v][u]) else 0) for v in range(H)]
        out, v = [], 0
        while v < H:
            e = v
            while e < H and codes[e] == codes[v]: e += 1
            out.append((e << 2) | codes[v]); v = e
        cols.append(out + [0])
    return cols

def db(vals): return "        defb " + ",".join(str(v) for v in vals)
def dw(vals): return "        defw " + ",".join(str(v) for v in vals)

def emit_frame(s, label, cols):
    """lane M2: one frame = 32 pointer words + its DISTINCT run lists (identical column lists share one copy). Returns the bytes."""
    first = {}
    for u in range(W):
        first.setdefault(tuple(cols[u]), u)
    s += [label + ":", dw(["%s_u%d" % (label, first[tuple(cols[u])]) for u in range(W)])]
    total = 64
    for u in range(W):
        if first[tuple(cols[u])] == u:
            s += ["%s_u%d:" % (label, u), db(cols[u])]
            total += len(cols[u])
    return total

def main():
    frames = frame_grids()
    s = ["; generated by tools/gen_hires.py (lane S) - do not edit. 32x48 zombie frames as 2-px-column run lists + scale tables."]
    nc2 = [max(1, round(hd / 3)) if hd else 0 for hd in range(129)]
    ustep2 = [0] + [min(65535, 8192 // n) for n in range(1, 49)]
    vstep2 = [round(hd * 256 / 48) for hd in range(0, 130, 2)]
    s += ["NC2:", db(nc2), "USTEP2:", dw(ustep2), "VSTEP2:", dw(vstep2)]
    s += ["HRFRM:", dw(["hrf_%d" % i for i in range(4)])]
    total = 0
    for i, g in enumerate(frames):
        total += emit_frame(s, "hrf_%d" % i, runs(g))
    s += ["hires_art_end:"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(s) + "\n")
    # lane M2: types 3..6 at org 0E000h (bank3.asm includes this file there); HRFRM2 row 0 = the zombie frames above
    s2 = ["; generated by tools/gen_hires.py (lane M2) - do not edit. 32x48 frames of enemy types 3..6 (pixel-doubled assets/sprites_m4)",
          "; as 2-px-column run lists with shared identical columns, + HRFRM2[(type-2)*4 + frame] (types 2..6 x walk A / walk B / attack / dead).",
          "HRFRM2:", dw(["hrf_%d" % i for i in range(4)])]
    for t in (3, 4, 5, 6):
        s2.append(dw(["hrf_%d_%d" % (t, i) for i in range(4)]))
    total2 = 40
    per_type = {}
    for t in (3, 4, 5, 6):
        n = 0
        for i, g in enumerate(type_grids(t)):
            n += emit_frame(s2, "hrf_%d_%d" % (t, i), runs(g))
        per_type[t] = n; total2 += n
    s2 += ["art2_end:"]
    OUT2.write_text("\n".join(s2) + "\n")
    # column tables (bank3.asm includes them at fixed orgs): BUF column base per 2-px column k, 2-px slot bits, ray column
    PXRAY = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 7, 7, 7]
    t = ["; generated by tools/gen_hires.py (lane S) - do not edit. 96 2-px columns: BUF base lo/hi, slot bits, ray column.",
         "        org 0F300h", "HRBLO:", "        defb " + ",".join("(BUF+%d) and 255" % (96 * (k >> 2)) for k in range(96)),
         "        org 0F360h", "HRBHI:", "        defb " + ",".join("(BUF+%d)/256" % (96 * (k >> 2)) for k in range(96)),
         "        org 0F400h", "HRMSK:", db([(0xC0, 0x30, 0x0C, 0x03)[k & 3] for k in range(96)]),
         "        org 0F460h", "HRRAY:", db([8 * ((2 * k) // 24) + PXRAY[(2 * k) % 24] for k in range(96)])]
    (OUT.parent / "hires_tabs.asm").write_text("\n".join(t) + "\n")
    print("wrote %s: 4 zombie frames, %d B of run lists + pointers (identical columns shared), tables %d B" % (OUT, total, 129 + 98 + 130))
    src = {t: sum(1 for n in TYPE_SRC[t] if HIRES_TYPES and (ROOT / "assets/sprites_hires" / (n + ".txt")).exists()) for t in (3, 4, 5, 6)}
    print("wrote %s: types 3..6 = 16 frames, %d B (HRFRM2 40 B + per type %s); hand-drawn hi-res frames per type %s (HIRES_TYPES=%s), art2_end = bank3_org + %d (gate F000h)"
          % (OUT2, total2, per_type, src, HIRES_TYPES, total2))

def model_frames():
    """For tools/test_hires.py: the same 4 zombie frames as lists of 32 run lists."""
    return [runs(g) for g in frame_grids()]

def model_type_frames():
    """lane M2, for the oracles: {type: [4 frames of 32 run lists]} for types 2..6 (2 = the zombie frames of model_frames())."""
    d = {2: model_frames()}
    for t in (3, 4, 5, 6):
        d[t] = [runs(g) for g in type_grids(t)]
    return d

if __name__ == "__main__":
    main()
