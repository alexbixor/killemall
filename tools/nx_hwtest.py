#!/usr/bin/env python3
"""nx_hwtest.py - lane H1: assemble src/next/hwtest.asm, pack build/next/hwtest.nex (bank 2 code, bank 5 zero, PC 8000h,
SP 5F00h), run it headless in ZEsarUX (tools/nx_run.py NexRun, TBBlue at true 28 MHz), wait for the result block's DONE word,
read the ULA screen (4000h..57FFh) over ZRCP, decode every 8x8 cell against the 48K ROM font (tools/zesarux/48.rom, glyphs at
3D00h), read the result block at 5F80h and run the oracles of build/night/H1_BRIEF.md:
  - DONE within 20 s; every printed number equals the result-block value it came from;
  - line 4 says NOT FOUND (ZEsarUX has the plain TBBlue DMA);
  - CPU / SRAM / BLOCKRAM 25.0 <= MHz <= 29.0;
  - fills verified (status 0), CPU and LDIR within 20% of the T-state prediction at the measured MHz, plain zxnDMA measured,
    zxnDDMA fills SKIPPED (or, with --equ FORCE_FOUND=1, run and reported BAD without hanging).
Usage: .venv/bin/python tools/nx_hwtest.py [--equ NAME=VAL ...] [--out build/next/hwtest.nex] [--bin-name hwtest]
       [--png build/night/H1_hwtest.png] [--expect-found 0|1] [--expect-bad-ddma] [--timeout 20]
Prints the decoded screen, the result block and PASS/FAIL per oracle; exit code 0 only when every oracle passes."""
import argparse, hashlib, pathlib, re, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
from run48 import scr_to_png

ROM = HERE / "zesarux/48.rom"
R = 0x5F80
T_CPU = 100 * (50219 + 304)        # hwtest.asm header: cpu_chunk 50219 T incl. call + 304 T of timed_run per iteration
T_MEM = 100 * (48796 + 304)
T_FILL_CPU = 156231                 # fill_cpu incl. call
T_FILL_LDIR = 258086                # fill_ldir incl. call
FILL_NAMES = ["CPU SRAM", "CPU BLK", "LDIR SRAM", "LDIR BLK", "ZXNDMA SRAM", "ZXNDMA BLK", "DDMA3 SRAM", "DDMA3 BLK", "DDMA2 SRAM", "DDMA2 BLK"]

def assemble(src, bin_path, sym_path, equs):
    cmd = ["pasmo"]
    for e in equs: cmd += ["--equ", e]
    cmd += ["--bin", src.name, str(bin_path), str(sym_path)]
    r = subprocess.run(cmd, cwd=src.parent, capture_output=True, text=True)
    if r.returncode != 0: sys.exit("pasmo failed (%d): %s%s" % (r.returncode, r.stdout, r.stderr))
    return pathlib.Path(bin_path).read_bytes()

def read_syms(path):
    syms = {}
    for line in pathlib.Path(path).read_text().splitlines():
        p = line.split()
        if len(p) >= 3 and p[1].upper() == "EQU":
            try: syms[p[0]] = int(p[2].rstrip("Hh"), 16)
            except ValueError: pass
    return syms

def font():
    rom = ROM.read_bytes()
    return {bytes(rom[0x3D00 + 8 * (c - 32):0x3D00 + 8 * (c - 32) + 8]): chr(c) for c in range(32, 128)}

def decode_screen(scr, glyphs):
    """24 rows of 32 characters from the 6144 pixel bytes; an unknown glyph prints as '?'"""
    rows = []
    for row in range(24):
        line = ""
        for col in range(32):
            cell = bytes(scr[((row & 0x18) << 8) + ((row & 7) << 5) + (k << 8) + col] for k in range(8))
            line += glyphs.get(cell, "?")
        rows.append(line.rstrip())
    return rows

def w(b, off): return b[off] | (b[off + 1] << 8)

def parse_block(b):
    d = {"done": w(b, 0), "mach": w(b, 2), "core": w(b, 4), "sub": w(b, 6), "board": w(b, 8), "ddma": w(b, 10), "probe_to": b[12], "probe_pg60": b[13],
         "lpf": w(b, 14), "nr03": b[16], "nr05": b[17], "tline": w(b, 18), "cpu_ln": w(b, 20), "cpu_mhz": w(b, 22), "sram_ln": w(b, 24), "sram_mhz": w(b, 26),
         "blk_ln": w(b, 28), "blk_mhz": w(b, 30), "speed": w(b, 0x5C), "runs": w(b, 0x5E), "t_cpu": w(b, 0x60) | (w(b, 0x62) << 16),
         "t_mem": w(b, 0x64) | (w(b, 0x66) << 16), "marker": b[0x68], "forced": b[0x69]}
    d["fills"] = [{"name": FILL_NAMES[i], "lines": w(b, 0x20 + 6 * i), "us": w(b, 0x22 + 6 * i), "status": b[0x24 + 6 * i], "sentinel": b[0x25 + 6 * i]} for i in range(10)]
    return d

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="src/next/hwtest.asm")
    ap.add_argument("--out", default="build/next/hwtest.nex")
    ap.add_argument("--bin-name", default="hwtest")
    ap.add_argument("--equ", action="append", default=[], help="pasmo --equ NAME=VAL (repeatable): PROBE_MARK=5Bh, FORCE_FOUND=1")
    ap.add_argument("--png", default="build/night/H1_hwtest.png")
    ap.add_argument("--expect-found", type=int, default=0, help="expected R_DDMA value (0 not found on ZEsarUX, 2 forced)")
    ap.add_argument("--expect-bad-ddma", action="store_true", help="FORCE_FOUND run on a plain DMA: the DDMA fills must report BAD, not hang")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--no-run", action="store_true", help="build only")
    a = ap.parse_args()
    src = ROOT / a.src
    bin_path, sym_path = ROOT / ("build/next/%s.bin" % a.bin_name), ROOT / ("build/next/%s.sym" % a.bin_name)
    code = assemble(src, bin_path, sym_path, a.equ)
    syms = read_syms(sym_path)
    code_end = 0x8000 + len(code)
    print("assembled %s (equ %s) -> %s: %d bytes, 8000h..%04Xh; code_end sym %04Xh, SRAM_BUF %04Xh, probe_to %04Xh (PROBE_OFF %04Xh), detect_dma %04Xh" % (
        a.src, a.equ or "-", bin_path.relative_to(ROOT), len(code), code_end, syms.get("code_end", -1), syms.get("SRAM_BUF", -1), syms.get("probe_to", -1), syms.get("PROBE_OFF", -1), syms.get("detect_dma", -1)))
    ok_all = True
    def check(name, cond, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(cond)
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))
    check("code ends below SRAM_BUF (9F00h)", code_end <= syms.get("SRAM_BUF", 0x9F00), "%04Xh" % code_end)
    check("probe_to in 8000h..9FFFh (page 60 rule of zxnddma_compare.asm)", 0x8000 <= syms.get("probe_to", 0) < 0xA000)
    detect = bytes([0x83, 0xC3, 0xD7, 0x04, 0xDB, 0x0B, 0xDF, 0x01] + [0x83] * 8 + [0x7D])
    i = code.find(detect)
    check("detect_dma bytes verbatim (83 C3 D7 04 DB 0B DF 01, 8 x 83, 7D)", i >= 0 and i == syms.get("detect_dma", -1) - 0x8000, "at %04Xh" % (0x8000 + i))
    out = ROOT / a.out
    build_nex(out, {5: bytes(16384), 2: bytes(code).ljust(16384, b"\0")}, pc=0x8000, sp=0x5F00)
    print("wrote %s (%d bytes, md5 %s, banks [2, 5], PC 8000h SP 5F00h)" % (out.relative_to(ROOT), out.stat().st_size, hashlib.md5(out.read_bytes()).hexdigest()))
    if a.no_run:
        sys.exit(0 if ok_all else 1)
    glyphs = font()
    t0 = time.time()
    with NexRun(out) as r:
        running = r.wait_pc_in(0x8000, 0xC000, timeout=20)
        print("program running (PC in 8000h..C000h): %s after %.1f s" % (running, time.time() - t0))
        t1 = time.time()
        done = r.wait_byte(R, 1, timeout=a.timeout)
        t_done = time.time() - t1
        pc = r.pc()
        print("DONE word = 1: %s after %.1f s (PC=%04X)" % (done, t_done, pc))
        blk = r.rd(R, 0x70)
        scr = r.rd(0x4000, 6912)
        turbo = r.q("get-cpu-turbo-speed")
        nr7 = r.nextreg(7)
    if len(scr) == 6912:
        scr_to_png(scr, str(ROOT / a.png))
        print("screen PNG: %s" % a.png)
    check("DONE within %.0f s" % a.timeout, done, "%.1f s" % t_done)
    if not (done and len(blk) == 0x70 and len(scr) == 6912):
        print("RESULT: FAIL (no result block / screen)"); sys.exit(1)
    d = parse_block(blk)
    rows = decode_screen(scr, glyphs)
    print("---- screen (ROM-font decode) ----")
    for i, row in enumerate(rows):
        if row: print("%2d: %s" % (i, row))
    print("---- result block 5F80h ----")
    print("  " + ", ".join("%s=%s" % (k, v) for k, v in d.items() if k != "fills"))
    for f in d["fills"]: print("  %-12s lines %4d us %5d status %d sentinel %02X" % (f["name"], f["lines"], f["us"], f["status"], f["sentinel"]))
    print("  ZEsarUX: nextreg 7 = %s, get-cpu-turbo-speed = %s" % (nr7, turbo))
    print("---- oracles ----")
    # line 2 ids
    m = re.match(r"MACHINE (\d+) CORE (\d+)\.(\d+)\.(\d+) BOARD (\d+)$", rows[2])
    check("line 2 ids printed == block", m and int(m.group(1)) == d["mach"] and int(m.group(2)) == d["core"] >> 4 and int(m.group(3)) == d["core"] & 15 and int(m.group(4)) == d["sub"] and int(m.group(5)) == d["board"], rows[2])
    m = re.match(r"VIDEO +(\d+) LINES TIMING (\d) (50|60)HZ$", rows[3])
    check("line 3 video == block", m and int(m.group(1)) == d["lpf"] and int(m.group(2)) == (d["nr03"] >> 4) & 7 and (m.group(3) == "60") == bool(d["nr05"] & 4), rows[3])
    check("lines per frame 312 (50 Hz) or 262 (60 Hz)", d["lpf"] in (312, 262), "%d" % d["lpf"])
    check("T per line used 224 or 228", d["tline"] in (224, 228), "%d (nextreg 03h = %02Xh)" % (d["tline"], d["nr03"]))
    exp_txt = {0: "ZXNDDMA NOT FOUND", 1: "ZXNDDMA FOUND", 2: "ZXNDDMA FORCED"}[a.expect_found]
    check("line 4 detection == %s and block R_DDMA == %d" % (exp_txt, a.expect_found), rows[4].startswith(exp_txt) and d["ddma"] == a.expect_found, "%r probe_to=%02X page60=%02X marker=%02X" % (rows[4], d["probe_to"], d["probe_pg60"], d["marker"]))
    if a.expect_found == 0:
        check("plain DMA copied the marker into probe_to (DMA present, no zxnDDMA)", d["probe_to"] == d["marker"] and d["probe_pg60"] != d["marker"])
    check("T_CPU / T_MEM in block == tool constants", d["t_cpu"] == T_CPU and d["t_mem"] == T_MEM, "%d %d" % (d["t_cpu"], d["t_mem"]))
    # MHz lines: printed == block, and recomputed from lines
    for row, label, ln, mhz, T in ((5, "CPU LOOP", "cpu_ln", "cpu_mhz", T_CPU), (6, "MEM SRAM", "sram_ln", "sram_mhz", T_MEM), (7, "MEM BLOCKRAM", "blk_ln", "blk_mhz", T_MEM)):
        m = re.match(re.escape(label) + r" +(\d+) LN +(\d+)\.(\d)+ MHZ$", rows[row])
        printed = m and int(m.group(1)) == d[ln] and int(m.group(2)) * 10 + int(m.group(3)) == d[mhz]
        k = round(T * 35 / d["tline"])
        recomputed = d[ln] and (k + d[ln] // 2) // d[ln] == d[mhz]
        check("line %d %s printed == block and MHz x 10 == round(K / lines)" % (row, label), printed and recomputed, "%r (K %d / %d lines = %.2f)" % (rows[row], k, d[ln], d[ln] and k / d[ln]))
        check("line %d %s 25.0 <= MHz <= 29.0" % (row, label), 250 <= d[mhz] <= 290, "%.1f MHz" % (d[mhz] / 10))
    mhz = d["cpu_mhz"] / 10 or 28.0
    for i, f in enumerate(d["fills"]):
        row = 9 + i
        meth, tgt = f["name"].split()
        if f["status"] == 2:
            check("line %d FILL %s SKIPPED" % (row, f["name"]), rows[row] == "FILL %-6s %-4s SKIPPED" % (meth, tgt), repr(rows[row]))
            continue
        m = re.match(r"FILL (\w+) +(\w+) +(\d+) US( BAD)?$", rows[row])
        printed = m and m.group(1) == meth and m.group(2) == tgt and int(m.group(3)) == f["us"] and bool(m.group(4)) == (f["status"] == 1)
        us_rec = f["lines"] * d["tline"] * 2 // 7
        check("line %d FILL %s printed == block (us = lines x %d x 2 / 7)" % (row, f["name"], d["tline"]), printed and us_rec == f["us"], "%r lines %d" % (rows[row], f["lines"]))
        if meth in ("CPU", "LDIR"):
            pred = (T_FILL_CPU if meth == "CPU" else T_FILL_LDIR) / mhz
            check("line %d FILL %s verified and within 20%% of %.0f us predicted at %.1f MHz" % (row, f["name"], pred, mhz), f["status"] == 0 and abs(f["us"] - pred) <= 0.2 * pred, "%d us (%.1f%%)" % (f["us"], (f["us"] - pred) / pred * 100))
        elif meth == "ZXNDMA":
            pred = 12288 * 6 / mhz
            note = "%d us = %.2f clocks/byte at %.1f MHz" % (f["us"], f["us"] * mhz / 12288, mhz)
            if f["us"] == 0: note += " - 0 lines: the emulator completes the DMA transfer instantly; hardware prediction 6 clocks/byte = %.0f us" % pred
            check("line %d FILL %s verified (status 0: first/middle/last byte = A5h)" % (row, f["name"]), f["status"] == 0, note)
        else:
            if a.expect_bad_ddma:
                check("line %d FILL %s ran without hanging and reports BAD (plain DMA ignores DF/F7)" % (row, f["name"]), f["status"] == 1, "%d us" % f["us"])
            else:
                check("line %d FILL %s verified" % (row, f["name"]), f["status"] == 0, "%d us" % f["us"])
        check("line %d FILL %s sentinel F000h untouched (%02X)" % (row, f["name"], 0xA5 ^ 0xFF), f["sentinel"] == (0xA5 ^ 0xFF), "%02X" % f["sentinel"])
    check("line 22 PRESS R TO REPEAT", rows[22] == "PRESS R TO REPEAT", repr(rows[22]))
    check("no unknown glyph on the screen", not any("?" in row for row in rows))
    print("RESULT: %s" % ("PASS" if ok_all else "FAIL"))
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
