#!/usr/bin/env python3
"""nx_test_walk.py - lane D1 test driver: assemble src/next/test_walk.asm, build the .nex, run it headless (tools/nx_run.py)
for each scene of spec section 9, and compare the walker's DRAW_PIECE / PLANE_ADD / VOID call list and ZBUF with the
reference (build/night/ref/<scene>.records.json from lane R when present, else tools/nx_walk_ref.py = this lane's Python
transcription of the spec). Also checks smul_shr / umul32 and yproj / ROW vectors and reports ticks per walk_frame.

    timeout 600 .venv/bin/python tools/nx_test_walk.py [--scenes corridor,hall,...] [--frames 20] [--skip-asm]

Outputs: build/next/test_walk.{bin,sym,nex}, build/night/D1_<scene>.out, build/night/D1_<scene>.records.json,
build/night/D1_summary.out (and build/night/D1_level0.bin when lane R's level0.bin is missing).
Exit code 0 only when every scene matches bit for bit."""
import argparse, json, pathlib, random, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
import nx_walk_ref as ref

SRC = ROOT / "src/next"
BIN, SYM, NEX = ROOT / "build/next/test_walk.bin", ROOT / "build/next/test_walk.sym", ROOT / "build/next/test_walk.nex"
NIGHT = ROOT / "build/night"
TABLES = ROOT / "build/next/tables_bank4.bin"
LEVEL_ASSET = ROOT / "build/next/assets/level0.bin"
CODE_BASE = 0x8000

def sym(name):
    for line in SYM.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == name:
            return int(parts[2].rstrip("Hh"), 16)
    raise KeyError(name)

def assemble():
    r = subprocess.run(["pasmo", "--bin", "test_walk.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)

def to_s16(v): return v - 65536 if v >= 32768 else v
def to_s32(v): return v - (1 << 32) if v >= (1 << 31) else v
def s8(v): return v - 256 if v >= 128 else v

def mul_vectors():
    rnd = random.Random(1)
    vec = [(-256, 127, 7), (256, -127, 7), (-256, -127, 7), (0, 5000, 8), (-512, 4095, 8), (511, 4095, 8), (-32768, -32768, 0),
           (-32768, 32767, 31), (32767, 32767, 16), (-1, 1, 0), (1, -1, 1), (-181, 0x7FFF, 14), (4095, -256, 10), (255, 65535, 8),
           (0xFFFF, 0xFFFF, 255), (0, 0xFFFF, 255), (12345, 54321, 255), (0x8000, 0x8000, 255)]   # s = 255 -> umul32(a, b) unsigned
    while len(vec) < 48:
        vec.append((rnd.randint(-32768, 32767), rnd.randint(-32768, 32767), rnd.randint(0, 24)))
    exp = []
    for a, b, s in vec:
        if s == 255:
            exp.append((a & 0xFFFF) * (b & 0xFFFF))
        else:
            exp.append(ref.smul_shr(to_s16(a & 0xFFFF), to_s16(b & 0xFFFF), s) & 0xFFFFFFFF)   # operands are signed int16
    blob = bytes([len(vec)]) + b"".join(struct.pack("<HHB", a & 0xFFFF, b & 0xFFFF, s) for a, b, s in vec)
    return vec, exp, blob

def y_vectors():
    rnd = random.Random(2)
    vec = [(-80, 6, 8), (64, -16, 8), (0, 22, 8), (22, 22, 300), (32, 22, 300), (0, 22, 4095), (64, 22, 4095), (0, 22, 5000),
           (0, 22, 0), (0, 22, 1), (0, 22, 7), (-24, 6, 100), (64, 6, 2000), (112, 0, 8), (8, 22, 64), (20, 22, 64), (-16, 6, 9),
           (-80, 32, 8), (112, -16, 8), (-128, 0, 8), (127, 0, 8), (-106, 22, 8), (-128, 0, 4095), (127, 0, 4095), (23, 22, 8), (21, 22, 8),
           (-24, 22, 9), (64, 22, 9), (0, 30, 23), (0, -2, 23), (-16, 6, 11), (64, 6, 29), (64, 6, 30), (64, 6, 31)]   # h - eye stays in int8 (spec section 3)
    while len(vec) < 64:
        vec.append((rnd.randint(-80, 112) if rnd.random() < 0.5 else rnd.choice([-24, -16, -8, 0, 8, 20, 32, 64]), rnd.choice([6, 22, -2, 30]), rnd.randint(0, 5000)))
    exp = []
    for h, eye, d in vec:
        y = ref.clamp16(48 * 256 - (h - eye) * ref.R(d))
        exp.append((y, ref.ROW(y)))
    blob = bytes([len(vec)]) + b"".join(struct.pack("<bbH", h, eye, d) for h, eye, d in vec)
    return vec, exp, blob

def level_bytes(log):
    if LEVEL_ASSET.exists() and LEVEL_ASSET.stat().st_size == 2048:
        lv = LEVEL_ASSET.read_bytes()
        mine = ref.level_bytes()
        diff = sum(1 for i in range(2048) if lv[i] != mine[i])
        log("level: using lane R's %s (%d bytes differ from this lane's section 7 encoding)" % (LEVEL_ASSET.relative_to(ROOT), diff))
        return lv
    lv = ref.level_bytes()
    (NIGHT / "D1_level0.bin").write_bytes(lv)
    log("level: lane R's level0.bin not found -> built build/night/D1_level0.bin from the spec section 7 map myself")
    return lv

def load_lane_r_records(scene, log):
    """build/night/ref/<scene>.records.json -> (records, zbuf) in this tool's tuple format, or None if absent/unparseable."""
    p = NIGHT / "ref" / ("%s.records.json" % scene)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        recs_in = data["records"] if isinstance(data, dict) else data
        zbuf = data.get("zbuf") if isinstance(data, dict) else None
        out = []
        for r in recs_in:
            if isinstance(r, dict) and "op" in r and "args" in r:            # lane R's format: {"op": "PLANE_ADD", "args": [...], ...}
                op = r["op"].upper(); a = [int(v) for v in r["args"]]
                if op == "DRAW_PIECE": out.append(["piece"] + a)
                elif op == "PLANE_ADD": out.append(["plane"] + a)
                elif op == "VOID": out.append(["void"] + a)
                else: raise ValueError("unknown op %r" % op)
            elif isinstance(r, dict):
                kind = str(r.get("kind", r.get("type", r.get("call", "")))).lower()
                if kind.startswith("piece") or kind.startswith("draw"):
                    out.append(["piece", r["c"], r["ra"], r["count"], r["tex"], r["s"], r["u"], r.get("v_first", r.get("v")), r["dv"]])
                elif kind.startswith("plane"):
                    out.append(["plane", r["c"], r["h"], r["tex"], r["a"], r["b"]])
                elif kind.startswith("void"):
                    out.append(["void", r["c"], r["a"], r["b"]])
                else:
                    raise ValueError("unknown record kind %r" % kind)
            else:
                k = str(r[0]).lower()
                k = "piece" if k.startswith("piece") or k.startswith("draw") else "plane" if k.startswith("plane") else "void" if k.startswith("void") else None
                if k is None: raise ValueError("unknown record %r" % (r,))
                out.append([k] + list(r[1:]))
        return out, zbuf
    except Exception as e:  # noqa
        log("  WARNING: lane R file %s exists but could not be parsed (%s) -> falling back to the Python transcription" % (p.relative_to(ROOT), e))
        return None

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

def run_scene(scene, code, lv, frames, log):
    px, py, ang = ref.SCENES[scene]
    img = bytearray(code.ljust(16384, b"\0"))
    img[0xB800 - CODE_BASE:0xB800 - CODE_BASE + 2048] = lv
    struct.pack_into("<HHHB", img, sym("SCENE") - CODE_BASE, px, py, ang, frames)
    mvec, mexp, mblob = mul_vectors(); img[sym("MULTEST") - CODE_BASE:sym("MULTEST") - CODE_BASE + len(mblob)] = mblob
    yvec, yexp, yblob = y_vectors(); img[sym("YTEST") - CODE_BASE:sym("YTEST") - CODE_BASE + len(yblob)] = yblob
    build_nex(NEX, {5: bytes(16384), 2: bytes(img), 4: TABLES.read_bytes(), 6: bytes(16384)}, pc=0x8000, sp=0x5F00)
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(sym("DONE_FLAG"), 1, timeout=60)
        if not ok:
            log("%s: TIMEOUT waiting for the done flag (PC=%04X)" % (scene, r.pc())); return False
        secs = time.time() - t0
        mres = r.rd(sym("MULRES"), 4 * len(mvec)); yres = r.rd(sym("YRES"), 3 * len(yvec))
        count = r.w16(sym("LOG_COUNT")); ptr = r.w16(sym("LOG_PTR"))
        nbytes = ptr - sym("LOG_BASE")
        buf = r.rd(sym("LOG_BASE"), nbytes) if nbytes > 0 else b""
        zraw = r.rd(0x1A00, 256)
        ticks, dticks, frames_done, tcal = r.w16(0x5808), r.w16(sym("T_DTICKS")), r.w16(0x5800), r.w16(sym("T_CAL"))
        cam = [r.byte(0x580A), r.byte(0x5818), r.byte(0x5819), to_s16(r.w16(0x5810)), to_s16(r.w16(0x5812)), to_s16(r.w16(0x5814)), to_s16(r.w16(0x5816))]
    # --- unit vectors
    mfail = [(mvec[i], mexp[i], struct.unpack_from("<I", mres, 4 * i)[0]) for i in range(len(mvec)) if struct.unpack_from("<I", mres, 4 * i)[0] != mexp[i]]
    yfail = []
    for i in range(len(yvec)):
        y, row = struct.unpack_from("<hB", yres, 3 * i)
        if (y, row) != yexp[i]: yfail.append((yvec[i], yexp[i], (y, row)))
    log("%s: smul_shr/umul32 vectors %d, failures %d %s" % (scene, len(mvec), len(mfail), mfail[:5]))
    log("%s: yproj/ROW vectors %d, failures %d %s" % (scene, len(yvec), len(yfail), yfail[:5]))
    # --- records
    z80 = decode_log(buf, count)
    zbuf = [struct.unpack_from("<H", zraw, 2 * i)[0] for i in range(128)]
    lane_r = load_lane_r_records(scene, log)
    py_recs, py_zbuf, exp_cam = ref.walk(lv, px, py, ang)
    if lane_r is not None:
        exp, exp_zbuf = lane_r
        src = "lane R build/night/ref/%s.records.json" % scene
        if exp_zbuf is None:
            exp_zbuf = py_zbuf
        pyd = sum(1 for i in range(max(len(exp), len(py_recs))) if (exp[i] if i < len(exp) else None) != ([py_recs[i][0]] + [int(v) for v in py_recs[i][1:]] if i < len(py_recs) else None))
        log("%s: cross-check: lane R's records vs this lane's Python transcription: %d records vs %d, %d differing positions" % (scene, len(exp), len(py_recs), pyd))
    else:
        exp, exp_zbuf = py_recs, py_zbuf
        src = "this lane's Python transcription (tools/nx_walk_ref.py) - lane R's records.json not present"
    exp = [[r[0]] + [int(v) for v in r[1:]] for r in exp]
    mism = [(i, exp[i] if i < len(exp) else None, z80[i] if i < len(z80) else None) for i in range(max(len(exp), len(z80))) if (exp[i] if i < len(exp) else None) != (z80[i] if i < len(z80) else None)]
    zmism = [(c, exp_zbuf[c], zbuf[c]) for c in range(128) if exp_zbuf[c] != zbuf[c]]
    log("%s: camera px=%04X py=%04X a=%d -> Z80 eye=%d mx=%d my=%d dirx=%d diry=%d plx=%d ply=%d (ref eye=%d mx=%d my=%d)" % (scene, px, py, ang, s8(cam[0]), cam[1], cam[2], cam[3], cam[4], cam[5], cam[6],
        exp_cam['eye'], exp_cam['mx'], exp_cam['my']))
    log("%s: reference = %s" % (scene, src))
    log("%s: records Z80 %d (log %d bytes%s), reference %d, mismatching positions %d; ZBUF mismatches %d" % (scene, count, nbytes, "" if count == len(z80) else ", DECODED %d" % len(z80), len(exp), len(mism), len(zmism)))
    for i, e, g in mism[:10]:
        log("   #%d expected %s got %s" % (i, e, g))
    for c, e, g in zmism[:10]:
        log("   ZBUF[%d] expected %d got %d" % (c, e, g))
    per = dticks / frames if frames else 0.0
    CAL_T = 16 * (65535 * 26 + 21) + 16 * 12 + 5          # T-states of the in-program calibration loop (test_walk.asm step 4b)
    t_per_tick = CAL_T / tcal if tcal else 567264.0        # nominal: 311 lines x 228 T x 8 = 567264 T per 50 Hz frame at 28 MHz
    tst = per * t_per_tick
    log("%s: timing: %d ticks for %d walk_frame calls (stubs disabled) = %.2f ticks/frame = %.2f M T-states/frame (calibration: %d ticks for %.2f M T = %.0f T/tick, i.e. %.1f MHz); budget 0.6 frame = 0.34 M T -> %.0fx over; total ticks %d, frames %d, wall %.1fs"
        % (scene, dticks, frames, per, tst / 1e6, tcal, CAL_T / 1e6, t_per_tick, t_per_tick * 50 / 1e6, tst / 340358 if tst else 0, ticks, frames_done, secs))
    (NIGHT / ("D1_%s.records.json" % scene)).write_text(json.dumps({"scene": scene, "px": px, "py": py, "a": ang, "records": z80, "zbuf": zbuf}))
    return not mism and not zmism and not mfail and not yfail and count == len(z80)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="corridor,hall,steps_down,altar")
    ap.add_argument("--frames", type=int, default=20, help="timing frames after the logged one")
    ap.add_argument("--skip-asm", action="store_true")
    args = ap.parse_args()
    NIGHT.mkdir(parents=True, exist_ok=True)
    if not args.skip_asm: assemble()
    code = BIN.read_bytes()
    summary = []
    def slog(s): print(s); summary.append(s)
    slog("test_walk.bin %d bytes; walk.asm %d bytes (walk_begin %04X..walk_end %04X), code_end %04X" % (len(code), sym("walk_end") - sym("walk_begin"), sym("walk_begin"), sym("walk_end"), sym("code_end")))
    lv = level_bytes(slog)
    results = {}
    for scene in args.scenes.split(","):
        lines = []
        def log(s): print(s); lines.append(s)
        results[scene] = run_scene(scene, code, lv, args.frames, log)
        (NIGHT / ("D1_%s.out" % scene)).write_text("\n".join(lines) + "\n")
        summary.extend(lines)
    verdict = "ALL %d SCENES MATCH" % len(results) if all(results.values()) else "FAILED: " + ", ".join(s for s, ok in results.items() if not ok)
    slog("RESULT: %s" % verdict)
    (NIGHT / "D1_summary.out").write_text("\n".join(summary) + "\n")
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()
