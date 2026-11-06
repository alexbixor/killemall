#!/usr/bin/env python3
"""nx_test_full_b.py - lane N1M end-to-end oracle for the Spectrum Next EDITION B program: src/next/test_full_b.asm = the real
program (main_b.asm: start-up, level parameters, walk_b.asm + draw_b.asm) with the camera forced to a spec v0.2 scene
(tools/nx_ref_flat.py SCENES: start, door, corridor, oblique) renders one frame headless; the 12288 LoRes bytes must equal
the Python reference frame of the compiled-in plane tier (nx_ref_flat.render_flat(..., tier=) with the SAME assets the
program ships: build/next/assets_b) - 0 differing bytes - and TFB_RES / 20 gives the whole engine's ticks per frame.

    timeout 580 .venv/bin/python tools/nx_test_full_b.py [--tier hi|lo|flat|all] [--assets build/next/assets_b]
                                   [--level build/night/N1_level01.bin] [--level-txt assets/levels/01_entry.txt]
                                   [--out build/night/N1M_full.out] [scene ...]

Per tier: pasmo [--equ PLANES_LO=1 | --equ PLANES_FLAT=1] --bin test_full_b.asm (cwd src/next), the 16K code image is
completed exactly as tools/nx_build.py does (palette at 9E00h, ONE mapc level at LEVEL, CEIL_B/FTEX_B/CTEX_B poked from the
level .txt), the scene (px, py, ang) is poked at TFB_SCENE (9D00h), banks 5 zero / 2 code / 4 tables / 8..11 walls.bin /
12 floors.bin, run in ZEsarUX (tools/nx_run.py), wait for TFB_DONE (59FFh) = 1, dump the screen, compare, read TFB_RES
(59FCh) and TFB_CAL (59F6h, ~49 ticks = 28 MHz). For tier hi the reference is also compared with lane N1's
build/night/ref_flat/<scene>.frame.bin (rendered with option A's assets: equal only where no edition B texture shows).
Outputs: build/next/test_full_b.{bin,sym,nex}, build/night/N1M_ref/<scene>.<tier>.frame.bin, build/night/N1M_full_<scene>.<tier>.png,
the log file (default build/night/N1M_full.out). Exit code 0 only when every scene of every tier has 0 differing bytes."""
import argparse, hashlib, pathlib, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
import nx_build
import nx_ref
import nx_ref_flat as ref
ROOT = HERE.parent
SRC = ROOT / "src/next"
BIN, SYM, NEX = ROOT / "build/next/test_full_b.bin", ROOT / "build/next/test_full_b.sym", ROOT / "build/next/test_full_b.nex"
NIGHT = ROOT / "build/night"
REF_DIR = NIGHT / "N1M_ref"
CODE_BASE = 0x8000
TIER_EQU = {"hi": ["--equ", "PLANES_HI=1"], "lo": ["--equ", "PLANES_LO=1"], "flat": ["--equ", "PLANES_FLAT=1"]}
TIMED_FRAMES = 20
CAL_T = 16 * (65535 * 26 + 21) + 16 * 12 + 5          # T-states of the calibration loop (test_walk_b.asm's arithmetic)
# N1M extra scenes (level 01, assets_b textures that lane N1's four scenes never show): the red door 'R' of map row 27
# (x = 23) seen from (23.5, 25.5) facing south, and the exit 'X' at (23, 29) seen from (20.5, 29.5) facing east.
# Level 01 has no blue door ('U'), so texture 6 cannot be shown from this level.
EXTRA_SCENES = {"reddoor": (0x1780, 0x1980, 256), "exit": (0x1480, 0x1D80, 0)}
for _k, _v in EXTRA_SCENES.items():
    ref.SCENES.setdefault(_k, _v)


def assemble(tier):
    r = subprocess.run(["pasmo"] + TIER_EQU[tier] + ["--bin", "test_full_b.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
    return BIN.read_bytes(), nx_build.read_syms(SYM)


def palette_rgb(pal):
    out = []
    for i in range(256):
        b0, b1 = pal[2 * i], pal[2 * i + 1]
        out.append((((b0 >> 5) & 7) * 255 // 7, ((b0 >> 2) & 7) * 255 // 7, ((((b0 & 3) << 1) | (b1 & 1)) * 255 // 7)))
    return out


def run_scene(scene, tier, code, syms, assets, lv_img, hb, opts, walls, floors, log, pal_rgb):
    px, py, ang = ref.SCENES[scene]
    img = bytearray(code.ljust(16384, b"\0"))
    img[nx_build.PALETTE_ADDR - CODE_BASE:nx_build.PALETTE_ADDR - CODE_BASE + 512] = (assets / "palette.bin").read_bytes()
    img[nx_build.LEVEL_ADDR - CODE_BASE:nx_build.LEVEL_ADDR - CODE_BASE + 2048] = lv_img
    for key in ("ceil", "ftex", "ctex"):                       # the same pokes as nx_build.poke_header, silently
        img[syms[nx_build.HEADER_SYMS[key]] - CODE_BASE] = hb[key]
    struct.pack_into("<HHH", img, syms["TFB_SCENE"] - CODE_BASE, px, py, ang)
    banks = {5: bytes(16384), 2: bytes(img), 4: nx_build.TABLES.read_bytes(), 12: floors.ljust(16384, b"\0")}
    for q in range(4):
        banks[8 + q] = walls[q * 16384:(q + 1) * 16384]
    build_nex(NEX, banks, pc=0x8000, sp=0x5F00)
    # the reference frame: lane N1's renderer, the compiled-in tier, the program's own assets and level parameters
    level_blob = lv_img[:8 + 1024 + 3 * lv_img[7]]
    exp, records, zbuf = ref.render_flat(level_blob, px, py, ang, nx_ref.WallTex(walls), nx_ref.FloorTex(floors), hb["ceil"], hb["ftex"], hb["ctex"], tier)
    REF_DIR.mkdir(parents=True, exist_ok=True)
    (REF_DIR / ("%s.%s.frame.bin" % (scene, tier))).write_bytes(exp)
    n_plane = sum(1 for r_ in records if r_["op"] == "PLANE_ADD"); n_piece = sum(1 for r_ in records if r_["op"] == "DRAW_PIECE"); n_void = sum(1 for r_ in records if r_["op"] == "VOID")
    note = ""
    if tier == "hi":
        old = NIGHT / "ref_flat" / ("%s.frame.bin" % scene)
        if old.exists():
            o = old.read_bytes(); nd = sum(1 for i in range(12288) if o[i] != exp[i])
            note = " ; reference vs lane N1's ref_flat/%s.frame.bin (option A assets): %d differing bytes" % (scene, nd)
    log("%s/%s: reference %d bytes sha1 %s, records %d (PLANE_ADD %d, DRAW_PIECE %d, VOID %d)%s" % (scene, tier, len(exp), hashlib.sha1(exp).hexdigest()[:12], len(records), n_plane, n_piece, n_void, note))
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(syms["TFB_DONE"], 1, timeout=120)
        scr = r.screen(); tres = r.w16(syms["TFB_RES"]); tcal = r.w16(syms["TFB_CAL"]); pc = r.pc()
        frames = r.w16(0x5800); eye = r.byte(0x580A); wceil, wftex, wctex = r.byte(0x5B00), r.byte(0x5B01), r.byte(0x5B02)
        if scr: NexRun.png(scr, NIGHT / ("N1M_full_%s.%s.png" % (scene, tier)), pal=pal_rgb)
    if not ok or len(scr) != 12288:
        log("%s/%s: FAIL done=%s screen=%d bytes pc=%04X (%.1fs)" % (scene, tier, ok, len(scr), pc, time.time() - t0)); return None
    diffs = [i for i in range(12288) if scr[i] != exp[i]]
    t_per_tick = CAL_T / tcal if tcal else 560000.0
    per = tres / float(TIMED_FRAMES)
    log("%s/%s: %d differing bytes of 12288 ; ticks for %d full frames = %d (%.2f ticks = %.1f ms per frame = %.1f fps; %.3f M T-states) ; calibration %d ticks (%.1f MHz) ; frames %d eye %d CEIL/FTEX/CTEX %d/%d/%d ; %.1fs"
        % (scene, tier, len(diffs), TIMED_FRAMES, tres, per, per * 20.0, 50.0 / per if per else 0.0, per * t_per_tick / 1e6, tcal, t_per_tick * 50 / 1e6, frames, eye, wceil, wftex, wctex, time.time() - t0))
    for i in diffs[:8]:
        log("   diff at row %d col %d: got %d expected %d" % (i // 128, i % 128, scr[i], exp[i]))
    (NIGHT / ("N1M_full_%s.%s.screen.bin" % (scene, tier))).write_bytes(scr)
    return (len(diffs), per)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", default="hi", help="hi | lo | flat | all")
    ap.add_argument("--assets", default="build/next/assets_b")
    ap.add_argument("--level", default="build/night/N1_level01.bin")
    ap.add_argument("--level-index", type=int, default=0)
    ap.add_argument("--level-start", action="store_true", help="lane N3F: scene `start` = the level header's camera (implied when --level-index > 0)")
    ap.add_argument("--level-txt", default="assets/levels/01_entry.txt")
    ap.add_argument("--out", default="build/night/N1M_full.out")
    ap.add_argument("scenes", nargs="*")
    a = ap.parse_args(argv)
    tiers = ["hi", "lo", "flat"] if a.tier == "all" else [a.tier]
    scenes = a.scenes or ["start", "door", "corridor", "oblique"]
    assets = ROOT / a.assets
    walls = (assets / "walls.bin").read_bytes(); floors = (assets / "floors.bin").read_bytes()
    pal_rgb = palette_rgb((assets / "palette.bin").read_bytes())
    lv_img = nx_build.level_image(ROOT / a.level, a.level_index)
    if a.level_index != 0 or a.level_start:
        # lane N3F (6 Nov 2026): for a level other than 01 the scene `start` is THAT level's mapc header camera (start cell centre,
        # angle * 4), as restart_level sets it; level 01's scene table (lane N1) is unchanged when --level-index is 0.
        ref.SCENES["start"] = (lv_img[4] * 256 + 128, lv_img[5] * 256 + 128, (lv_img[6] * 4) & 1023)
        print("level-start scene: (%.2f, %.2f) angle %d from the level header" % (ref.SCENES["start"][0] / 256, ref.SCENES["start"][1] / 256, ref.SCENES["start"][2]))
    opts = nx_build.level_header_options(ROOT / a.level_txt)
    hb = nx_build.header_bytes(opts, assets)
    lines = []
    def log(s): print(s, flush=True); lines.append(s)
    log("nx_test_full_b %s: assets %s (walls sha1 %s, floors sha1 %s), level %s, CEIL/FTEX/CTEX %d/%d/%d, scenes %s" % (
        time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), a.assets, hashlib.sha1(walls).hexdigest()[:12], hashlib.sha1(floors).hexdigest()[:12], a.level, hb["ceil"], hb["ftex"], hb["ctex"], " ".join(scenes)))
    all_ok = True
    for tier in tiers:
        code, syms = assemble(tier)
        log("tier %s: test_full_b.asm -> %d bytes (8000h..%04Xh), TFB_SCENE %04Xh, PLANES_LO=%d PLANES_FLAT=%d" % (tier, len(code), CODE_BASE + len(code), syms["TFB_SCENE"], syms.get("PLANES_LO", -1), syms.get("PLANES_FLAT", -1)))
        res = {}
        for sc in scenes:
            res[sc] = run_scene(sc, tier, code, syms, assets, lv_img, hb, opts, walls, floors, log, pal_rgb)
        log("RESULT %s: " % tier + " ".join("%s=%s" % (k, ("PASS %.2f ticks" % v[1]) if v and v[0] == 0 else ("FAIL %s" % (("%d diffs %.2f ticks" % v) if v else "no run"))) for k, v in res.items()))
        all_ok &= all(v is not None and v[0] == 0 for v in res.values())
        (ROOT / a.out).write_text("\n".join(lines) + "\n")
    log("RESULT: %s" % ("ALL PASS (%s)" % ", ".join(tiers) if all_ok else "FAILED"))
    (ROOT / a.out).write_text("\n".join(lines) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
