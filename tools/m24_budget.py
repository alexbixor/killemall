#!/usr/bin/env python3
"""m24_budget.py - M2.4 byte budget facts (read-only): sizes of the sprite blit routines (symbol deltas), run-list bytes of the
current art, and how many bytes the run lists would shrink if opaque-black ('o') compiled as transparent (the sprite card
makes black == transparent: every cell the sprite touches is cleared to paper first)."""
import re, sys, pathlib
sys.path.insert(0, 'tools')
ROOT = pathlib.Path('.')
sym = {}
for l in open('build/kea48.sym'):
    m = re.match(r'(\S+)\s+EQU\s+0([0-9A-F]+)H', l)
    if m: sym[m.group(1)] = int(m.group(2), 16)
addrs = sorted(set(sym.values()))
def size(n):
    a = sym[n]; return next(x for x in addrs if x > a) - a
def span(a, b): return sym[b] - sym[a]
print("sprites_f: ds_cols..dc_run(data) %d B, dc_attr..dc_run %d B, draw_weapon %d B, draw_sprite..ds_hv %d B" % (
    span('ds_cols', 'dc_run'), span('dc_attr', 'dc_run'), span('draw_weapon', 'dw_col') + size('dw_col') + size('dw_r'), span('draw_sprite', 'ds_hv')))
print("hud_b draw_weapon exact: %04X..%04X" % (sym['draw_weapon'], sym['dw_col']))
for n in ['vis_sort_draw', 'draw_sprite', 'ds_cols', 'dc_l', 'dc_vis', 'dc_run_l', 'dc_next', 'dc_mark', 'dc_attr', 'dc_run', 'ds_cnt', 'TYPEINK', 'THSPR', 'enemy_h', 'mul16', 'hi_end']:
    print("  %-14s %04X" % (n, sym[n]))
import gen48
spr = gen48.parse_sprites()
tot_now = tot_new = 0
for i in range(14):
    h, data = spr[i]
    cols = gen48.runs16(h, data)
    now = sum(len(c) for c in cols)
    # black (code 1) -> transparent (0), merge equal neighbours
    new = 0
    for c in cols:
        codes = []
        for b in c[:-1]:
            v, code = b >> 3, b & 7
            if code == 1: code = 0
            if codes and codes[-1][1] == code: codes[-1] = (v, code)
            else: codes.append((v, code))
        new += len(codes) + 1
    tot_now += now; tot_new += new
    print("spr_%02d h%2d runs now %3d B  ink-only %3d B" % (i, h, now, new))
print("run lists total now %d B, ink-only %d B -> saving %d B" % (tot_now, tot_new, tot_now - tot_new))
print("low block: spr_table %04X SCHAIN %04X level_data %04X start 8000 -> free before 0x8000: %d B" % (sym['spr_table'], sym['SCHAIN'], sym['level_data'], 0x8000 - (sym['level_data'] + 1081)))
print("high block: hi_end %04X, stack top FDF0 -> gap %d B" % (sym['hi_end'], 0xFDF0 - sym['hi_end']))
