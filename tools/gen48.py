#!/usr/bin/env python3
"""gen48.py - generates data tables, pre-shifted textures, unrolled drawing code and the four DDA loop variants for the
48K engine (src/48k/gen/tables48.asm, unrolled48.asm, dda48.asm).  Pasmo syntax, decimal numbers only.

Fixed point (shared with kea48.asm):
  angles 256/turn; positions 8.8 (cell.frac); SINTAB/COSTAB/PLXTAB/PLYTAB/MOVXTAB/MOVYTAB s8.8 words (256 entries each).
  RECIP[i]   word  65536/i clamped 32767  (deltaDist 8.8 for |rayDir| = i/256), 512 entries
  SQLO/SQHI  byte  floor(k*k/4) lo/hi for k=0..511 (squares-table multiply); SQHI = SQLO+512; page aligned
  HTABN[i]   byte  wall height for dist i/64 ; HTABF[i] height for dist i/8 ; even, 2..96, plus the clipped virtual
                   heights of CLIPSET (104..192) for dist < 1; page aligned
  TEXMAP[code] texture page ; CODEINK[code] attribute ink   (M2.2: FPS10TAB removed with the fps counter)
  BANDTAB    word  BANDTAB + h = address of the band routine for wall height h (even, 0..192); page aligned
  TEXPG[code] byte  high byte of the texture page for a cell code (TEX/256 + page)
  SLOTM[p]   byte  bits of ray slot p (p = col and 7) inside its byte: E0 1C 03 F0 0F C0 38 07 (widths 3,3,2,4,4,2,3,3)
  ADJTAB[p]  byte  byte column inside the 24-px group of 8 rays: 0,0,0,1,1,2,2,2
  COLBASE[c] word  BUF + 96*c, c = 0..23 (page-contained, in the padding before HTABN)
  TEX        9 textures, 256 bytes each: byte at TEX + page*256 + u*16 + v = 255 if texel lit else 0.
             The band ANDs the texel with (SLOTM[p] & shade) once per run of rows, so no pre-shifted copies are needed.
Back buffer BUF = 24832 (0x6100): column-major, 24 byte-columns x 96-byte stride, row r of byte column c at
  COLBASE[c] + r = BUF + c*96 + r (M2.5C 192-px window; a column may cross a page -> all row pointers step with inc de).
  Ray column col (0..63, 3 px): bytecol = 3*(col>>3) + ADJTAB[col&7] (0,0,0,1,1,2,2,2), slot bits SLOTM[col&7].
Unrolled code:
  CLRBUF   PUSH-fills the buffer: rows 48-95 the floor dot lattice + distance lines, rows 0-47 the ceiling lattice + the
           mirrored distance lines (alternate set). M2.5E: two fill words per set, alternating per word parity (even word w:
           DE / DE', odd: BC / BC'); floor 0x0100 / 0x1000 (dot on the odd row 49+2w, staggered 4 px = diamonds, 6.25%),
           ceiling 0x0001 / 0x0000 (dot on the even row 46-2w, aligned squares, 3.125%); line words 0xFF00 / 0x00FF.
  ATTR_d   writes the 12 attribute rows of one byte column for a wall whose top row is in attribute row d (0..6).
  COPYBUF  copies the buffer to the screen window (SP pops 2 rows at a time), interrupts stay enabled.
  BAND_h   OR-blits an h-row textured column: HL = texture (H page, L = u*16), DE = buffer address of the top row,
           IXL = SLOTM[p] & shade (shade 255 lit / 170 dark side), C = ~SLOTM[p].  Per run of rows with the same texel:
           B = texel & IXL; every row: byte = (byte & C) | B (M2.5B: the ceiling has dots, so rows above the horizon mask too).
  BANDC_h  clipped band for virtual height h > 96: 96 rows, texture rows centred.
"""
import math, pathlib, os

OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "48k" / "gen"
OUT.mkdir(parents=True, exist_ok=True)
CLIPSET = [int(v) for v in os.environ.get("KEA_CLIPSET", "104,112,128,160,192").split(",")]   # T6 knob: build48.sh drops 160/192 (RAM)

def dw(vals):
    return "\n".join("        defw " + ",".join(str(v) if isinstance(v, str) else str(v & 0xFFFF) for v in vals[i:i + 8])
                     for i in range(0, len(vals), 8))

def db(vals):
    return "\n".join("        defb " + ",".join(str(v) if isinstance(v, str) else str(v & 0xFF) for v in vals[i:i + 16])
                     for i in range(0, len(vals), 16))

def even_height(dist):
    if dist <= 1.0:
        return 96
    h = max(2, min(96, int(96 / dist)))
    return h & ~1 if h > 2 else 2

def wall_height(dist):
    """Even height 2..96, or for dist < 1 the largest CLIPSET virtual height <= 96/dist (96 if none)."""
    if dist > 1.0:
        return even_height(dist)
    hv = 96 / dist if dist > 0 else 1e9
    c = [h for h in CLIPSET if h <= hv]
    return max(c) if c else 96

def scr_addr(y):
    return 0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)

# ---------------- textures (16x16, 1 = lit texel) ----------------
def tex_brick(u, v):
    row = v // 4; off = 4 if row % 2 else 0
    return 0 if (v % 4 == 3 or (u + off) % 8 == 7) else 1
def tex_stone(u, v):
    return 0 if (v % 8 == 0 or u % 16 == 0 or (v > 8 and u == 8) or (u * 7 + v * 3) % 11 == 0) else 1
def tex_metal(u, v):
    rivet = (u in (2, 13) and v in (2, 13))
    return 1 if (rivet or v in (0, 15) or u in (0, 15)) else 0
def tex_tech(u, v):
    return 1 if (v % 4 == 1 or (u % 8 == 3 and v % 4 != 3)) else 0
def tex_moss(u, v):
    return 1 if ((u * 5 + v * 9) % 7 < 2 or (u + v) % 6 == 0) else 0
def tex_vent(u, v):
    return 1 if (v % 2 == 0 and 1 <= u <= 14) or u in (0, 15) else 0
def tex_pipes(u, v):
    return 1 if (u % 4 in (1, 2) and not (u % 4 == 2 and v % 5 == 0)) else 0
def tex_door(u, v):
    frame = u in (0, 15) or v in (0, 15)
    bar = 6 <= u <= 9 and 3 <= v <= 12
    return 1 if (frame or bar or (v == 7 and 2 <= u <= 13)) else 0
def tex_exit(u, v):
    return 1 if (u == v or u == 15 - v or u in (0, 15) or v in (0, 15)) else 0
TEXTURES = [tex_brick, tex_stone, tex_metal, tex_tech, tex_moss, tex_vent, tex_pipes, tex_door, tex_exit]
TEXMAP = [0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 0, 8, 0, 0, 0]

def tex_pages():
    return [255 if f(u, v) else 0 for f in TEXTURES for u in range(16) for v in range(16)]

ALIGN256 = "        defs ((($+255) and 65280) - $)"

def tables():
    tau = 2 * math.pi
    sin = [round(math.sin(tau * a / 256) * 256) for a in range(256)]
    cos = [round(math.cos(tau * a / 256) * 256) for a in range(256)]
    plx = [round(-0.99 * math.sin(tau * a / 256) * 256) for a in range(256)]     # M2.5C: plane 0.99 (192 px, square cells)
    ply = [round(0.99 * math.cos(tau * a / 256) * 256) for a in range(256)]
    movx = [round(0.15 * math.cos(tau * a / 256) * 256) for a in range(256)]
    movy = [round(0.15 * math.sin(tau * a / 256) * 256) for a in range(256)]
    recip = [32767] + [min(32767, round(65536 / i)) for i in range(1, 512)]
    sq = [(k * k) >> 2 for k in range(512)]
    htabn = [wall_height(i / 64) for i in range(256)]
    assert all(cos[a] == sin[(a + 64) & 255] for a in range(256)), "COSTAB alias"
    assert all(plx[a] == ply[(a + 64) & 255] for a in range(256)), "PLXTAB alias"
    assert all(movx[a] == movy[(a + 64) & 255] for a in range(256)), "MOVXTAB alias"
    htabf = [even_height(i / 8) for i in range(256)]
    band_entries = []
    for h in range(0, 194, 2):
        if h == 0: band_entries.append("BAND_NONE")
        elif h <= 96: band_entries.append("BAND_%d" % h)
        elif h in CLIPSET: band_entries.append("BANDC_%d" % h)
        else: band_entries.append("BAND_NONE")
    s = ["; generated by tools/gen48.py - do not edit",
         # M2.5B: cos(a) == sin(a+64) exactly (same rounding), likewise plx/ply and movx/movy -> the x tables are aliases
         # 128 B into the y tables, which carry 64 wrap entries (320 words each). 1,152 B saved for the textured ceiling bands.
         "SINTAB:", dw(sin + sin[:64]), "COSTAB  equ SINTAB+128",
         "PLYTAB:", dw(ply + ply[:64]), "PLXTAB  equ PLYTAB+128",
         "MOVYTAB:", dw(movy + movy[:64]), "MOVXTAB equ MOVYTAB+128",
         "RECIP:", dw(recip),
         '        include "../common/floor.asm"',                    # M2.3: floor lines code+data in the alignment padding
         '        include "../common/blood.asm"',                    # M2.6: ds_inkl + blood 1 red flash, same padding (lowcode.asm is full)
         "        if (($ and 255) > 208)\n        defs 256 - ($ and 255)   ; COLBASE must not cross a page (ld b,COLBASE/256 + inc c)\n        endif",
         "COLBASE:", dw(["BUF+%d" % (96 * c) for c in range(24)]),   # M2.5C: 24 column bases, page-contained BY CONSTRUCTION (see 11.)
         ALIGN256,
         "HTABN:", db(htabn), "HTABF:", db(htabf),
         "SQLO:", db([v & 0xFF for v in sq]), "SQHI:", db([v >> 8 for v in sq]),
         "BANDTAB:", dw(band_entries),                                   # 194 bytes, page aligned (follows SQHI)
         "TEXPG:", db(["TEX/256+%d" % p for p in TEXMAP]),
         "SLOTM:", "        defb 224,28,3,240,15,192,56,7",             # M2.5C: slot bits per col&7 (3,3,2,4,4,2,3,3 px)
         "ADJTAB:", "        defb 0,0,0,1,1,2,2,2",                     # M2.5C: byte column inside the 24-px group
         # M2.5: one ink for the whole window - no CODEINK / ATTRTAB / ATTR_d / ATTRCOPY
         "dsp_tab:", "        defw dda_pp,dda_pn,dda_np,dda_nn",
         '        include "../common/attrfill.asm"',                 # M2.6 blood 3: aw_fill (13 B) in the 22 B padding before TEX
         ALIGN256, "TEX:", db(tex_pages())]
    (OUT / "tables48.asm").write_text("\n".join(s) + "\n")

def band_rows(h):
    """Per-row texture v for a wall h rows high (h <= 96): same mapping as the M1 STEPTAB accumulator."""
    return [((r * (4096 // h)) >> 8) & 15 for r in range(h)]

def clipped_rows(hv):
    top = (hv - 96) // 2
    return [((r * (4096 // hv)) >> 8) & 15 for r in range(top, top + 96)]

def emit_band(label, vs, lower_from):
    """HL = texture column (L = u*16 + v), DE = buffer row pointer, C = floor-slot mask, IXL = shade mask (255 / 170).
    Per run of rows sharing one texel: ld a,(hl) / and ixl / ld b,a ; per row: ld a,(de) / [and c] / or b / ld (de),a / inc e."""
    s = [label + ":"]
    if vs[0]:
        s += ["        ld a,l", "        add a,%d" % vs[0], "        ld l,a"]
    runs = []
    for r, v in enumerate(vs):
        if runs and runs[-1][0] == v:
            runs[-1][2] += 1
        else:
            runs.append([v, r, 1])
    prev_v = vs[0]
    last = len(vs) - 1
    for v, r0, n in runs:
        if v != prev_v:
            d = v - prev_v
            s += ["        inc l"] if d == 1 else ["        ld a,l", "        add a,%d" % d, "        ld l,a"]
            prev_v = v
        s += ["        ld a,(hl)", "        and ixl", "        ld b,a"]
        for r in range(r0, r0 + n):
            s.append("        ld a,(de)")
            s.append("        and c")                      # M2.5B: also above the horizon (ceiling dots under the wall slot)
            s.append("        or b")
            s.append("        ld (de),a")
            if r != last:
                s.append("        inc de")                    # M2.5C: 96-byte stride, columns may cross a page
    s.append("        ret")
    return s

def unrolled():
    s = ["; generated by tools/gen48.py - do not edit"]
    # ---- CLRBUF: PUSH fill, SP walks down from BUF+2304 (24 columns x 96 rows, column 23 first); per column 24 pushes floor
    #      (word 23 = rows 95/94 first ... word 0 = rows 49/48 last; low byte -> even row), then 24 pushes ceiling in the
    #      alternate set (word 0 = rows 46/47 first ... word 23 = rows 0/1).
    # M2.5E: two fill words per set, chosen per word parity: even words push de / de', odd words push bc / bc' (fl_set writes
    #        D5 / C5, or E5 = push hl / hl' for a distance line). Floor DE 0x0100 (dot x=7 on the odd row 49+2w), BC 0x1000
    #        (dot x=3): diamonds. M2.6 D5 ceiling: DE' 0x8041 / BC' 0x2214 / IX 0x0814 / IY 0x2241 by w&3 = a continuous
    #        45-degree X lattice (8 px x 8 rows diamonds); push ix / push iy are 2-byte slots (see common/floor.asm).
    #        Line words are constants: floor HL 0xFF00 (odd row solid), ceiling HL' 0x00FF (even row solid) = the fill word
    #        with its dot row replaced, so the lattice stays continuous. apply_opts patches cl_de+1 / cl_bc+1 / cl_ce+1.
    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2304", "        exx",            # M2.5C: 24 x 96 B
          "cl_ce:  ld de,%d" % 0x8041, "cl_cb:  ld bc,%d" % 0x2214, "cl_cw:  ld hl,%d" % 0x00FF, "        exx",
          "cl_cx:  ld ix,%d" % 0x0814, "cl_cy:  ld iy,%d" % 0x2241,          # M2.6 D5 ceiling: four fill words by w&3
          "cl_de:  ld de,%d" % 0x0100, "cl_bc:  ld bc,%d" % 0x1000,
          "        ld a,24", "cl_col: ld hl,%d" % 0xFF00]        # HL = floor line word; M2.5C: 24 columns, no row gap
    s += ["cl_fl:  push bc"] + ["        push %s" % ("de" if i & 1 else "bc") for i in range(1, 24)]   # push i = word 23-i: odd word -> bc
    s += ["        exx", "cl_cl:  push de"] + ["        push %s" % ("de", "bc", "ix", "iy")[i & 3] for i in range(1, 24)] + ["        exx"]   # M2.6 D5: push i = word i, fill by w&3 (1,1,2,2-byte slots; fl_set patches one byte per word)
    s += ["        dec a", "        jp nz,cl_col", "cl_sp:  ld sp,0", "        ret"]
    # M2.5: ATTR_d / ATTRCOPY removed (one ink for the whole window, set once by cls)
    # ---- COPYBUF: buffer -> screen, one column at a time (48 pops), interrupts stay enabled (ISR pushes land on bytes
    #      already popped, or below BUF at the very start).  C = byte column 0..15, alt HL = buffer column pointer.
    s += ["COPYBUF:", "        ld (cb_sp+1),sp", "        exx", "        ld hl,BUF", "        ld bc,96", "        exx", "        ld c,0",
          "cb_col: exx", "        ld sp,hl", "        add hl,bc", "        exx"]      # M2.5C: HL' = next column (stride 96)
    for r in range(0, 96, 2):
        s.append("        pop de")
        if r % 8 == 0:
            y = 8 + r
            s += ["        ld a,c", "        add a,%d" % (((y & 0x38) << 2) + 4), "        ld l,a",      # M2.5C: screen col 4 + c
                  "        ld h,%d" % (0x40 + ((y & 0xC0) >> 3))]
        else:
            s.append("        inc h")
        s += ["        ld (hl),e", "        inc h", "        ld (hl),d"]
    s += ["        inc c", "        ld a,c", "        cp 24", "        jp c,cb_col", "cb_sp:  ld sp,0", "        ret"]
    # ---- bands
    s.append("BAND_NONE:")
    s.append("        ret")
    for h in range(2, 97, 2):
        s += emit_band("BAND_%d" % h, band_rows(h), h // 2)
    for hv in CLIPSET:
        s += emit_band("BANDC_%d" % hv, clipped_rows(hv), 48)
    (OUT / "unrolled48.asm").write_text("\n".join(s) + "\n")

def dda():
    """HL = sideDistX, DE = sideDistY, BC = deltaDistX, IX = deltaDistY, HL' (alternate set) = map cell pointer.
    Exits: hit_x (A = cell code, HL = perp dist), hit_y (same), hit_far.
    Compared with M1: the comparison is a 16-bit 'sbc' (ld a,l / sub e / ld a,h / sbc a,d = 16 T, no branches) instead of a
    3-branch byte compare; the Y side distance lives in DE and the map row step uses the pre-split 'ld a,iyl/add/ld iyl,a'
    only when needed.  Same step order (X when sideX < sideY, Y otherwise), same overflow and exit semantics."""
    s = ["; generated by tools/gen48.py - do not edit"]
    for sx in (1, -1):
        for sy in (1, -1):
            v = ("p" if sx > 0 else "n") + ("p" if sy > 0 else "n")
            L = lambda t: "%s_%s" % (t, v)
            s += ["dda_%s:" % v,
                  L("dl") + ":",
                  "        ld a,l", "        sub e", "        ld a,h", "        sbc a,d", "        jr nc," + L("ys"),
                  L("xs") + ":",
                  "        add hl,bc", "        jr c," + L("xi"),
                  "        exx",
                  "        inc hl" if sx > 0 else "        dec hl",
                  "        ld a,(hl)", "        exx", "        or a", "        jr z," + L("dl"),
                  "        sbc hl,bc",
                  "        jp hit_x",
                  L("ys") + ":",
                  "        ld a,e", "        add a,ixl", "        ld e,a", "        ld a,d", "        adc a,ixh", "        ld d,a",
                  "        jr c," + L("yi"),
                  "        exx",
                  "        ld a,l",
                  "        add a,32" if sy > 0 else "        sub 32",
                  "        ld l,a",
                  "        jr nc," + L("yk"),
                  "        inc h" if sy > 0 else "        dec h",
                  L("yk") + ":",
                  "        ld a,(hl)", "        exx", "        or a", "        jr z," + L("dl"),
                  "        ld c,a", "        ex de,hl",
                  "        ld a,l", "        sub ixl", "        ld l,a", "        ld a,h", "        sbc a,ixh", "        ld h,a",
                  "        ld a,c",
                  "        jp hit_y",
                  L("xi") + ":",
                  "        ld hl,65535", "        ld a,d", "        and e", "        inc a", "        jr nz," + L("dl"), "        jp hit_far",
                  L("yi") + ":",
                  "        ld de,65535", "        ld a,h", "        and l", "        inc a", "        jr nz," + L("dl"), "        jp hit_far"]
    (OUT / "dda48.asm").write_text("\n".join(s) + "\n")

# ---------------------------------------------------------------- T1: sprites (consumes T5 src/gen/sprites_data.asm)
SPRSRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "gen" / "sprites_data.asm"

def parse_sprites():
    """T5 format: spr_NN: label, db H, then W/8 byte-columns x (H mask bytes, H pixel bytes). Returns {id: (H, bytes)}."""
    out, cur, acc = {}, None, []
    for line in SPRSRC.read_text().splitlines():
        t = line.split(";")[0].strip()
        if t.startswith("spr_") and t[4:6].isdigit() and ":" in t:
            if cur is not None: out[cur] = (acc[0], bytes(acc[1:]))
            cur, acc = int(t[4:6]), []
        elif cur is not None and (t.startswith("db ") or t.startswith("defb ")):
            for v in t.split(None, 1)[1].split(","):
                v = v.strip()
                if v: acc.append(int(v[1:], 16) if v.startswith("$") else int(v))
    if cur is not None: out[cur] = (acc[0], bytes(acc[1:]))
    return out

def runs16(h, data, box=24, halo_on=True):
    """16-px sprite -> 16 column run lists. Each run byte = (v_end << 3) | code, code 0 transparent, 1 black, 3 white;
    v_end = source row (0..24) where the run ends; list ends with 0. Art is bottom-aligned in the 24-row box."""
    cols = []
    # M2.5 halo: every transparent pixel with an ink pixel among its 8 neighbours (inside the 16 x box) becomes black, so a
    # white figure keeps a 1-px dark outline on a white wall (TTT-style masked sprite; one ink for the whole window).
    def ink_at(u, v):
        if not halo_on or not (0 <= u < 16 and box - h <= v < box): return 0
        return (data[(u >> 3) * 2 * h + h + (v - (box - h))] >> (7 - (u & 7))) & 1
    halo = [[any(ink_at(u + du, v + dv) for du in (-1, 0, 1) for dv in (-1, 0, 1) if du or dv) for u in range(16)]
            for v in range(box)]
    for u in range(16):
        bc, bit = u >> 3, 7 - (u & 7)
        m = [1] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h: bc * 2 * h + h]]
        p = [0] * (box - h) + [(b >> bit) & 1 for b in data[bc * 2 * h + h: bc * 2 * h + 2 * h]]
        codes = [0 if (m[v] and not halo[v][u]) else (3 if p[v] else 1) for v in range(box)]   # M2.5 halo
        out, v = [], 0
        while v < box:
            e = v
            while e < box and codes[e] == codes[v]: e += 1
            out.append((e << 3) | codes[v]); v = e
        cols.append(out + [0])
    return cols

def sprites48():
    """gen/sprites48.asm: spr_table (ids 0..17); ids 0..13 = 16 column offsets (words) + run lists; weapons 14..17 verbatim
    (db 24 + data); SCHAIN (96 x ld a,(de)/and c/or b/ld (de),a/inc e + ret); page SPG: ROWTAB (25 words, RAM) then
    CHJ[n] = SCHAIN_END - 5n (n 0..96); NCTAB[hcol] = columns (hcol/3); STEPTAB[nc] = u step 8.8; VSTEP[hv/2] = hv*256/24."""
    if not SPRSRC.exists():
        spr = {i: (24, bytes([0xFF] * 24 + [0xAA, 0x55] * 12) * 2) for i in range(14)}        # placeholder boxes
        spr.update({i: (24, bytes([0] * 96) * 2) for i in range(14, 18)})
    else:
        spr = parse_sprites()
    nctab = [max(1, min(28, round(2 * hc / 9))) if hc else 0 for hc in range(129)]   # M2.5C: 3 px per ray column -> nc = 16*hc/24/3
    steptab = [0] + [min(65535, round(16 * 256 / nc)) for nc in range(1, 29)]       # nc <= 28 (hv cap 128)
    vstep = [round(hv * 256 / 24) for hv in range(0, 130, 2)]
    s = ["; generated by tools/gen48.py (T1) from src/gen/sprites_data.asm - do not edit",
         "        org 27648              ; M2.5C: dashboard data page 0x6C00 (0x6CB5..0x6CFF = ISR landing of the FTY build)",
         '        include "../common/dash_data.asm"      ; M2.2 dashboard data (tools/m22_pixdata.py)',
         "        org 28416              ; M2.5C: low block 0x6F00..0x7FFF: page tables, sprite data, SCHAIN and the level",
         # M2.5C: CHJ (SCHAIN_END - 5n) is RAM at 0x6000 now, built by init_game (kea48.asm); SPG label dropped
         "NCTAB:", db(nctab), "STEPTAB:", dw(steptab), "VSTEP:", dw(vstep),
         "spr_table:",
         "        defw " + ",".join("spr_%d" % i for i in range(18))]
    for i in range(14):
        h, data = spr.get(i, (24, bytes(96)))
        cols = runs16(h, data, halo_on=i < 8)          # M2.5: halo for the enemies; items (8..13) carry their own black
        s += ["spr_%d:" % i, "        defw " + ",".join("spr_%d_u%d" % (i, u) for u in range(16))]
        for u in range(16):
            s += ["spr_%d_u%d:" % (i, u), db(cols[u])]
    for i in range(14, 16):                      # M2.4: ids 16/17 (shotgun) are not drawn by any code path (hud_b: 14 + frame 0/1):
        h, data = spr.get(i, (24, bytes(192)))   # their 386 B make room for sprites_e.asm in the low block
        s += ["spr_%d:" % i, "        defb %d" % h, db(list(data))]
    s += ["spr_16  equ spr_14", "spr_17  equ spr_15"]
    s += ["SCHAIN:"] + ["        ld a,(de)", "        and c", "        or b", "        ld (de),a", "        inc de"] * 96   # M2.5C: inc de
    s += ["SCHAIN_END:", "        ret"]                 # M2.5: sprites_e.asm back in the high block (halo run lists need the room)
    (OUT / "sprites48.asm").write_text("\n".join(s) + "\n")

if __name__ == "__main__":
    tables(); unrolled(); dda(); sprites48()
    print("wrote", OUT)
