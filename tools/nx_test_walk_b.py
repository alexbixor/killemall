#!/usr/bin/env python3
"""nx_test_walk_b.py - lane N1 oracle: assemble src/next/test_walk_b.asm, build the .nex, run it headless (tools/nx_run.py)
per scene and compare the walker's DRAW_PIECE / PLANE_ADD / VOID call list + ZBUF with build/night/ref_flat/<scene>.records.json
(tools/nx_ref_flat.py). Prints ticks/frame per scene (stubs disabled) and one RESULT line.

    timeout 580 .venv/bin/python tools/nx_test_walk_b.py [--scenes start,door,corridor,oblique] [--frames 20] [--skip-asm]

Outputs: build/next/test_walk_b.{bin,sym,nex}, build/night/N1_test_walk_b.out, build/night/N1_<scene>.records.json.
Exit code 0 only when every scene matches."""
import argparse, json, pathlib, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
import nx_ref_flat as ref

SRC = ROOT / "src/next"
BIN, SYM, NEX = ROOT / "build/next/test_walk_b.bin", ROOT / "build/next/test_walk_b.sym", ROOT / "build/next/test_walk_b.nex"
NIGHT = ROOT / "build/night"
TABLES = ROOT / "build/next/tables_bank4.bin"
CODE_BASE = 0x8000
CEIL, FTEX, CTEX = 32, 0, 1

def sym(name):
    for line in SYM.read_text().splitlines():
        parts = line.replace("\t", " ").split()
        if len(parts) >= 3 and parts[0] == name:
            return int(parts[2].rstrip("Hh"), 16)
    raise KeyError(name)

def assemble():
    r = subprocess.run(["pasmo", "--bin", "test_walk_b.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)

def decode_log(buf, count):
    recs, i = [], 0
    for _ in range(count):
        if i >= len(buf): break
        t = buf[i]
        if t == 1:
            c, ra, cnt, tex, s, u, v, dv = struct.unpack_from("<BBBBBBHH", buf, i + 1); recs.append(["piece", c, ra, cnt, tex, s, u, v, dv]); i += 11
        elif t == 2:
            c, h, tex, a, b = struct.unpack_from("<BbBBB", buf, i + 1); recs.append(["plane", c, h, tex, a, b]); i += 6
        elif t == 3:
            c, a, b = struct.unpack_from("<BBB", buf, i + 1); recs.append(["void", c, a, b]); i += 4
        else:
            recs.append(["bad", t]); break
    return recs

def load_ref(scene):
    data = json.loads((NIGHT / "ref_flat" / ("%s.records.json" % scene)).read_text())
    out = []
    for r in data["records"]:
        op = r["op"]; a = [int(v) for v in r["args"]]
        out.append([{"DRAW_PIECE": "piece", "PLANE_ADD": "plane", "VOID": "void"}[op]] + a)
    return out, data["zbuf"], data["camera"]

def run_scene(scene, code, lv, frames, log):
    px, py, ang = ref.SCENES[scene]
    img = bytearray(code.ljust(16384, b"\0"))
    img[0xB800 - CODE_BASE:0xB800 - CODE_BASE + len(lv)] = lv
    struct.pack_into("<HHHBBBB", img, sym("WB_SCENE") - CODE_BASE, px, py, ang, frames, CEIL, FTEX, CTEX)
    build_nex(NEX, {5: bytes(16384), 2: bytes(img), 4: TABLES.read_bytes(), 6: bytes(16384)}, pc=0x8000, sp=0x5F00)
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(sym("WB_DONE"), 1, timeout=90)
        if not ok:
            log("%s: TIMEOUT waiting for the done flag (PC=%04X)" % (scene, r.pc())); return False, 0.0
        secs = time.time() - t0
        count = r.w16(sym("WB_LOG_COUNT")); ptr = r.w16(sym("WB_LOG_PTR"))
        nbytes = ptr - sym("WB_LOG_BASE")
        buf = r.rd(sym("WB_LOG_BASE"), nbytes) if nbytes > 0 else b""
        zraw = r.rd(0x1A00, 256)
        ticks, dticks, frames_done, tcal = r.w16(0x5808), r.w16(sym("WB_T_DTICKS")), r.w16(0x5800), r.w16(sym("WB_T_CAL"))
        eye, mx, my = r.byte(0x580A), r.byte(0x5818), r.byte(0x5819)
    z80 = decode_log(buf, count)
    zbuf = [struct.unpack_from("<H", zraw, 2 * i)[0] for i in range(128)]
    exp, exp_zbuf, cam = load_ref(scene)
    mism = [(i, exp[i] if i < len(exp) else None, z80[i] if i < len(z80) else None) for i in range(max(len(exp), len(z80))) if (exp[i] if i < len(exp) else None) != (z80[i] if i < len(z80) else None)]
    zmism = [(c, exp_zbuf[c], zbuf[c]) for c in range(128) if exp_zbuf[c] != zbuf[c]]
    log("%s: camera px=%04X py=%04X a=%d CEIL=%d FTEX=%d CTEX=%d -> Z80 eye=%d mx=%d my=%d (ref eye=%d mx=%d my=%d)" % (scene, px, py, ang, CEIL, FTEX, CTEX, eye, mx, my, cam["eye"], cam["mx"], cam["my"]))
    log("%s: records Z80 %d (log %d bytes%s), reference %d (build/night/ref_flat/%s.records.json), mismatching positions %d; ZBUF mismatches %d" % (
        scene, count, nbytes, "" if count == len(z80) else ", DECODED %d" % len(z80), len(exp), scene, len(mism), len(zmism)))
    for i, e, g in mism[:10]:
        log("   #%d expected %s got %s" % (i, e, g))
    for c, e, g in zmism[:10]:
        log("   ZBUF[%d] expected %d got %d" % (c, e, g))
    per = dticks / frames if frames else 0.0
    CAL_T = 16 * (65535 * 26 + 21) + 16 * 12 + 5
    t_per_tick = CAL_T / tcal if tcal else 567264.0
    tst = per * t_per_tick
    log("%s: timing: %d ticks for %d walk_frame_b calls (stubs disabled) = %.3f ticks/frame = %.3f M T-states/frame (calibration: %d ticks for %.2f M T = %.0f T/tick = %.1f MHz); target 0.8 ticks -> %s; total ticks %d, frames %d, wall %.1fs"
        % (scene, dticks, frames, per, tst / 1e6, tcal, CAL_T / 1e6, t_per_tick, t_per_tick * 50 / 1e6, "OK" if per <= 0.8 else "OVER", ticks, frames_done, secs))
    (NIGHT / ("N1_%s.records.json" % scene)).write_text(json.dumps({"scene": scene, "px": px, "py": py, "a": ang, "records": z80, "zbuf": zbuf}))
    return (not mism and not zmism and count == len(z80)), per

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="start,door,corridor,oblique")
    ap.add_argument("--frames", type=int, default=50, help="timing frames after the logged one")
    ap.add_argument("--skip-asm", action="store_true")
    args = ap.parse_args()
    NIGHT.mkdir(parents=True, exist_ok=True)
    if not args.skip_asm: assemble()
    code = BIN.read_bytes()
    lines = []
    def log(s): print(s, flush=True); lines.append(s)
    log("test_walk_b.bin %d bytes; walk_b.asm %d bytes (walk_b_begin %04X..walk_b_end %04X), code_end %04X" % (len(code), sym("walk_b_end") - sym("walk_b_begin"), sym("walk_b_begin"), sym("walk_b_end"), sym("code_end")))
    lv = ref.LEVEL_BIN.read_bytes()[1:]           # mapc file -> the first level (skip the level-count byte)
    log("level: %s (%d bytes incl. the count byte) -> %d bytes at LEVEL" % (ref.LEVEL_BIN.relative_to(ROOT), len(lv) + 1, len(lv)))
    results, ticks = {}, {}
    for scene in args.scenes.split(","):
        results[scene], ticks[scene] = run_scene(scene, code, lv, args.frames, log)
    verdict = "ALL %d SCENES MATCH" % len(results) if all(results.values()) else "FAILED: " + ", ".join(s for s, ok in results.items() if not ok)
    log("TICKS/FRAME: " + ", ".join("%s %.3f" % (s, t) for s, t in ticks.items()) + " (target <= 0.8)")
    log("RESULT: %s" % verdict)
    (NIGHT / "N1_test_walk_b.out").write_text("\n".join(lines) + "\n")
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()
