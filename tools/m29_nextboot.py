#!/usr/bin/env python3
"""m29_nextboot.py - state-driven NextZXOS boot -> killemall.nex start for headless ZEsarUX TBBlue (ZRCP).
The firmware shows a video-mode test card ("ENTER selects mode") that waits for ENTER, then boots NextZXOS, which shows welcome
pages (SPACE = Start NextZXOS), then the main menu (ENTER = Browser), then the Browser (CAPS+6 x16 = killemall.nex, ENTER).
Timing differs run to run (host load), so each stage is recognised from a `save-screen` BMP signature instead of fixed waits:
  test card  : border green (0,182,0)
  splash     : border black, >85 % black (wait: it boots by itself; SPACE here would open the firmware menu)
  welcome    : border grey, cyan < 0.5 %, black 9-15 %
  main menu  : border grey, black < 7 %
  browser    : border grey, cyan > 2 %
  game       : border black, black 60-90 %, grey < 5 %  (title screen / menu of the game)
boot_to_game(q, tap, log) returns True when the game's own menu is up (PC in 0x8000..0xBFFF)."""
import os, time, re
from PIL import Image

def signature(bmp):
    im = Image.open(bmp).convert("RGB"); w, h = im.size
    bord = im.getpixel((8, 8)); px = list(im.crop((w // 8, h // 8, w * 7 // 8, h * 7 // 8)).get_flattened_data() if hasattr(im, "get_flattened_data") else im.crop((w // 8, h // 8, w * 7 // 8, h * 7 // 8)).getdata())
    n = float(len(px))
    black = sum(1 for p in px if max(p) < 60) / n
    cyan = sum(1 for p in px if p[0] < 80 and p[1] > 150 and p[2] > 150) / n
    grey = sum(1 for p in px if abs(p[0] - p[1]) < 20 and abs(p[1] - p[2]) < 20 and 150 < p[0] < 240) / n
    return bord, black, cyan, grey

def classify(bmp):
    bord, black, cyan, grey = signature(bmp)
    if bord == (0, 182, 0): return "testcard"
    if bord == (0, 0, 0) and black > 0.85: return "splash"
    if bord == (0, 0, 0) and 0.55 < black < 0.95 and grey < 0.05: return "game"
    if bord == (182, 182, 182):
        if cyan > 0.02: return "browser"
        if black < 0.07: return "menu"
        if 0.09 <= black <= 0.15: return "welcome"
    return "unknown(%s %.3f %.3f %.3f)" % (bord, black, cyan, grey)

def boot_to_game(q, tap, pc, log=print, limit=150, bmp="/tmp/nextboot.bmp"):
    """q(cmd, wait) -> ZRCP text; tap(keys, hold, gap); pc() -> int. Returns True when the game runs."""
    t0 = time.time(); last = None; downs_done = False
    while time.time() - t0 < limit:
        if os.path.exists(bmp): os.remove(bmp)
        q("save-screen " + bmp, 0.6)
        st = classify(bmp) if os.path.exists(bmp) else "noshot"
        if st != last: log("  nextboot %5.1fs: %s (PC %04x)" % (time.time() - t0, st, pc())); last = st
        if st == "testcard": tap(("ENTER",), 0.2, 3.0)
        elif st == "splash": time.sleep(2.0)
        elif st == "welcome": tap(("SPACE",), 0.2, 2.5)
        elif st == "menu": tap(("ENTER",), 0.2, 3.0)
        elif st == "browser":
            if not downs_done:
                for _ in range(16): tap(("CAPS", "6"), 0.15, 0.2)
                downs_done = True
            tap(("ENTER",), 0.2, 5.0)
        elif st == "game":
            # the game's title/menu: the engine image is loaded (PC anywhere in 0x8000..0xFFFF or in the ROM ISR at 0x0038)
            v = pc()
            if v >= 0x8000 or v == 0x0038: return True
            time.sleep(1.0)
        else: time.sleep(1.5)
    return False
