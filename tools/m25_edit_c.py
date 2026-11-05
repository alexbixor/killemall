#!/usr/bin/env python3
"""m25_edit_c.py - M2.5 step C: 192-px window (user 31 Oct: "Start making the version with the bigger window"). Idempotent edits.

Design (build/m25_notes.md 31 Oct 21:0xZ):
 - 3D window 192 x 96 px at x 32..223 (screen byte columns 4..27, attribute rows 1..12); frame at x 31 / x 224 (cols 3 / 28).
 - still 64 rays, drawn 3 px wide with byte-rounded widths [3,3,2,4,4,2,3,3] per 24-px group:
     bytecol = 3*(col>>3) + ADJTAB[col&7], ADJTAB = 0,0,0,1,1,2,2,2 ; SLOTM[col&7] = E0 1C 03 F0 0F C0 38 07.
   zbuf, the vis list, hitscan (centre ray 32) and the sprite column loop are untouched.
 - plane 0.66 -> 0.99: a cell at distance 1 stays 96 rows x 97 px (square), FOV 67 -> 89 degrees.
 - back buffer BUF: 24 byte columns x 96-byte stride (2,304 B) at 0x6100..0x69FF; row pointers are 16-bit (inc de) because
   a column may cross a page. COLBASE[bytecol] = BUF + 96*bytecol (24 words, in the padding before HTABN).
 - RAM map (low 32K): 0x6000 CHJ (194 B, RAM, built by init_game) | 0x60C2..0x60FF ISR landing below BUF (fixes the latent
   SOLIDPG corruption when an interrupt hits the last push of CLRBUF) | BUF 0x6100 | FTX 0x6A00 | 0x6C00 dash_data (181 B) +
   landing reserve for the FTY build | FTY 0x6D00 | 0x6F00 low block: NCTAB, STEPTAB (29 words), VSTEP, spr_table, sprites,
   SCHAIN, level_data.  Test harness stubs move from page 0x6A to the DRAM spare 0x5EC0..0x5EFF (tools/m25_edit_c_tests.py).
 - sprites: cx = 32 + v/2 (was 3/4 v: 48.5 ~ 32/0.66), NCTAB = round(2*hc/9), weapon at byte columns 10..13.
The 128K build inherits everything via make128.py (mktap128.py: CLEAR = code start - 1)."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
G = ROOT / "tools/gen48.py"
K = ROOT / "src/48k/kea48.asm"
SC = ROOT / "src/common/sprites_c.asm"
SF = ROOT / "src/common/sprites_f.asm"
HU = ROOT / "src/common/hud.asm"
HB = ROOT / "src/common/hud_b.asm"
PX = ROOT / "tools/m22_pixdata.py"
MK = ROOT / "tools/mktap128.py"
BS = ROOT / "tools/build_m25_48.sh"

def edit(path, pairs, marker):
    s = path.read_text()
    if marker in s:
        print("%s: step C already applied" % path.name); return
    for old, new in pairs:
        assert s.count(old) == 1, "anchor not unique/found in %s: %r" % (path.name, old[:70])
        s = s.replace(old, new)
    path.write_text(s); print("%s: step C applied" % path.name)

# ---- 1. gen48.py
g_pairs = [
 ('Back buffer BUF = 24576: column-major, 16 byte-columns x 128-byte stride, row r of byte column c at BUF + c*128 + r.',
  'Back buffer BUF = 24832 (0x6100): column-major, 24 byte-columns x 96-byte stride, row r of byte column c at\n'
  '  COLBASE[c] + r = BUF + c*96 + r (M2.5C 192-px window; a column may cross a page -> all row pointers step with inc de).\n'
  '  Ray column col (0..63, 3 px): bytecol = 3*(col>>3) + ADJTAB[col&7] (0,0,0,1,1,2,2,2), slot bits SLOTM[col&7].'),
 ('  SLOTM[p]   byte  bits of ray slot p (p = col and 3) inside a byte: 192,48,12,3',
  '  SLOTM[p]   byte  bits of ray slot p (p = col and 7) inside its byte: E0 1C 03 F0 0F C0 38 07 (widths 3,3,2,4,4,2,3,3)\n'
  '  ADJTAB[p]  byte  byte column inside the 24-px group of 8 rays: 0,0,0,1,1,2,2,2\n'
  '  COLBASE[c] word  BUF + 96*c, c = 0..23 (page-contained, in the padding before HTABN)'),
 ('    plx = [round(-0.66 * math.sin(tau * a / 256) * 256) for a in range(256)]\n'
  '    ply = [round(0.66 * math.cos(tau * a / 256) * 256) for a in range(256)]\n',
  '    plx = [round(-0.99 * math.sin(tau * a / 256) * 256) for a in range(256)]     # M2.5C: plane 0.99 (192 px, square cells)\n'
  '    ply = [round(0.99 * math.cos(tau * a / 256) * 256) for a in range(256)]\n'),
 ("         '        include \"../common/floor.asm\"',                    # M2.3: floor lines code+data in the alignment padding\n",
  "         '        include \"../common/floor.asm\"',                    # M2.3: floor lines code+data in the alignment padding\n"
  "         \"COLBASE:\", dw([\"BUF+%d\" % (96 * c) for c in range(24)]),   # M2.5C: 24 column bases, same padding (page-contained)\n"),
 ('         "SLOTM:", "        defb 192,48,12,3",\n',
  '         "SLOTM:", "        defb 224,28,3,240,15,192,56,7",             # M2.5C: slot bits per col&7 (3,3,2,4,4,2,3,3 px)\n'
  '         "ADJTAB:", "        defb 0,0,0,1,1,2,2,2",                     # M2.5C: byte column inside the 24-px group\n'),
 ('            if r != last:\n                s.append("        inc e")\n',
  '            if r != last:\n                s.append("        inc de")                    # M2.5C: 96-byte stride, columns may cross a page\n'),
 ('    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2048", "        exx",\n',
  '    s += ["CLRBUF:", "        ld (cl_sp+1),sp", "        ld sp,BUF+2304", "        exx",            # M2.5C: 24 x 96 B\n'),
 ('          "        ld a,16", "cl_col: ld hl,65504", "        add hl,sp", "        ld sp,hl",\n'
  '          "        ld hl,65450"]                                  # M2.3: HL = 0xFFAA floor line word (odd row solid, even row checker)\n',
  '          "        ld a,24", "cl_col: ld hl,65450"]              # M2.3: HL = 0xFFAA floor line word; M2.5C: 24 columns, no row gap\n'),
 ('    s += ["COPYBUF:", "        ld (cb_sp+1),sp", "        exx", "        ld hl,BUF", "        exx", "        ld c,0",\n'
  '          "cb_col: exx", "        ld sp,hl", "        ld a,l", "        xor 128", "        ld l,a", "        jr nz,$+3",\n'
  '          "        inc h", "        exx"]\n',
  '    s += ["COPYBUF:", "        ld (cb_sp+1),sp", "        exx", "        ld hl,BUF", "        ld bc,96", "        exx", "        ld c,0",\n'
  '          "cb_col: exx", "        ld sp,hl", "        add hl,bc", "        exx"]      # M2.5C: HL\' = next column (stride 96)\n'),
 ('            s += ["        ld a,c", "        add a,%d" % (((y & 0x38) << 2) + 8), "        ld l,a",\n',
  '            s += ["        ld a,c", "        add a,%d" % (((y & 0x38) << 2) + 4), "        ld l,a",      # M2.5C: screen col 4 + c\n'),
 ('    s += ["        inc c", "        ld a,c", "        cp 16", "        jp c,cb_col", "cb_sp:  ld sp,0", "        ret"]\n',
  '    s += ["        inc c", "        ld a,c", "        cp 24", "        jp c,cb_col", "cb_sp:  ld sp,0", "        ret"]\n'),
 ('    nctab = [max(1, min(64, round(hc / 3))) if hc else 0 for hc in range(129)]\n'
  '    steptab = [0] + [min(65535, round(16 * 256 / nc)) for nc in range(1, 65)]\n',
  '    nctab = [max(1, min(28, round(2 * hc / 9))) if hc else 0 for hc in range(129)]   # M2.5C: 3 px per ray column -> nc = 16*hc/24/3\n'
  '    steptab = [0] + [min(65535, round(16 * 256 / nc)) for nc in range(1, 29)]       # nc <= 28 (hv cap 128)\n'),
 ('         "        org 27904              ; T1: page tables, sprite data, SCHAIN and the level live in the free low block 27904..32767",\n'
  '         "SPG:",                                                       # M2.2: ROWTAB (RAM) moved to DRAM (state.asm)\n'
  '         "CHJ:", "        defw " + ",".join("SCHAIN_END-%d" % (5 * n) for n in range(97)),\n'
  '         "NCTAB:", db(nctab), "STEPTAB:", dw(steptab), "VSTEP:", dw(vstep),\n'
  "         '        include \"../common/dash_data.asm\"      ; M2.2 dashboard data (tools/m22_pixdata.py)',\n",
  '         "        org 27648              ; M2.5C: dashboard data page 0x6C00 (0x6CB5..0x6CFF = ISR landing of the FTY build)",\n'
  "         '        include \"../common/dash_data.asm\"      ; M2.2 dashboard data (tools/m22_pixdata.py)',\n"
  '         "        org 28416              ; M2.5C: low block 0x6F00..0x7FFF: page tables, sprite data, SCHAIN and the level",\n'
  '         # M2.5C: CHJ (SCHAIN_END - 5n) is RAM at 0x6000 now, built by init_game (kea48.asm); SPG label dropped\n'
  '         "NCTAB:", db(nctab), "STEPTAB:", dw(steptab), "VSTEP:", dw(vstep),\n'),
 ('    s += ["SCHAIN:"] + ["        ld a,(de)", "        and c", "        or b", "        ld (de),a", "        inc e"] * 96\n',
  '    s += ["SCHAIN:"] + ["        ld a,(de)", "        and c", "        or b", "        ld (de),a", "        inc de"] * 96   # M2.5C: inc de\n'),
]

# ---- 2. kea48.asm
k_pairs = [
 ('; Window: 128x96 pixels at x 64..191, y 8..103 (byte columns 8..23, attribute rows 1..12). 64 rays, 2 px each.\n'
  '; Rendering: all pixels go to the back buffer BUF (column-major, 16 byte-columns x 128-byte stride) and are copied to the\n',
  '; Window (M2.5C): 192x96 pixels at x 32..223, y 8..103 (byte columns 4..27, attribute rows 1..12). 64 rays, 3 px each\n'
  '; (byte-rounded widths 3,3,2,4,4,2,3,3 per 24-px group: bytecol = 3*(col>>3) + ADJTAB[col&7], slot bits SLOTM[col&7]).\n'
  '; Rendering: all pixels go to the back buffer BUF (column-major, 24 byte-columns x 96-byte stride) and are copied to the\n'),
 ('ATTRWIN equ 22568          ; attribute address of window row 0 (attr row 1), column 8\n'
  'BUF     equ 24576          ; back buffer: byte column c, row r at BUF + c*128 + r (rows 96..127 unused)\n'
  'FTX     equ 26624          ; per-frame table: word FTX + 2k = fracx * k (k = 0..255), rebuilt when fracx changes\n'
  'FTY     equ 27392          ; same for fracy (page 0x6A left as a gap: ISR pushes during the FTY build land there)\n',
  'ATTRWIN equ 22564          ; attribute address of window row 0 (attr row 1), column 4 (M2.5C: 24 cells per row)\n'
  'CHJ     equ 24576          ; M2.5C: 0x6000..0x60C1 RAM: CHJ[n] = SCHAIN_END - 5n (n 0..96), built by init_game (sprites_f.asm\n'
  '                           ; reads it with ld l,a / inc l: page-contained). 0x60C2..0x60FF: ISR pushes at the last push of\n'
  '                           ; CLRBUF (SP = BUF) land here, not in SOLIDPG (latent M2.2..M2.5B bug: 4 B / 128K ~36 B per hit).\n'
  'BUF     equ 24832          ; 0x6100: back buffer, byte column c (0..23), row r at COLBASE[c] + r = BUF + c*96 + r (2,304 B)\n'
  'BUFCOLS equ 24             ; (tests read these two)\n'
  'BUFSTR  equ 96\n'
  'FTX     equ 27136          ; 0x6A00: per-frame table, word FTX + 2k = fracx * k (k = 0..255), rebuilt when fracx changes\n'
  '                           ; (ISR pushes at the end of its build land in BUF, which CLRBUF rewrites right after)\n'
  'FTY     equ 27904          ; 0x6D00: same for fracy (page 0x6C holds dash_data + the landing reserve for this build)\n'),
 ('init_game:\n'
  '        call win_tint          ; M2.5: window ink for this level (TINTTAB) into the 12x16 ATTRWIN cells; render never writes attributes\n',
  'init_game:\n'
  '        call win_tint          ; M2.5: window ink for this level (TINTTAB) into the 12x24 ATTRWIN cells; render never writes attributes\n'
  '        ld hl,CHJ              ; M2.5C: CHJ[n] = SCHAIN_END - 5n for n = 0..96 (sprite run-list chain entries) in RAM below BUF\n'
  '        ld de,SCHAIN_END\n'
  '        ld bc,5\n'
  '        ld a,97\n'
  'ig_chj: ld (hl),e\n'
  '        inc l\n'
  '        ld (hl),d\n'
  '        inc l\n'
  '        ex de,hl\n'
  '        or a\n'
  '        sbc hl,bc\n'
  '        ex de,hl\n'
  '        dec a\n'
  '        jr nz,ig_chj\n'),
 ('; into the window attribute cells (12 rows x 16 cells, rows 1..12 cols 8..23). Frame cells (cols 7 / 24) and the HUD stay as they are.\n',
  '; into the window attribute cells (12 rows x 24 cells, rows 1..12 cols 4..27). Frame cells (cols 3 / 28) and the HUD stay as they are.\n'),
 ('wt1:    ld b,16\n'
  'wt2:    ld (hl),a\n'
  '        inc l                  ; 16 cells of one row never cross a page (row low byte 0x28/0x48/../0xE8/0x08..)\n'
  '        djnz wt2\n'
  '        ld de,16               ; +32 per row: 16 done by inc l, 16 here\n',
  'wt1:    ld b,24\n'
  'wt2:    ld (hl),a\n'
  '        inc l                  ; 24 cells of one row never cross a page (row low byte 0x24/0x44/../0xE4 + 23 = 0xFB)\n'
  '        djnz wt2\n'
  '        ld de,8                ; +32 per row: 24 done by inc l, 8 here\n'),
 ('; column geometry\n'
  '        ld a,(col)\n'
  '        ld b,a\n'
  '        and 3\n'
  '        ld (sub4),a\n'
  '        ld a,b\n'
  '        srl a\n'
  '        srl a\n'
  '        ld (bytecol),a\n',
  '; column geometry (M2.5C): sub4 = col & 7 (SLOTM index), bytecol = 3*(col>>3) + ADJTAB[col&7]\n'
  '        ld a,(col)\n'
  '        ld b,a\n'
  '        and 7\n'
  '        ld (sub4),a\n'
  '        add a,ADJTAB and 255\n'
  '        ld l,a\n'
  '        ld h,ADJTAB/256\n'
  '        ld a,b\n'
  '        rrca\n'
  '        rrca\n'
  '        rrca\n'
  '        and 7                  ; col >> 3 = 24-px group\n'
  '        ld c,a\n'
  '        add a,a\n'
  '        add a,c\n'
  '        add a,(hl)\n'
  '        ld (bytecol),a\n'),
 ('        ld a,(bytecol)\n'
  '        rrca\n'
  '        ld e,a\n'
  '        and 7\n'
  '        add a,BUF/256\n'
  '        ld d,a\n'
  '        ld a,e\n'
  '        and 128\n'
  '        ld e,a\n'
  '        ld a,(topr)\n'
  '        add a,e\n'
  '        ld e,a                 ; DE = buffer address of the band\'s top row\n',
  '        ld a,(bytecol)         ; M2.5C: DE = COLBASE[bytecol] + topr (16-bit: a column may cross a page)\n'
  '        add a,a\n'
  '        add a,COLBASE and 255\n'
  '        ld c,a\n'
  '        ld b,COLBASE/256\n'
  '        ld a,(bc)\n'
  '        ld e,a\n'
  '        inc c\n'
  '        ld a,(bc)\n'
  '        ld d,a\n'
  '        ld a,(topr)\n'
  '        add a,e\n'
  '        ld e,a\n'
  '        jr nc,$+3\n'
  '        inc d                  ; DE = buffer address of the band\'s top row\n'),
]

# ---- 3. sprites_c.asm: cx = 32 + v/2 (32/0.99 = 32.3 rays per unit lateral/depth ratio)
sc_pairs = [
 ('; thing_xform2: tdx/tdy/tdepth set, IX -> thing. Camera lateral s = -dx*sin + dy*cos; column cx = 32 + 48.5*s/depth.\n',
  '; thing_xform2: tdx/tdy/tdepth set, IX -> thing. Camera lateral s = -dx*sin + dy*cos; column cx = 32 + 32.3*s/depth\n'
  '; (M2.5C: plane 0.99 -> 32/0.99 rays per unit of s/depth; was 48.5 = 32/0.66).\n'),
 ('        ret nc                 ; product >= 2^17 -> |cx-32| >= 96: off screen\n',
  '        ret nc                 ; product >= 2^17 -> |cx-32| >= 64: off screen\n'),
 ('        ld a,h                 ; A = v (0..127)\n'
  '        ld c,a\n'
  '        srl a\n'
  '        srl a\n'
  '        ld b,a\n'
  '        ld a,c\n'
  '        sub b                  ; A = 3/4 v = |cx - 32|  (48.5 ~ 64 * 3/4)\n'
  '        ld c,a\n',
  '        ld a,h                 ; A = v (0..127)\n'
  '        srl a                  ; A = v/2 = |cx - 32|  (M2.5C: 32.3 ~ 64 / 2)\n'
  '        ld c,a\n'),
]

# ---- 4. sprites_f.asm: COLBASE/ADJTAB/SLOTM(8) addressing, 16-bit row add
sf_pairs = [
 ('; Column c (0..63): zbuf[c] <= hv (no nearer wall) -> visible. Buffer byte column c/4, slot bits SLOTM[c&3]. Each run\n',
  '; Column c (0..63): zbuf[c] <= hv (no nearer wall) -> visible. Buffer byte column 3*(c>>3) + ADJTAB[c&7] (M2.5C, 3-px rays),\n'
  '; slot bits SLOTM[c&7]. Each run\n'),
 ('; buffer address: D = BUF/256 + (c>>3), E = (c&4)<<5 ; slot mask\n'
  '        ld a,(ds_c)\n'
  '        ld c,a\n'
  '        ld a,c\n'
  '        rrca\n'
  '        rrca\n'
  '        rrca\n'
  '        and 7\n'
  '        add a,BUF/256\n'
  '        ld d,a\n'
  '        ld a,c\n'
  '        and 4\n'
  '        rrca\n'
  '        rrca\n'
  '        rrca                   ; 4 -> 128\n'
  '        ld e,a\n'
  '        ld (dc_buf),de\n'
  '        ld a,c\n'
  '        and 3\n'
  '        add a,SLOTM and 255\n',
  '; buffer address (M2.5C): DE = COLBASE[3*(c>>3) + ADJTAB[c&7]] ; slot mask SLOTM[c&7]\n'
  '        ld a,(ds_c)\n'
  '        ld c,a\n'
  '        and 7\n'
  '        ld b,a                 ; B = c & 7\n'
  '        add a,ADJTAB and 255\n'
  '        ld l,a\n'
  '        ld h,ADJTAB/256\n'
  '        ld a,c\n'
  '        rrca\n'
  '        rrca\n'
  '        rrca\n'
  '        and 7                  ; c >> 3\n'
  '        ld e,a\n'
  '        add a,a\n'
  '        add a,e\n'
  '        add a,(hl)             ; bytecol\n'
  '        add a,a\n'
  '        add a,COLBASE and 255\n'
  '        ld l,a\n'
  '        ld h,COLBASE/256\n'
  '        ld e,(hl)\n'
  '        inc l\n'
  '        ld d,(hl)\n'
  '        ld (dc_buf),de\n'
  '        ld a,b\n'
  '        add a,SLOTM and 255\n'),
 ('        ld hl,(dc_buf)\n'
  '        ld a,l\n'
  '        or c\n'
  '        ld l,a\n'
  '        ex de,hl               ; DE = BUF column + r0\n',
  '        ld hl,(dc_buf)\n'
  '        ld a,l\n'
  '        add a,c\n'
  '        ld l,a\n'
  '        jr nc,$+3\n'
  '        inc h                  ; M2.5C: 16-bit (stride 96, a column may cross a page)\n'
  '        ex de,hl               ; DE = BUF column + r0\n'),
]

# ---- 5. hud.asm: frame at x 31 / x 224 (cols 3 / 28)
hu_pairs = [
 ('; Static (hud_init, data in dash_data.asm): red frame round the window (x 63 / x 192 / y 7), red rail y 104, red dividers\n',
  '; Static (hud_init, data in dash_data.asm): red frame round the window (M2.5C: x 31 / x 224 / y 7), red rail y 104, red dividers\n'),
 ('; frame sides x 63 / x 192 (rows 1..12) and dividers x 83 / x 171 (y 105..167)\n'
  'hi_v:   ld hl,0x4027           ; row 1 line 0, col 7\n'
  '        ld bc,96*256+1         ; 96 lines, left byte 0x01\n'
  '        ld de,17*256+128       ; right column +17 (col 24), byte 0x80\n',
  '; frame sides x 31 / x 224 (rows 1..12, M2.5C) and dividers x 83 / x 171 (y 105..167)\n'
  'hi_v:   ld hl,0x4023           ; row 1 line 0, col 3\n'
  '        ld bc,96*256+1         ; 96 lines, left byte 0x01\n'
  '        ld de,25*256+128       ; right column +25 (col 28), byte 0x80\n'),
 ('        ld hl,22528+32+7       ; frame sides red: rows 1..12, cols 7 and 24\n'
  '        ld d,17\n',
  '        ld hl,22528+32+3       ; frame sides red: rows 1..12, cols 3 and 28 (M2.5C)\n'
  '        ld d,25\n'),
]

# ---- 6. hud_b.asm: weapon centred in the 24-column window (byte columns 10..13), stride 96
hb_pairs = [
 ('; then 24 pixel bytes) into BUF byte columns 6..9, rows 72..95: buf = (buf AND mask) OR pix. ~ 96 rows x 7 ops.\n',
  '; then 24 pixel bytes) into BUF byte columns 10..13 (M2.5C: centre of 24), rows 72..95: buf = (buf AND mask) OR pix.\n'),
 ('        ld hl,BUF+6*128+72     ; byte column 6, row 72\n',
  '        ld hl,BUF+10*96+72     ; byte column 10, row 72 (M2.5C stride 96)\n'),
 ('        pop hl\n'
  '        ld a,l\n'
  '        add a,128\n'
  '        ld l,a\n'
  '        jr nc,$+3\n'
  '        inc h\n'
  '        pop bc\n'
  '        djnz dw_col\n',
  '        pop hl\n'
  '        ld a,l\n'
  '        add a,96               ; M2.5C: next byte column\n'
  '        ld l,a\n'
  '        jr nc,$+3\n'
  '        inc h\n'
  '        pop bc\n'
  '        djnz dw_col\n'),
]

# ---- 7. m22_pixdata.py: frame top line y 7 x 31..224, red cells cols 3..28 (regenerates src/common/dash_data.asm)
px_pairs = [
 ('runs = [(0x4707, 1, 0x01), (0x4708, 16, 0xFF), (0x4718, 1, 0x80),   # pixels: frame top line y 7, x 63..192\n',
  'runs = [(0x4703, 1, 0x01), (0x4704, 24, 0xFF), (0x471C, 1, 0x80),   # pixels: frame top line y 7, x 31..224 (M2.5C)\n'),
 ('        (attr(0, 7), 18, RED),       # frame top line y 7 (cols 7..24)\n',
  '        (attr(0, 3), 26, RED),       # frame top line y 7 (cols 3..28, M2.5C)\n'),
]

# ---- 8. mktap128.py: CLEAR follows the code start (image begins at the dash_data page 0x6C00 now)
mk_pairs = [
 ('CLEAR = 27903\n', 'CLEAR = 27903          # overwritten in main(): code start - 1 (M2.5C: the image starts at 0x6C00)\n'),
 ('def main():\n    start, code = code_block(pathlib.Path(sys.argv[1]).read_bytes())\n',
  'def main():\n    global CLEAR\n    start, code = code_block(pathlib.Path(sys.argv[1]).read_bytes())\n'
  '    CLEAR = start - 1                                   # M2.5C: RAMTOP just below the first loaded byte\n'),
]

# ---- 9. build_m25_48.sh: layout gates (COLBASE page-contained, dash page, low block org)
bs_pairs = [
 ("awk '$1==\"hi_end\"{a=$3;",
  "awk '$1==\"COLBASE\"{a=$3; sub(/H$/,\"\",a); v=strtonum(\"0x\" a)} $1==\"HTABN\"{h=$3; sub(/H$/,\"\",h); hv=strtonum(\"0x\" h)} "
  "END{ printf \"COLBASE 0x%04X..0x%04X page-contained below HTABN: %s\\n\", v, v+47, (int(v/256)==int((v+47)/256) && v+48<=hv)?\"yes\":\"NO\"; "
  "if (int(v/256)!=int((v+47)/256) || v+48>hv) exit 1 }' build/kea48.sym\n"
  "awk '$1==\"DASH_RUNS\"{a=$3; sub(/H$/,\"\",a); v=strtonum(\"0x\" a)} $1==\"NCTAB\"{n=$3; sub(/H$/,\"\",n); nv=strtonum(\"0x\" n)} "
  "END{ printf \"dash page 0x%04X (0x6C00: %s), low block org 0x%04X (0x6F00: %s)\\n\", v, (v==27648)?\"yes\":\"NO\", nv, (nv==28416)?\"yes\":\"NO\"; "
  "if (v!=27648 || nv!=28416) exit 1 }' build/kea48.sym\n"
  "awk '$1==\"hi_end\"{a=$3;"),
]

if __name__ == "__main__":
    edit(G, g_pairs, "M2.5C: 24 column bases")
    edit(K, k_pairs, "BUFCOLS equ 24")
    edit(SC, sc_pairs, "M2.5C: 32.3")
    edit(SF, sf_pairs, "M2.5C: 16-bit (stride 96")
    edit(HU, hu_pairs, "cols 3 and 28 (M2.5C)")
    edit(HB, hb_pairs, "M2.5C stride 96")
    edit(PX, px_pairs, "x 31..224 (M2.5C)")
    edit(MK, mk_pairs, "M2.5C: RAMTOP")
    edit(BS, bs_pairs, "COLBASE 0x%04X")

# ---- 10. kea48.asm: label on the dark-side shade so the walls-only geometry check can switch the 0xAA dither off (it is
#      indistinguishable from the floor checker on even rows: geo48 view 25.5/3.5/40 ray 56 measured 76 for an engine 78 / ref 80)
k2_pairs = [
 ('        ld a,(side)\n        rrca\n        sbc a,a\n        and 85\n        cpl                    ; 255 lit side / 170 dark side\n',
  '        ld a,(side)\n        rrca\n        sbc a,a\nrd_shade:\n        and 85                 ; tests poke rd_shade+1 = 0: both sides lit (walls-only geometry scan)\n        cpl                    ; 255 lit side / 170 dark side\n'),
]
if __name__ == "__main__":
    edit(K, k2_pairs, "rd_shade:")

# ---- 11. gen48.py: COLBASE page-contained BY CONSTRUCTION (1 Nov 07:5xZ, user: 128K walls missing on the right ~1/5).
#      The 128K image has +0xA7 B of code before the tables (shim128 replaces beeper): COLBASE landed at 0xD7DE..0xD80D, i.e. across
#      a page; `ld b,COLBASE/256` + `inc c` wrapped bytecols 17..23 to 0xD700.. -> base 0x0092 -> right 7 byte columns never drawn.
#      The 48K build (COLBASE 0xD737) was fine and the only page gate read kea48.sym. Guard: pad to the next page if < 48 B remain.
g2_pairs = [
 ('         "COLBASE:", dw(["BUF+%d" % (96 * c) for c in range(24)]),   # M2.5C: 24 column bases, same padding (page-contained)\n',
  '         "        if (($ and 255) > 208)\\n        defs 256 - ($ and 255)   ; COLBASE must not cross a page (ld b,COLBASE/256 + inc c)\\n        endif",\n'
  '         "COLBASE:", dw(["BUF+%d" % (96 * c) for c in range(24)]),   # M2.5C: 24 column bases, page-contained BY CONSTRUCTION (see 11.)\n'),
]
if __name__ == "__main__":
    edit(G, g2_pairs, "COLBASE must not cross a page")
