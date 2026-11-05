#!/usr/bin/env python3
"""m30_bench_gen.py - M3 option-A benchmark for the Spectrum Next (4 Nov 2026).
Generates build/m30_bench.asm (Z80N via db, pasmo) + build/m30_bench_bank0.bin (textures, 16 KB for 0xC000..0xFFFF).
The program switches the Next to 28 MHz and the LoRes layer (128x96, one byte = one of 256 colours, no attribute
cells), programs an RRRGGGBB palette, installs an IM2 50 Hz tick counter (private stack: the floor drawer keeps SP in
screen memory), then times four drawing tests of 100 frames each (result = 50 Hz ticks, at res_t1..res_t4):
  T1 walls   : 128 textured wall columns, full height = 12,288 texels (32x32 textures, 3 shade levels)
  T2 floorhi : textured floor + ceiling, every pixel its own texel (16x16 textures, 3 shades), 96 rows x 128 px
  T3 floorlo : same but one texel per 2 px (half horizontal texture resolution)
  T4 scene   : floor/ceiling (hi, full screen) + the corridor scene's wall columns over it = a real frame with overdraw
Wall column drawer: HL = texture v (8.8, +32*256 for the odd texture column), BC = dv, D = texture page, IX -> screen
(rows 2k/2k+1 = (ix-128)/(ix+0), inc ixh per pair), 48 unrolled pairs, entered at the first row, exit via a RET patched
at the row after the last. Floor drawer: HL = x (8.8: u = top nibble of L), DE = y (4.12: v = low nibble of D),
texel index = (L and F0h) or (D and 0Fh) -> textures stored transposed (u*16+v), B = page, pixels written two at a time
with PUSH (SP = row end), dx/dy immediates (Z80N add hl,nn / add de,nn) patched per row."""
import math, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 128, 96
F = 96.0                    # focal length in pixels: a wall at distance 1 is 96 rows tall; half-width 64 -> FOV 67 deg
TEXBASE = 0xC000            # 3 shades x 16 pages (2 texture columns of 32 rows per 256-byte page) = 12 KB
FLOORTEX = 0xF000           # 3 shades x 256 B floor, then 3 x 256 B ceiling = 0xF000..0xF5FF
MAP = ["########",
       "#......#",
       "#.##...#",
       "#......#",
       "#...#..#",
       "#......#",
       "#......#",
       "########"]
PX, PY = 1.5, 3.5           # player, looking east (+x)
DIRX, DIRY = 1.0, 0.0
PLX, PLY = 0.0, 64.0 / F    # camera plane half-vector

def rgb332(r, g, b):
    r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
    return ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)

def shade(c, s):            # s = 0 bright, 1 mid, 2 dark
    k = (1.0, 0.68, 0.42)[s]
    return tuple(int(v * k) for v in c)

def wall_tex():             # 32x32 bricks, tex[v][u]
    t = [[(0, 0, 0)] * 32 for _ in range(32)]
    for v in range(32):
        for u in range(32):
            row = v // 8; off = (row % 2) * 4
            mortar = (v % 8 == 7) or ((u + off) % 16 == 15)
            if mortar: c = (150, 140, 120)
            else:
                n = ((u * 7 + v * 13) % 11) - 5
                c = (165 + n * 4, 70 + n * 3, 50 + n * 2)
                if (u + off) % 16 in (0, 1) or v % 8 == 0: c = (c[0] + 20, c[1] + 12, c[2] + 8)
            t[v][u] = c
    return t

def floor_tex():            # 16x16 grey flagstones
    t = [[(0, 0, 0)] * 16 for _ in range(16)]
    for v in range(16):
        for u in range(16):
            edge = (u % 8 == 0) or (v % 8 == 0)
            n = ((u * 5 + v * 3) % 7) - 3
            t[v][u] = (60, 60, 70) if edge else (120 + n * 6, 115 + n * 6, 110 + n * 5)
    return t

def ceil_tex():             # 16x16 blue-grey diamond pattern with lines
    t = [[(0, 0, 0)] * 16 for _ in range(16)]
    for v in range(16):
        for u in range(16):
            d = abs(u - 7.5) + abs(v - 7.5)
            line = abs(d - 7.5) < 0.6 or abs(d - 3.5) < 0.6
            t[v][u] = (90, 110, 160) if line else (40 + int(d) * 3, 45 + int(d) * 3, 70 + int(d) * 4)
    return t

def bank0():
    b = bytearray(16384)
    wt, ft, ct = wall_tex(), floor_tex(), ceil_tex()
    for s in range(3):
        for u in range(32):
            page = s * 16 + u // 2; half = (u & 1) * 32
            for v in range(32):
                b[page * 256 + half + v] = rgb332(*shade(wt[v][u], s))
    for s in range(3):
        for v in range(16):
            for u in range(16):
                b[FLOORTEX - 0xC000 + s * 256 + u * 16 + v] = rgb332(*shade(ft[v][u], s))
                b[FLOORTEX - 0xC000 + 768 + s * 256 + u * 16 + v] = rgb332(*shade(ct[v][u], s))
    return bytes(b)

def row_addr(r):
    return 0x4000 + r * 128 if r < 48 else 0x6000 + (r - 48) * 128

def cast(col):
    cam = 2.0 * (col + 0.5) / W - 1.0
    rx, ry = DIRX + PLX * cam, DIRY + PLY * cam
    mx, my = int(PX), int(PY)
    ddx = abs(1.0 / rx) if rx else 1e30; ddy = abs(1.0 / ry) if ry else 1e30
    sx = -1 if rx < 0 else 1; sy = -1 if ry < 0 else 1
    sdx = (PX - mx) * ddx if rx < 0 else (mx + 1.0 - PX) * ddx
    sdy = (PY - my) * ddy if ry < 0 else (my + 1.0 - PY) * ddy
    while True:
        if sdx < sdy: sdx += ddx; mx += sx; side = 0
        else: sdy += ddy; my += sy; side = 1
        if MAP[my][mx] == "#": break
    d = max((sdx - ddx) if side == 0 else (sdy - ddy), 0.05)
    hit = (PY + d * ry) if side == 0 else (PX + d * rx)
    return d, side, hit - math.floor(hit)

def column_record(col, d, side, u):
    h = F / d
    s = 0 if d < 1.3 else (1 if d < 2.6 else 2)
    if side == 1: s = min(2, s + 1)
    tc = min(31, int(u * 32))
    top = 48.0 - h / 2.0
    start = max(0, int(math.ceil(top - 0.5 - 1e-9)))
    end = min(95, int(math.ceil(top + h - 0.5 - 1e-9)) - 1)
    if end < start: end = start
    count = end - start + 1
    dv = 32.0 / h
    v_first = (start + 0.5 - top) * dv
    dvi = max(1, int(round(dv * 256)))
    v0 = max(0, int(round(v_first * 256)))
    while v0 + (count - 1) * dvi > 32 * 256 - 1 and dvi > 1: dvi -= 1
    if v0 + (count - 1) * dvi > 32 * 256 - 1: v0 = max(0, 32 * 256 - 1 - (count - 1) * dvi)
    page = (TEXBASE >> 8) + s * 16 + tc // 2
    hl = (v0 + (tc & 1) * 32 * 256 - dvi) & 0xFFFF      # the drawer adds dv before the first fetch
    ix = row_addr(start + 1 if start % 2 == 0 else start) + col
    return col, start, count, page, hl, dvi, ix

def scene_columns():
    return [column_record(c, *cast(c)) for c in range(W)]

def full_columns():
    return [column_record(c, 1.0, 0, (c % 32) / 32.0 + 0.001) for c in range(W)]

def floor_rows(lo):
    rows = []
    for r in range(H):
        if r >= 48: rd = (0.5 * F) / (r + 0.5 - 48.0); tex = FLOORTEX
        else: rd = (0.5 * F) / (47.5 - r); tex = FLOORTEX + 768
        s = 0 if rd < 1.6 else (1 if rd < 3.2 else 2)
        page = (tex >> 8) + s
        def point(col):
            cam = 2.0 * (col + 0.5) / W - 1.0
            return PX + rd * (DIRX + PLX * cam), PY + rd * (DIRY + PLY * cam)
        x1, y1 = point(127); x0, y0 = point(126)
        dxp, dyp = x0 - x1, y0 - y1                    # per pixel, going left (push writes downwards)
        step = 2 if lo else 1
        sx, sy = x1 - dxp * step, y1 - dyp * step      # the drawer adds dx/dy before the first fetch
        X0 = int(round(sx * 256)) & 0xFFFF; Y0 = int(round(sy * 4096)) & 0xFFFF
        DX = int(round(dxp * step * 256)) & 0xFFFF; DY = int(round(dyp * step * 4096)) & 0xFFFF
        rows.append((row_addr(r) + 128, X0, Y0, DX, DY, page))
    return rows

def asm():
    L = []; A = L.append
    A("; m30_bench.asm - generated by tools/m30_bench_gen.py (M3 option-A benchmark, Spectrum Next, LoRes 128x96x256)")
    A("        org 8000h")
    A("start:  di")
    A("        ld sp,0BFF0h")
    A("        db 0EDh,091h,07h,03h      ; nextreg 7,3     CPU 28 MHz")
    A("        db 0EDh,091h,15h,80h      ; nextreg 15h,80h LoRes layer on (128x96, 8 bpp), sprites off")
    A("        db 0EDh,091h,43h,00h      ; nextreg 43h,0   ULA first palette, auto-increment on")
    A("        db 0EDh,091h,40h,00h      ; nextreg 40h,0   palette index 0")
    A("        xor a")
    A("pal:    db 0EDh,092h,41h          ; nextreg 41h,a   colour = index (RRRGGGBB)")
    A("        inc a")
    A("        jr nz,pal")
    A("        ld hl,0FE00h")
    A("        ld (hl),0FDh")
    A("        ld de,0FE01h")
    A("        ld bc,256")
    A("        ldir")
    A("        ld a,0C3h")
    A("        ld (0FDFDh),a")
    A("        ld hl,isr")
    A("        ld (0FDFEh),hl")
    A("        ld a,0FEh")
    A("        ld i,a")
    A("        im 2")
    A("        ei")
    A("        halt")
    A("        halt")
    A("        call bench_cpu")
    A("        ld (res_t0),hl")
    A("        ld hl,4000h")
    A("        call bench_fill")
    A("        ld (res_t5),hl")
    A("        ld hl,0A000h")
    A("        call bench_fill")
    A("        ld (res_t6),hl")
    A("        ld iy,cols_full")
    A("        call bench_cols")
    A("        ld (res_t1),hl")
    A("        call pause")
    A("        ld iy,rows_hi")
    A("        ld hl,draw_rows_hi")
    A("        call bench_rows")
    A("        ld (res_t2),hl")
    A("        call pause")
    A("        ld iy,rows_lo")
    A("        ld hl,draw_rows_lo")
    A("        call bench_rows")
    A("        ld (res_t3),hl")
    A("        call pause")
    A("        call bench_scene")
    A("        ld (res_t4),hl")
    A("        ld a,1")
    A("        ld (bench_done),a")
    A("stop:   halt")
    A("        jr stop")
    A("pause:  ld b,250                 ; 5 s so the runner can grab a clean picture of each test")
    A("        call pz2")
    A("        ld b,150")
    A("pz2:")
    A("pz:     halt")
    A("        djnz pz")
    A("        ret")
    A("isr:    ld (isr_sp),sp")
    A("        ld sp,isr_stk")
    A("        push hl")
    A("        ld hl,(ticks)")
    A("        inc hl")
    A("        ld (ticks),hl")
    A("        pop hl")
    A("        ld sp,(isr_sp)")
    A("        ei")
    A("        reti")
    for name, drawer in (("bench_cols", "draw_cols"), ("bench_rows", None), ("bench_scene", None)):
        A("%s:" % name)
        if name == "bench_rows": A("        ld (br_call+1),hl")
        A("        ld hl,(ticks)")
        A("        ld (t0),hl")
        A("        ld a,100")
        A("        ld (fcount),a")
        A("%s_f:" % name)
        if name == "bench_cols":
            A("        push iy"); A("        call draw_cols"); A("        pop iy")
        elif name == "bench_rows":
            A("        push iy"); A("br_call: call 0"); A("        pop iy")
        else:
            A("        ld iy,rows_hi"); A("        call draw_rows_hi"); A("        ld iy,cols_scene"); A("        call draw_cols")
        A("        ld hl,(frames)")
        A("        inc hl")
        A("        ld (frames),hl")
        A("        ld a,(fcount)")
        A("        dec a")
        A("        ld (fcount),a")
        A("        jp nz,%s_f" % name)
        A("        ld hl,(ticks)")
        A("        ld de,(t0)")
        A("        or a")
        A("        sbc hl,de")
        A("        ret")
    A("bench_cpu:                        ; 10 x 65536 iterations x 28 T = 18.35 M T-states = 32.8 ticks at 28 MHz (559,104 T per 50 Hz frame)")
    A("        ld hl,(ticks)")
    A("        ld (t0),hl")
    A("        ld a,10")
    A("        ld (fcount),a")
    A("bcpu1:  ld bc,0")
    A("bcpu2:  dec bc                    ; 16-bit dec sets no flags: test b|c explicitly")
    A("        ld d,b")
    A("        ld a,b")
    A("        or c")
    A("        jp nz,bcpu2               ; 6+4+4+4+10 = 28 T per iteration x 655360 = 18.35 M T = 32.8 ticks at 28 MHz")
    A("        ld hl,fcount")
    A("        dec (hl)")
    A("        jp nz,bcpu1")
    A("        ld hl,(ticks)")
    A("        ld de,(t0)")
    A("        or a")
    A("        sbc hl,de")
    A("        ret")
    A("bench_fill:                       ; HL = base; 100 x 6144 byte writes (ld (hl),a / inc hl = 13 T) = 8.0 M T = 14.3 ticks at 28 MHz")
    A("        ld (bf_base),hl")
    A("        ld hl,(ticks)")
    A("        ld (t0),hl")
    A("        ld a,100")
    A("bf1:    ex af,af'")
    A("        ld hl,(bf_base)")
    A("        ld b,48")
    A("bf2:")
    for _ in range(128):
        A("        ld (hl),a")
        A("        inc hl")
    A("        dec b")
    A("        jp nz,bf2")
    A("        ex af,af'")
    A("        dec a")
    A("        jp nz,bf1")
    A("        ld hl,(ticks)")
    A("        ld de,(t0)")
    A("        or a")
    A("        sbc hl,de")
    A("        ret")
    A("draw_cols:")
    A("        ld b,128")
    A("dc_col: push bc")
    A("        ld l,(iy+2)")
    A("        ld h,(iy+3)")
    A("        ld a,(hl)")
    A("        ld (dc_orig),a")
    A("        ld (dc_patch),hl")
    A("        ld (hl),0C9h")
    A("        ld l,(iy+0)")
    A("        ld h,(iy+1)")
    A("        ld (dc_call+1),hl")
    A("        ld l,(iy+4)")
    A("        ld h,(iy+5)")
    A("        push hl")
    A("        pop ix")
    A("        ld d,(iy+6)")
    A("        ld l,(iy+7)")
    A("        ld h,(iy+8)")
    A("        ld c,(iy+9)")
    A("        ld b,(iy+10)")
    A("dc_call: call 0")
    A("        ld hl,(dc_patch)")
    A("        ld a,(dc_orig)")
    A("        ld (hl),a")
    A("        ld bc,11")
    A("        add iy,bc")
    A("        pop bc")
    A("        djnz dc_col")
    A("        ret")
    for name, lo in (("hi", False), ("lo", True)):
        A("draw_rows_%s:" % name)
        A("        ld c,96")
        A("dr%s_row:" % name)
        A("        push bc")
        A("        push iy")
        A("        ld (br_sp),sp")
        A("        ld c,(iy+6)")
        A("        ld b,(iy+7)")
        A("        ld e,(iy+8)")
        A("        ld d,(iy+9)")
        for k in range(4):
            for sub in (("",) if lo else ("a", "b")):
                A("        ld (fx%s%d%s+2),bc" % (name, k, sub)); A("        ld (fy%s%d%s+2),de" % (name, k, sub))
        A("        ld a,(iy+10)")
        A("        ld ixh,a")
        A("        ld ixl,16")
        A("        ld l,(iy+0)")
        A("        ld h,(iy+1)")
        A("        ld sp,hl")
        A("        ld l,(iy+2)")
        A("        ld h,(iy+3)")
        A("        ld e,(iy+4)")
        A("        ld d,(iy+5)")
        A("        ld b,ixh")
        A("dr%s_loop:" % name)
        for k in range(4):
            if lo:
                A("fx%s%d: db 0EDh,034h,0,0        ; add hl,nn (dx)" % (name, k))
                A("fy%s%d: db 0EDh,035h,0,0        ; add de,nn (dy)" % (name, k))
                A("        ld a,l"); A("        xor d"); A("        and 0F0h"); A("        xor d")
                A("        ld c,a"); A("        ld a,(bc)")
                A("        ld c,a"); A("        ld b,a"); A("        push bc"); A("        ld b,ixh")
            else:
                A("fx%s%da: db 0EDh,034h,0,0" % (name, k))
                A("fy%s%da: db 0EDh,035h,0,0" % (name, k))
                A("        ld a,l"); A("        xor d"); A("        and 0F0h"); A("        xor d")
                A("        ld c,a"); A("        ld a,(bc)"); A("        ex af,af'")
                A("fx%s%db: db 0EDh,034h,0,0" % (name, k))
                A("fy%s%db: db 0EDh,035h,0,0" % (name, k))
                A("        ld a,l"); A("        xor d"); A("        and 0F0h"); A("        xor d")
                A("        ld c,a"); A("        ld a,(bc)")
                A("        ld c,a"); A("        ex af,af'"); A("        ld b,a"); A("        push bc"); A("        ld b,ixh")
        A("        dec ixl")
        A("        jp nz,dr%s_loop" % name)
        A("        ld sp,(br_sp)")
        A("        pop iy")
        A("        ld bc,11")
        A("        add iy,bc")
        A("        pop bc")
        A("        dec c")
        A("        jp nz,dr%s_row" % name)
        A("        ret")
    for k in range(48):
        if k == 24:
            A("wr48:   push de")
            A("        ld de,0800h")
            A("        add ix,de")
            A("        pop de")
            A("wr48b:  add hl,bc")
        else:
            A("wr%d:   add hl,bc" % (2 * k))
        A("        ld e,h"); A("        ld a,(de)"); A("        ld (ix-128),a")
        A("wr%d:   add hl,bc" % (2 * k + 1))
        A("        ld e,h"); A("        ld a,(de)"); A("        ld (ix+0),a"); A("        inc ixh")
    A("wr96:   ret")
    def coltab(label, recs):
        A("%s:" % label)
        for (col, start, count, page, hl, dvi, ix) in recs:
            end = start + count
            entry = "wr%d" % start if start != 48 else "wr48b"
            A("        dw %s,wr%d,%d" % (entry, end, ix))
            A("        db %d" % page)
            A("        dw %d,%d" % (hl, dvi))
    coltab("cols_full", full_columns())
    coltab("cols_scene", scene_columns())
    for name, lo in (("rows_hi", False), ("rows_lo", True)):
        A("%s:" % name)
        for (sp, X0, Y0, DX, DY, page) in floor_rows(lo):
            A("        dw %d,%d,%d,%d,%d" % (sp, X0, Y0, DX, DY))
            A("        db %d" % page)
    A("ticks:  dw 0")
    A("frames: dw 0")
    A("t0:     dw 0")
    A("fcount: db 0")
    A("dc_orig: db 0")
    A("dc_patch: dw 0")
    A("br_sp:  dw 0")
    A("isr_sp: dw 0")
    A("res_t1: dw 0")
    A("res_t2: dw 0")
    A("res_t3: dw 0")
    A("res_t4: dw 0")
    A("res_t0: dw 0")
    A("res_t5: dw 0")
    A("res_t6: dw 0")
    A("bf_base: dw 0")
    A("bench_done: db 0")
    A("        ds 32")
    A("isr_stk:")
    A("code_end:")
    return "\n".join(L) + "\n"

def main():
    (ROOT / "build/m30_bench.asm").write_text(asm())
    (ROOT / "build/m30_bench_bank0.bin").write_bytes(bank0())
    sc = scene_columns()
    print("scene columns: start %d..%d count %d..%d pages %d..%d" % (min(r[1] for r in sc), max(r[1] for r in sc),
          min(r[2] for r in sc), max(r[2] for r in sc), min(r[3] for r in sc), max(r[3] for r in sc)))
    print("wrote build/m30_bench.asm (%d lines) and build/m30_bench_bank0.bin (16384 B)" % asm().count("\n"))

if __name__ == "__main__":
    main()
