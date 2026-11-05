#!/usr/bin/env python3
"""t6_bpprobe.py - probe ZEsarUX breakpoint handling over ZRCP with the normal autoload: connect, enable breakpoints,
set PC=8000H, poll PC and the screen. usage: t6_bpprobe.py tap"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import t6_zes
tap = str(pathlib.Path(sys.argv[1]).resolve())
z = t6_zes.Zes(tap, port=10153)
t_conn = time.time()
print("pc after connect: %04X" % z.pc())
print("enable:", z.cmd("enable-breakpoints", 0.2).strip()[:80])
print("set:", z.cmd("set-breakpoint 1 PC=8000H", 0.2).strip()[:80])
print("bps:", z.cmd("get-breakpoints", 0.2).strip().replace("\n", " | ")[:60])
title = pathlib.Path("build/title.scr").read_bytes()
t0 = time.time(); hit = False; seen = []
while time.time() - t0 < 30:
    pc = z.pc(); seen.append("%04X" % pc)
    if pc == 0x8000:
        hit = True; break
    time.sleep(0.1)
print("hit %s after %.1f s, pc %04X; pcs seen: %s" % (hit, time.time() - t0, z.pc(), " ".join(seen[:40])))
scr = z.grab()
print("screen == title: pix %s attr %s" % (scr[:6144] == title[:6144], scr[6144:] == title[6144:]))
print("regs:", z.cmd("get-registers", 0.3).strip()[:100])
r = z.cmd("exit-cpu-step", 0.3); time.sleep(1.5)
print("after exit-cpu-step pc %04X" % z.pc())
z.close()
