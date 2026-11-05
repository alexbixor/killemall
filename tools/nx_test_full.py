#!/usr/bin/env python3
"""nx_test_full.py - lane S end-to-end oracle: the real walker + real drawers (src/next/test_full.asm = walk.asm with the
plane-span coalescer + draw.asm, the same code main.asm links) render each spec section 9 scene headless; the 12288 screen
bytes must equal build/night/ref/<scene>.frame.bin (0 differing bytes) and T_RES gives the whole engine's ticks per frame.

    timeout 280 .venv/bin/python tools/nx_test_full.py [scene ...]      (default: corridor hall steps_down altar)

Outputs: build/next/test_full.{bin,sym,nex}, build/night/S_full_<scene>.png, stdout lines (save as build/night/S_*.out)."""
import os, pathlib, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
import nx_walk_ref as ref
ROOT = HERE.parent
SRC = ROOT / "src/next"
BIN, SYM, NEX = ROOT / "build/next/test_full.bin", ROOT / "build/next/test_full.sym", ROOT / "build/next/test_full.nex"
ASSETS = ROOT / "build/next/assets"
REF = ROOT / "build/night/ref"
OUT = ROOT / "build/night"
SCENE_ADDR, T_RES, T_CAL, DONE = 0x9F00, 0x59FC, 0x59F6, 0x59FF
TEST_SRC = os.environ.get("NX_TEST_FULL_SRC", "test_full.asm")   # test_full_pre.asm = same with the pre-lane-S draw.asm backup

def assemble():
    r = subprocess.run(["pasmo", "--bin", sys.argv[1] if False else TEST_SRC, str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
    return BIN.read_bytes()

def run_scene(scene, code):
    px, py, ang = ref.SCENES[scene]
    img = bytearray(code.ljust(16384, b"\0"))
    img[0xB800 - 0x8000:0xB800 - 0x8000 + 2048] = (ASSETS / "level0.bin").read_bytes()
    struct.pack_into("<HHH", img, SCENE_ADDR - 0x8000, px, py, ang)
    walls = (ASSETS / "walls.bin").read_bytes(); floors = (ASSETS / "floors.bin").read_bytes()
    banks = {5: bytes(16384), 2: bytes(img), 4: (ROOT / "build/next/tables_bank4.bin").read_bytes(), 12: floors + bytes(8192)}
    for k in range(4):
        banks[8 + k] = walls[k * 16384:(k + 1) * 16384]
    build_nex(NEX, banks, pc=0x8000, sp=0x5F00)
    refscr = (REF / ("%s.frame.bin" % scene)).read_bytes()
    t0 = time.time()
    with NexRun(NEX) as r:
        ok = r.wait_byte(DONE, 1, timeout=120)
        scr = r.screen(); tres = r.w16(T_RES); tcal = r.w16(T_CAL); pc = r.pc()
        if scr: NexRun.png(scr, OUT / ("S_full_%s.png" % scene))
    if not ok or len(scr) != 12288:
        print("%s: FAIL done=%s screen=%d bytes pc=%04X" % (scene, ok, len(scr), pc)); return False
    diffs = [i for i in range(12288) if scr[i] != refscr[i]]
    print("%s: %d differing bytes of 12288 ; ticks for 20 full frames = %d (%.2f ticks = %.1f ms per frame = %.1f fps) ; calibration %d ticks (~49 = 28 MHz) ; %.1fs"
          % (scene, len(diffs), tres, tres / 20.0, tres, 20 * 50.0 / tres if tres else 0, tcal, time.time() - t0))
    for i in diffs[:8]:
        print("   diff at row %d col %d: got %d expected %d" % (i // 128, i % 128, scr[i], refscr[i]))
    return not diffs

def main(argv):
    scenes = argv or ["corridor", "hall", "steps_down", "altar"]
    code = assemble()
    print("nx_test_full %s : code %d bytes (8000h..%04Xh)" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), len(code), 0x8000 + len(code)))
    res = {s: run_scene(s, code) for s in scenes}
    print("RESULT: " + " ".join("%s=%s" % (k, "PASS" if v else "FAIL") for k, v in res.items()))
    return 0 if all(res.values()) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
