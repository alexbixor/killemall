#!/usr/bin/env python3
"""D2 timing breakdown: replay the hall scene with subsets of the record ops (reuses tools/nx_test_draw.py)."""
import sys, json, pathlib
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
import nx_test_draw as T
from nx_nex import build_nex
from nx_run import NexRun
ROOT = pathlib.Path("/home/ubuntu/work/killemall")
code = T.assemble()
scene = sys.argv[1] if len(sys.argv) > 1 else "hall"
j = json.loads((T.REF / ("%s.records.json" % scene)).read_text())
cam = j["camera"]
pal = (T.ASSETS / "palette.bin").read_bytes(); walls = (T.ASSETS / "walls.bin").read_bytes(); floors = (T.ASSETS / "floors.bin").read_bytes()
for label, keep, noflush in (("all", {"DRAW_PIECE", "PLANE_ADD", "VOID"}, 0), ("pieces only", {"DRAW_PIECE"}, 0), ("planes only", {"PLANE_ADD"}, 0),
                            ("planes only, plane_add bookkeeping only (no flush)", {"PLANE_ADD"}, 1), ("none (replay loop + flush of nothing)", set(), 0)):
    recs = [r for r in j["records"] if r["op"] in keep]
    chunks = T.encode_records(recs)
    img = bytearray(16384); img[:len(code)] = code; img[T.PAL_COPY - 0x8000:T.PAL_COPY - 0x8000 + 512] = pal
    vars_img = bytearray(16384)
    def w16(addr, v): vars_img[addr - 0x4000] = v & 255; vars_img[addr - 0x4000 + 1] = (v >> 8) & 255
    w16(0x5802, cam["px"]); w16(0x5804, cam["py"]); vars_img[0x580A - 0x4000] = cam["eye"] & 255; vars_img[0x59F5 - 0x4000] = noflush
    w16(0x5810, cam["dirx"]); w16(0x5812, cam["diry"]); w16(0x5814, cam["plx"]); w16(0x5816, cam["ply"])
    banks = {5: bytes(vars_img), 2: bytes(img), 4: (ROOT / "build/next/tables_bank4.bin").read_bytes(), 12: floors + bytes(8192)}
    for k in range(4): banks[8 + k] = walls[k * 16384:(k + 1) * 16384]
    banks.update(T.record_banks(chunks))
    nex = ROOT / "build/next/test_draw_tim.nex"
    build_nex(nex, banks, pc=0x8000, sp=0x5F00)
    with NexRun(nex) as r:
        ok = r.wait_byte(T.DONE, 1, timeout=90); tres = r.w16(T.T_RES)
    print("%-45s records %5d : ticks for 20 replays = %3d (%.2f ticks/frame, %.1f ms/frame) done=%s" % (label, len(recs), tres, tres / 20.0, tres, ok))
