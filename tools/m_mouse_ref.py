#!/usr/bin/env python3
"""m_mouse_ref.py (lane M, 5 Nov 2026) - Python reference of input.asm mouse_look (the mouse look mapping).
State: angle (8-bit, 256 units = 360 deg), frac (8-bit, 1/256 angle units), last (8-bit, X counter at the previous frame),
btn (click latch, action bits b4 fire / b5 use). Inputs: x = Kempston mouse X counter (port 0FBDFh), buttons = port 0FADFh byte
(active low: b0 RIGHT, b1 LEFT), oang (GLIDE builds: the step-start angle, turned by the same amount).
    dx = (x - last) as signed 8-bit; (angle:frac) += dx * 2^MSHIFT as a 16-bit value (MSHIFT 6 -> 1/4 unit per count,
    1024 counts per full turn); last = x; btn |= 0x10 if left down, 0x20 if right down.
import: from m_mouse_ref import mouse_look_ref, MSHIFT"""
MSHIFT = 6

def s8(v):
    v &= 0xFF
    return v - 256 if v >= 128 else v

def mouse_look_ref(angle, frac, last, btn, x, buttons, oang=0, opt_mouse=1):
    """-> (angle, frac, last, btn, oang) after one call of mouse_look"""
    if opt_mouse == 0:
        return angle & 0xFF, frac & 0xFF, last & 0xFF, btn & 0xFF, oang & 0xFF
    dx = s8(x - last)
    acc = (angle << 8 | frac) + dx * (1 << MSHIFT)      # (angle:frac) + dx * 2^MSHIFT, 16-bit wrap
    acc &= 0xFFFF
    turn = ((acc >> 8) - angle) & 0xFF                   # whole units actually turned (for oang)
    nb = btn
    if not (buttons & 0x02): nb |= 0x10                  # b1 low = LEFT button down -> fire
    if not (buttons & 0x01): nb |= 0x20                  # b0 low = RIGHT button down -> use/open
    return acc >> 8, acc & 0xFF, x & 0xFF, nb & 0xFF, (oang + turn) & 0xFF

if __name__ == "__main__":
    # a few hand-checkable cases
    for case in ((0, 0, 0, 0, 4, 0xFF), (0, 0, 0x7F, 0, 0x80, 0xFF), (10, 0, 0xFF, 0, 0x00, 0xFF), (10, 0xC0, 0, 0, 1, 0xFD),
                 (0, 0, 0, 0, 0xFC, 0xFE), (100, 0x80, 0x10, 0, 0x10, 0xFC)):
        print(case, "->", mouse_look_ref(*case))
