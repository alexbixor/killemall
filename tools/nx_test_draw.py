#!/usr/bin/env python3
"""nx_test_draw.py - lane D2 test: replay the reference drawer call lists through src/next/draw.asm in ZEsarUX and
compare the LoRes screen with build/night/ref/<scene>.frame.bin (0 differing bytes required, spec section 9).

  .venv/bin/python tools/nx_test_draw.py [scene ...]        (default: hall corridor steps_down altar)

Per scene: assemble src/next/test_draw.asm (pasmo, cwd src/next), poke the 512-byte palette copy at PAL_COPY (8E00h),
encode <scene>.records.json as the byte-coded list (1 = piece c,ra,count,tex,s,u,v lo,v hi,dv lo,dv hi ; 2 = plane
c,h,tex,a,b ; 3 = void c,a,b ; 4 = next 8K chunk ; 0 = end) into 8K chunks = 8K banks 12.. (16K banks 6, 7),
build the .nex (banks 5 zero screen, 2 code, 4 tables, 8..11 walls.bin, 12 floors.bin, 6/7 records), run it headless,
wait for DONE (59FFh) = 1, dump the 12288-byte screen, compare, read T_RES (59FCh) = ticks for 20 replays,
save build/night/D2_<scene>.png. Results are appended to build/night/D2_result.out."""
import json, pathlib, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
ROOT = HERE.parent
SRC = ROOT / "src/next"
BIN = ROOT / "build/next/test_draw.bin"
SYM = ROOT / "build/next/test_draw.sym"
NEX = ROOT / "build/next/test_draw.nex"
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
OPS = {"DRAW_PIECE": 1, "PLANE_ADD": 2, "VOID": 3}


def assemble():
    r = subprocess.run(["pasmo", "--bin", "test_draw.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
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


def run_scene(scene, code, log):
    j = json.loads((REF / ("%s.records.json" % scene)).read_text())
    records = j["records"]
    chunks = encode_records(records)
    img = bytearray(16384)
    img[:len(code)] = code
    pal = (ASSETS / "palette.bin").read_bytes(); assert len(pal) == 512
    img[PAL_COPY - 0x8000:PAL_COPY - 0x8000 + 512] = pal
    walls = (ASSETS / "walls.bin").read_bytes(); assert len(walls) == 65536
    floors = (ASSETS / "floors.bin").read_bytes(); assert len(floors) == 8192
    # camera variables (spec 2/10) in the bank 5 image: px, py (Q8), eye (int8), dirx, diry, plx, ply (signed Q8)
    cam = j["camera"]
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
    ref = (REF / ("%s.frame.bin" % scene)).read_bytes(); assert len(ref) == 12288
    nbytes = sum(len(encode_record(r)) for r in records) + len(chunks)
    log("%s: %d records (%d bytes, %d chunk(s)), nex %d bytes" % (scene, len(records), nbytes, len(chunks), NEX.stat().st_size))
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(DONE, 1, timeout=90)
        scr = r.screen()
        tres = r.w16(T_RES); tcal = r.w16(T_CAL); ticks = r.w16(TICKS); pc = r.pc()
        if scr: NexRun.png(scr, OUT / ("D2_%s.png" % scene))
    if not ok or len(scr) != 12288:
        log("%s: FAIL done=%s screen=%d bytes pc=%04X (%.1fs)" % (scene, ok, len(scr), pc, time.time() - t0))
        return False
    diffs = [i for i in range(12288) if scr[i] != ref[i]]
    log("%s: %d differing bytes of 12288 ; ticks for 20 replays = %d (%.2f ticks = %.1f ms per frame, %.1f fps drawers only) ; calibration %d ticks (expect ~49 at 28 MHz) ; %.1fs" % (
        scene, len(diffs), tres, tres / 20.0, tres, 20 * 50.0 / tres if tres else 0, tcal, time.time() - t0))
    for i in diffs[:10]:
        log("   diff at row %d col %d: got %d expected %d" % (i // 128, i % 128, scr[i], ref[i]))
    (OUT / ("D2_%s.screen.bin" % scene)).write_bytes(scr)
    return not diffs


def main(argv):
    scenes = argv or ["hall", "corridor", "steps_down", "altar"]
    code = assemble()
    out = OUT / "D2_result.out"
    lines = []
    def log(s):
        print(s); lines.append(s)
    log("nx_test_draw %s : code %d bytes (8000h..%04Xh)" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), len(code), 0x8000 + len(code)))
    results = {}
    for sc in scenes:
        results[sc] = run_scene(sc, code, log)
    log("RESULT: " + " ".join("%s=%s" % (k, "PASS" if v else "FAIL") for k, v in results.items()))
    out.write_text("\n".join(lines) + "\n")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
