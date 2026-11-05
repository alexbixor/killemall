#!/usr/bin/env python3
"""nx_test_draw_b.py - lane N1D test: replay the v0.1 reference drawer call lists (build/night/ref/<scene>.records.json)
through src/next/draw_b.asm (edition B drawers) in ZEsarUX and compare the LoRes screen with the tier's frame from
tools/nx_ref_planes.py (hi = build/night/ref/<scene>.frame.bin exactly; lo / flat per spec v0.2 section 4).
0 differing bytes of 12288 per scene required; ticks per frame measured over 20 replays (T_RES / 20).

  .venv/bin/python tools/nx_test_draw_b.py [--tier hi|lo|flat|all] [--only pieces|planes] [--out NAME] [scene ...]
      default: all tiers, all record kinds, scenes hall corridor steps_down altar; output build/night/N1D_<tier>[_<only>].out
      --only pieces : replay DRAW_PIECE + VOID records only (walls alone, the frame comparison is skipped)
      --only planes : replay PLANE_ADD records only (planes alone, frame comparison skipped)

Per scene: assemble src/next/test_draw_b.asm (pasmo [--equ PLANES_LO=1 | --equ PLANES_FLAT=1], cwd src/next), poke the
palette copy at PAL_COPY (8E00h), encode the records as the byte-coded list (1 = piece c,ra,count,tex,s,u,v lo,v hi,dv lo,
dv hi ; 2 = plane c,h,tex,a,b ; 3 = void c,a,b ; 4 = next 8K chunk ; 0 = end) into 8K banks 12.. (16K banks 6, 7), build the
.nex (banks 5 zero screen + camera vars, 2 code, 4 tables, 8..11 walls.bin, 12 floors.bin), run it headless, wait for DONE
(59FFh) = 1, dump the screen, compare, read T_RES (59FCh) = ticks for 20 replays and T_CAL (59F6h, ~49 = 28 MHz).
Prints one RESULT line per tier; PNGs of the emulator screens go to build/night/N1D_<scene>.<tier>.png."""
import json, pathlib, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
import nx_ref_planes
ROOT = HERE.parent
SRC = ROOT / "src/next"
BIN = ROOT / "build/next/test_draw_b.bin"
SYM = ROOT / "build/next/test_draw_b.sym"
NEX = ROOT / "build/next/test_draw_b.nex"
ASSETS = ROOT / "build/next/assets"
REF = ROOT / "build/night/ref"
OUT = ROOT / "build/night"
PAL_COPY = 0x8E00
DONE = 0x59FF
T_RES = 0x59FC
T_CAL = 0x59F6         # calibration loop ticks (27263093 T-states: ~49 at 28 MHz, ~97 at 14 MHz)
TICKS = 0x5808
REC_BANK16 = 6          # first 16K bank of the record list (8K banks 12, 13, then 14, 15)
CHUNK = 8192
TIER_EQU = {"hi": [], "lo": ["--equ", "PLANES_LO=1"], "flat": ["--equ", "PLANES_FLAT=1"]}
SCENES = ["hall", "corridor", "steps_down", "altar"]


def assemble(tier):
    r = subprocess.run(["pasmo"] + TIER_EQU[tier] + ["--bin", "test_draw_b.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
    code = BIN.read_bytes()
    if len(code) > PAL_COPY - 0x8000:
        sys.exit("code too big: %d bytes, must end before 8E00h" % len(code))
    return code


def encode_record(rec):
    op = rec["op"]; a = rec["args"]
    if op == "DRAW_PIECE":
        c, ra, count, tex, s, u, v, dv = a
        assert 0 <= v < 65536 and 0 <= dv < 65536, rec
        return bytes([1, c, ra, count, tex, s, u, v & 255, v >> 8, dv & 255, dv >> 8])
    if op == "PLANE_ADD":
        c, h, tex, a_, b = a
        return bytes([2, c, h & 255, tex, a_, b])
    if op == "VOID":
        c, a_, b = a
        return bytes([3, c, a_, b])
    raise ValueError(op)


def encode_records(records):
    """-> list of 8K chunks; a record never straddles a chunk (op 4 = continue in the next chunk, 0 = end)."""
    chunks = []; cur = bytearray()
    for rec in records:
        e = encode_record(rec)
        if len(cur) + len(e) + 1 > CHUNK:          # keep room for the trailing 4/0 byte
            cur.append(4); chunks.append(bytes(cur).ljust(CHUNK, b"\0")); cur = bytearray()
        cur += e
    cur.append(0); chunks.append(bytes(cur).ljust(CHUNK, b"\0"))
    return chunks


def record_banks(chunks):
    banks = {}
    for i in range(0, len(chunks), 2):
        pair = chunks[i:i + 2]
        if len(pair) == 1: pair.append(bytes(CHUNK))
        banks[REC_BANK16 + i // 2] = pair[0] + pair[1]
    return banks


def run_scene(scene, tier, only, code, assets, log):
    j = json.loads((REF / ("%s.records.json" % scene)).read_text())
    cam = json.loads((REF / ("%s.camera.json" % scene)).read_text())
    records = j["records"]
    if only == "pieces":
        records = [r for r in records if r["op"] in ("DRAW_PIECE", "VOID")]
    elif only == "planes":
        records = [r for r in records if r["op"] == "PLANE_ADD"]
    chunks = encode_records(records)
    img = bytearray(16384)
    img[:len(code)] = code
    pal = (ASSETS / "palette.bin").read_bytes(); assert len(pal) == 512
    img[PAL_COPY - 0x8000:PAL_COPY - 0x8000 + 512] = pal
    walls = (ASSETS / "walls.bin").read_bytes(); assert len(walls) == 65536
    floors = (ASSETS / "floors.bin").read_bytes(); assert len(floors) == 8192
    # camera variables (spec 2/10) in the bank 5 image: px, py (Q8), eye (int8), dirx, diry, plx, ply (signed Q8)
    vars_img = bytearray(16384)
    def w16(addr, v): vars_img[addr - 0x4000] = v & 255; vars_img[addr - 0x4000 + 1] = (v >> 8) & 255
    w16(0x5802, cam["px"]); w16(0x5804, cam["py"]); w16(0x5806, cam["a"])
    vars_img[0x580A - 0x4000] = cam["eye"] & 255
    w16(0x5810, cam["dirx"]); w16(0x5812, cam["diry"]); w16(0x5814, cam["plx"]); w16(0x5816, cam["ply"])
    vars_img[0x5818 - 0x4000] = cam["mx"]; vars_img[0x5819 - 0x4000] = cam["my"]
    banks = {5: bytes(vars_img), 2: bytes(img), 4: (ROOT / "build/next/tables_bank4.bin").read_bytes(), 12: floors + bytes(8192)}
    for k in range(4):
        banks[8 + k] = walls[k * 16384:(k + 1) * 16384]
    banks.update(record_banks(chunks))
    build_nex(NEX, banks, pc=0x8000, sp=0x5F00)
    # the expected frame: nx_ref_planes (hi must equal build/night/ref/<scene>.frame.bin, proven in N1D_ref_hi.out)
    ref = nx_ref_planes.render_tier(j["records"], cam, assets[0], assets[1], tier)
    if tier == "hi":
        ref01 = (REF / ("%s.frame.bin" % scene)).read_bytes()
        assert ref == ref01, "nx_ref_planes hi frame differs from the v0.1 reference frame for %s" % scene
    nbytes = sum(len(encode_record(r)) for r in records) + len(chunks)
    log("%s/%s%s: %d records (%d bytes, %d chunk(s)), nex %d bytes" % (scene, tier, "/" + only if only else "", len(records), nbytes, len(chunks), NEX.stat().st_size))
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(DONE, 1, timeout=90)
        scr = r.screen()
        tres = r.w16(T_RES); tcal = r.w16(T_CAL); pc = r.pc()
        if scr and not only: NexRun.png(scr, OUT / ("N1D_%s.%s.png" % (scene, tier)))
    if not ok or len(scr) != 12288:
        log("%s/%s: FAIL done=%s screen=%d bytes pc=%04X (%.1fs)" % (scene, tier, ok, len(scr), pc, time.time() - t0))
        return None
    if only:
        log("%s/%s/%s: ticks for 20 replays = %d (%.2f ticks = %.1f ms per frame) ; calibration %d ticks (expect ~49 at 28 MHz) ; %.1fs" % (
            scene, tier, only, tres, tres / 20.0, tres, tcal, time.time() - t0))
        return (-1, tres / 20.0)
    diffs = [i for i in range(12288) if scr[i] != ref[i]]
    log("%s/%s: %d differing bytes of 12288 ; ticks for 20 replays = %d (%.2f ticks = %.1f ms per frame, %.1f fps drawers only) ; calibration %d ticks (expect ~49 at 28 MHz) ; %.1fs" % (
        scene, tier, len(diffs), tres, tres / 20.0, tres, 20 * 50.0 / tres if tres else 0, tcal, time.time() - t0))
    for i in diffs[:10]:
        log("   diff at row %d col %d: got %d expected %d" % (i // 128, i % 128, scr[i], ref[i]))
    (OUT / ("N1D_%s.%s.screen.bin" % (scene, tier))).write_bytes(scr)
    return (len(diffs), tres / 20.0)


def main(argv):
    tiers = ["hi", "lo", "flat"]; only = None; outname = None; scenes = []
    i = 0
    while i < len(argv):
        if argv[i] == "--tier":
            tiers = ["hi", "lo", "flat"] if argv[i + 1] == "all" else [argv[i + 1]]; i += 2
        elif argv[i] == "--only":
            only = argv[i + 1]; assert only in ("pieces", "planes"); i += 2
        elif argv[i] == "--out":
            outname = argv[i + 1]; i += 2
        else:
            scenes.append(argv[i]); i += 1
    scenes = scenes or SCENES
    assets = nx_ref_planes.load_assets()
    lines = []
    def log(s):
        print(s, flush=True); lines.append(s)
    all_ok = True
    for tier in tiers:
        code = assemble(tier)
        log("nx_test_draw_b %s tier %s%s: code %d bytes (8000h..%04Xh)" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), tier,
                                                                         " only " + only if only else "", len(code), 0x8000 + len(code)))
        res = {}
        for sc in scenes:
            res[sc] = run_scene(sc, tier, only, code, assets, log)
        if only:
            log("RESULT %s/%s: " % (tier, only) + " ".join("%s=%s" % (k, ("%.2f ticks" % v[1]) if v else "FAIL") for k, v in res.items()))
            all_ok &= all(v is not None for v in res.values())
        else:
            log("RESULT %s: " % tier + " ".join("%s=%s" % (k, ("PASS %.2f ticks" % v[1]) if v and v[0] == 0 else ("FAIL %s" % (("%d diffs" % v[0]) if v else "no run"))) for k, v in res.items()))
            all_ok &= all(v is not None and v[0] == 0 for v in res.values())
        out = OUT / ((outname or ("N1D_%s%s" % (tier, "_" + only if only else ""))) + ".out")
        out.write_text("\n".join(lines) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
