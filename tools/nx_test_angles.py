#!/usr/bin/env python3
"""nx_test_angles.py - lane N4 oracle A: the 1024-angle sweep for the vertical-black-bar bug (build/night/N4_BRIEF.md item 1).

Part A (--ref): for 8 positions (the N1 scenes start/door/corridor/oblique on level 01 + 4 extra on levels 01 and 08) and ALL
1024 angles, run the Python reference walker (tools/nx_ref_flat.py FlatRenderer.column, records only) and flag any column
 (1) whose record list ends with no wall piece and no VOID,
 (2) that has no wall piece (zero-height wall) while a neighbour column's piece is full height (96 rows),
 (3) whose zbuf is 0 / 65535 / 4095-VOID while a neighbour is not,
 (4) that is a VOID (palette 0, rows 0..96) with a non-VOID neighbour = a visible black bar.
Part B (--live): one headless ZEsarUX per position runs build/night/N4_test_angles.asm (= main_b.asm, flat tier, with a ZRCP-driven
scene loop): for every flagged angle and 64 evenly spaced angles the program renders the real frame, the tool reads the 12288
screen bytes + ZBUF and compares them with the reference frame (nx_ref_flat.render_flat tier flat) and counts black bars with
the independent per-pixel rule: a column with a palette-0 pixel that has a non-zero pixel above AND below it, or a whole
column of palette 0, is a bar.

    timeout 580 .venv/bin/python tools/nx_test_angles.py --ref  [--out build/night/N4_angles_ref.out]
    timeout 580 .venv/bin/python tools/nx_test_angles.py --live --pos start,door [--nex build/night/N4_test_angles.nex]
    .venv/bin/python tools/nx_test_angles.py --build        # assemble build/night/N4_test_angles.asm -> .bin/.sym/.nex

Everything is written under build/night/N4_* (the other lanes' files are not touched)."""
import argparse, hashlib, json, pathlib, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nx_build, nx_ref
import nx_ref_flat as ref
from nx_nex import build_nex
from nx_run import NexRun
from run48 import zrcp

NIGHT = ROOT / "build/night"
SRC = ROOT / "src/next"
ASM = NIGHT / "N4_test_angles.asm"
BIN, SYM, NEX = NIGHT / "N4_test_angles.bin", NIGHT / "N4_test_angles.sym", NIGHT / "N4_test_angles.nex"
ASSETS = ROOT / "build/next/assets_b"
LEVELS = NIGHT / "N3_levels.bin"
CODE_BASE = 0x8000
W, H = 128, 96

# positions: name -> (level index 0-based, px, py) ; the 4 N1 scenes + 4 of lane N4's choice
POSITIONS = {
    "start": (0, 0x0380, 0x0780),
    "door": (0, 0x0C80, 0x0380),
    "corridor": (0, 0x0180, 0x0D80),
    "oblique": (0, 0x0A80, 0x0D80),
    "l01_hall": (0, 0x1380, 0x0780),      # level 01 (19.5, 7.5): inside the B room, long views both ways
    "l01_south": (0, 0x0780, 0x1C80),     # level 01 (7.5, 28.5): south part of the map
    "l08_start": (7, 0x1180, 0x1C80),     # level 08 start (17.5, 28.5): the 28-cell east-west corridor of row 28
    "l08_hall": (7, 0x0F80, 0x0B80),      # level 08 (15.5, 11.5): the big central hall, long diagonals
}


def level_blob(index):
    lv = nx_build.level_image(LEVELS, index)
    return bytes(lv[:8 + 1024 + 3 * lv[7]]), bytes(lv)


def level_params(index):
    txt = sorted((ROOT / "assets/levels").glob("%02d_*.txt" % (index + 1)))[0]
    hb = nx_build.header_bytes(nx_build.level_header_options(txt), ASSETS)
    return hb["ceil"], hb["ftex"], hb["ctex"]


class RecRenderer(ref.FlatRenderer):
    """records + zbuf only (no pixel painting): fast enough for 1024 angles x 8 positions."""
    def PLANE_ADD(self, c, h, tex, a, b, kind, d):
        self.records.append({"op": "PLANE_ADD", "args": [c, h, tex, a, b]})
    def DRAW_PIECE(self, c, ra, count, tex, s, u, v_first, dv, kind, d):
        self.records.append({"op": "DRAW_PIECE", "args": [c, ra, count, tex, s, u, v_first, dv]})
    def VOID(self, c, a, b):
        self.records.append({"op": "VOID", "args": [c, a, b]})
    def run(self):
        for c in range(W):
            self.column(c)
        return self.records, self.zbuf


_tex_cache = {}
def textures():
    if not _tex_cache:
        _tex_cache["w"] = nx_ref.WallTex((ASSETS / "walls.bin").read_bytes())
        _tex_cache["f"] = nx_ref.FloorTex((ASSETS / "floors.bin").read_bytes())
    return _tex_cache["w"], _tex_cache["f"]


def analyse(records, zbuf):
    """-> dict of flagged columns per rule (see the module docstring)."""
    cols = {c: [] for c in range(W)}
    for r in records:
        cols[r["args"][0]].append(r)
    piece_rows = [0] * W
    is_void = [False] * W
    for c in range(W):
        for r in cols[c]:
            if r["op"] == "DRAW_PIECE":
                piece_rows[c] += r["args"][2]
            elif r["op"] == "VOID":
                is_void[c] = True
    f1 = [c for c in range(W) if not cols[c] or cols[c][-1]["op"] not in ("DRAW_PIECE", "VOID")]
    f2, f3, f4 = [], [], []
    for c in range(W):
        nb = [n for n in (c - 1, c + 1) if 0 <= n < W]
        if piece_rows[c] == 0 and not is_void[c] and any(piece_rows[n] == H for n in nb):
            f2.append(c)
        z = zbuf[c]
        if z in (0, 65535) and any(zbuf[n] not in (0, 65535) for n in nb):
            f3.append(c)
        if is_void[c] and any(not is_void[n] for n in nb):
            f4.append(c)
    return {"no_end_piece": f1, "zero_height_wall": f2, "zbuf_edge": f3, "void_bar_edge": f4,
            "void_cols": [c for c in range(W) if is_void[c]]}


def sweep_ref(names, log):
    """Part A: -> {name: {angle: analysis-with-flags}} (only angles with any flag), plus VOID column totals."""
    walls, floors = textures()
    out = {}
    for name in names:
        li, px, py = POSITIONS[name]
        blob, _ = level_blob(li)
        ceil, ftex, ctex = level_params(li)
        flagged, void_total, void_angles = {}, 0, 0
        t0 = time.time()
        for a in range(1024):
            rr = RecRenderer(blob, px, py, a, walls, floors, ceil, ftex, ctex, "flat")
            records, zbuf = rr.run()
            an = analyse(records, zbuf)
            nvoid = len(an["void_cols"])
            void_total += nvoid
            void_angles += 1 if nvoid else 0
            if any(an[k] for k in ("no_end_piece", "zero_height_wall", "zbuf_edge", "void_bar_edge")):
                flagged[a] = an
        log("%-10s level %02d px=%04X py=%04X CEIL=%d: %d of 1024 angles flagged; angles with VOID columns %d, VOID columns total %d; "
            "rule counts: no_end_piece %d, zero_height_wall %d, zbuf_edge %d, void_bar_edge %d (%.1fs)" % (
                name, li + 1, px, py, ceil, len(flagged), void_angles, void_total,
                sum(1 for v in flagged.values() if v["no_end_piece"]), sum(1 for v in flagged.values() if v["zero_height_wall"]),
                sum(1 for v in flagged.values() if v["zbuf_edge"]), sum(1 for v in flagged.values() if v["void_bar_edge"]), time.time() - t0))
        out[name] = {"flagged": flagged, "void_total": void_total, "void_angles": void_angles}
    return out


def bars_in_frame(frame):
    """independent per-pixel rule: per column, count palette-0 runs that have a non-zero pixel above AND below, or a whole black column.
    -> (bar_columns list, black_pixels)"""
    bars = []
    for c in range(W):
        col = frame[c::W]
        if all(v == 0 for v in col):
            bars.append(c)
            continue
        inside = False
        for y in range(1, H - 1):
            if col[y] == 0 and col[y - 1] != 0:
                inside = True
            if inside and col[y] == 0 and col[y + 1] != 0:
                bars.append(c)
                break
            if col[y] != 0:
                inside = False
    return bars, frame.count(0)


# ---------------------------------------------------------------- Part B: the live program
def assemble():
    r = subprocess.run(["pasmo", "--equ", "PLANES_FLAT=1", "--bin", str(ASM), str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
    return BIN.read_bytes(), nx_build.read_syms(SYM)


def make_nex(code, syms, lv_img, hb):
    img = bytearray(code.ljust(16384, b"\0"))
    img[nx_build.PALETTE_ADDR - CODE_BASE:nx_build.PALETTE_ADDR - CODE_BASE + 512] = (ASSETS / "palette.bin").read_bytes()
    img[nx_build.LEVEL_ADDR - CODE_BASE:nx_build.LEVEL_ADDR - CODE_BASE + 2048] = lv_img
    for key in ("ceil", "ftex", "ctex"):
        img[syms[nx_build.HEADER_SYMS[key]] - CODE_BASE] = hb[key]
    walls = (ASSETS / "walls.bin").read_bytes(); floors = (ASSETS / "floors.bin").read_bytes()
    banks = {5: bytes(16384), 2: bytes(img), 4: nx_build.TABLES.read_bytes(), 12: floors.ljust(16384, b"\0")}
    for q in range(4):
        banks[8 + q] = walls[q * 16384:(q + 1) * 16384]
    build_nex(NEX, banks, pc=0x8000, sp=0x5F00)


def rd_fast(r, addr, n):
    """read-memory in one ZRCP command (nx_run.rd uses 2 KB chunks with a 0.2 s wait each)."""
    out = zrcp(r.s, "read-memory %d %d" % (addr, n), 0.05)
    h = "".join(ch for ch in out.split("command>")[0] if ch in "0123456789ABCDEFabcdef")[:2 * n]
    return bytes.fromhex(h) if len(h) == 2 * n else r.rd(addr, n)


def wr(r, addr, data):
    """lane N2 pitfall: ZEsarUX write-memory parses bare values as DECIMAL; the H suffix makes them hex (never NexRun.wr)."""
    zrcp(r.s, "write-memory %d %s" % (addr, " ".join("%02XH" % b for b in data)), 0.05)


def live_position(name, angles, code, syms, log, full_frames=True):
    """one emulator: for each angle poke the scene, run one frame, read screen + zbuf, compare with the reference."""
    li, px, py = POSITIONS[name]
    blob, lv_img = level_blob(li)
    ceil, ftex, ctex = level_params(li)
    make_nex(code, syms, lv_img, {"ceil": ceil, "ftex": ftex, "ctex": ctex})
    walls, floors = textures()
    res = []
    t0 = time.time()
    with NexRun(NEX) as r:
        if not r.wait_byte(syms["NA_READY"], 1, timeout=60):
            log("%s: program never became ready (PC=%04X)" % (name, r.pc())); return res
        for a in angles:
            wr(r, syms["NA_SCENE"], struct.pack("<HHH", px, py, a))
            wr(r, syms["NA_DONE"], b"\0")
            wr(r, syms["NA_GO"], b"\1")
            if not r.wait_byte(syms["NA_DONE"], 1, timeout=20):
                log("%s a=%d: TIMEOUT (PC=%04X)" % (name, a, r.pc())); break
            scr = rd_fast(r, 0x4000, 6144) + rd_fast(r, 0x6000, 6144)
            zraw = rd_fast(r, 0x1A00, 256)
            zbuf = [struct.unpack_from("<H", zraw, 2 * i)[0] for i in range(W)]
            exp, records, ezbuf = ref.render_flat(blob, px, py, a, walls, floors, ceil, ftex, ctex, "flat")
            diffs = sum(1 for i in range(W * H) if scr[i] != exp[i]) if len(scr) == W * H else -1
            bars, black = bars_in_frame(scr) if len(scr) == W * H else ([], -1)
            rbars, rblack = bars_in_frame(exp)
            zmism = [c for c in range(W) if zbuf[c] != ezbuf[c]]
            res.append({"pos": name, "a": a, "diff_bytes": diffs, "live_bars": bars, "live_black": black, "ref_bars": rbars, "ref_black": rblack,
                        "zbuf_mismatch": zmism, "live_sha1": hashlib.sha1(scr).hexdigest()[:10], "ref_sha1": hashlib.sha1(exp).hexdigest()[:10]})
            if diffs or zmism or bars:
                log("  %s a=%4d: %d differing bytes, zbuf mismatches %d, LIVE bars %d %s (black px %d), ref bars %d" % (
                    name, a, diffs, len(zmism), len(bars), ("c=%d..%d" % (bars[0], bars[-1])) if bars else "", black, len(rbars)))
    log("%s: %d angles live in %.1fs: angles with differing bytes %d, with zbuf mismatches %d, with live bars %d (bar columns total %d), ref bars %d" % (
        name, len(res), time.time() - t0, sum(1 for x in res if x["diff_bytes"]), sum(1 for x in res if x["zbuf_mismatch"]),
        sum(1 for x in res if x["live_bars"]), sum(len(x["live_bars"]) for x in res), sum(1 for x in res if x["ref_bars"])))
    return res


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--pos", default=",".join(POSITIONS))
    ap.add_argument("--max-flagged", type=int, default=48, help="live: at most this many flagged angles per position (evenly thinned)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tag", default="", help="suffix for the output files, e.g. _before / _after")
    a = ap.parse_args(argv)
    names = [n for n in a.pos.split(",") if n]
    lines = []
    def log(s): print(s, flush=True); lines.append(s)
    log("nx_test_angles %s: positions %s" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), " ".join(names)))
    if a.build or a.live:
        code, syms = assemble()
        log("assembled %s -> %d bytes (NA_SCENE %04X NA_GO %04X NA_DONE %04X)" % (ASM.relative_to(ROOT), len(code), syms["NA_SCENE"], syms["NA_GO"], syms["NA_DONE"]))
    flagged_json = NIGHT / ("N4_angles_flagged%s.json" % a.tag)
    if a.ref:
        sw = sweep_ref(names, log)
        tot_flag = sum(len(v["flagged"]) for v in sw.values()); tot_void = sum(v["void_total"] for v in sw.values())
        log("REF SWEEP: %d positions x 1024 angles: %d flagged angles, %d VOID (black) columns in total" % (len(names), tot_flag, tot_void))
        flagged_json.write_text(json.dumps({n: {str(k): v for k, v in sw[n]["flagged"].items()} for n in sw}))
        (ROOT / (a.out or "build/night/N4_angles_ref%s.out" % a.tag)).write_text("\n".join(lines) + "\n")
    if a.live:
        fl = json.loads(flagged_json.read_text()) if flagged_json.exists() else {}
        allres = []
        for name in names:
            fa = sorted(int(k) for k in fl.get(name, {}))
            if len(fa) > a.max_flagged:
                fa = fa[::max(1, len(fa) // a.max_flagged)][:a.max_flagged]
            angles = sorted(set(fa) | set(range(0, 1024, 16)))
            log("%s: live angles %d (%d flagged by the reference sweep + 64 evenly spaced)" % (name, len(angles), len(fa)))
            allres += live_position(name, angles, code, syms, log)
            subprocess.run(["pkill", "-x", "zesarux"])
        nd = sum(1 for x in allres if x["diff_bytes"]); nz = sum(1 for x in allres if x["zbuf_mismatch"]); nb = sum(1 for x in allres if x["live_bars"])
        log("LIVE RESULT: %d frames: %d with differing bytes vs the reference, %d with zbuf mismatches, %d with black bars (live), %d with black bars (reference)" % (
            len(allres), nd, nz, nb, sum(1 for x in allres if x["ref_bars"])))
        (NIGHT / ("N4_angles_live%s.json" % a.tag)).write_text(json.dumps(allres))
        (ROOT / (a.out or "build/night/N4_angles_live%s.out" % a.tag)).write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
