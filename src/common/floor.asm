; floor.asm - M2.3 floor distance lines + M2.6 D5 ceiling fills. CLRBUF (gen/unrolled48.asm) fills the 24 floor words of every
; byte column with PUSHes; fl_set patches those 24 push opcodes once per frame: D5 = push de (fill word of the even words), C5 =
; push bc (fill word of the odd words; M2.5E dot lattice, both 0 on DETAIL LOW), E5 = push hl (line word 0xFF00: odd row solid
; -> a 1-px line). Word w covers window rows 48+2w (L/E) and 49+2w (H/D); its top edge is at perpendicular distance 24/w cells
; = FL_D4[w] in 1/16 cell. A line is drawn in word w when a grid distance k*8 (half cells, nearer than FL_KMAX cells) lies
; between FL_D4[w+1] and FL_D4[w] after both are shifted by the phase p = fl_ph/16, so the lines are 1/2 cell apart, flow toward
; the player when walking forward (fl_ph grows), away when backing, and stand still when turning (constant perpendicular
; distance = parallel to the camera plane). fl_ph is advanced by move_by (kea48.asm) via fl_adv with B = +38 / -38 (game_a.asm)
; once per tick in which the player actually moved (0.15 cell); a zero-delta or blocked axis adds nothing.
; M2.5B: the 24 ceiling pushes (cl_cl, rows 47..0, alternate set) get the mirror of their floor word (ceiling rows 46-2w,47-2w
; <-> floor rows 48+2w,49+2w), so the ceiling lines mirror the floor lines exactly and flow the same way.
; M2.6 D5 ceiling (2 Nov, approved mock): a continuous 45-degree X lattice, 8 px x 8 rows diamonds = FOUR fill words by w and 3
; (word = odd row 47-2w in the high byte, even row 46-2w in the low byte, like every push):
;   w&3=0 rows 47/46 = 80/41 -> DE' 0x8041 (push de = D5)      w&3=1 rows 45/44 = 22/14 -> BC' 0x2214 (push bc = C5)
;   w&3=2 rows 43/42 = 08/14 -> IX  0x0814 (push ix = DD E5)   w&3=3 rows 41/40 = 22/41 -> IY  0x2241 (push iy = FD E5)
; The ceiling line word stays HL' = 0x00FF (push hl = E5: even row solid). So the ceiling slot of word w is 1 byte for w&3 in
; {0,1} (D5 / C5, or E5 for a line) and 2 bytes for w&3 in {2,3} (DD E5 / FD E5, or 00 E5 = nop + push hl for a line): fl_set
; writes exactly one byte per word (the opcode, or the prefix byte of a 2-byte slot). Slot layout per column: 1,1,2,2 bytes x 6
; = 36 bytes; the written byte of word w sits at cl_cl + 6*(w/4) + (0,1,2,4)[w&3]. FL_D4 is 4-aligned so (L and 3) == (w and 3)
; while HL walks it. Cost: fl_set ~5.5k T per frame; CLRBUF +12 prefix bytes x 4 T x 24 columns = +1,152 T per frame (0.3 %).
; Placement: tables48.asm includes this file right before the 256-byte alignment of HTABN, i.e. inside padding that was
; already lost -> 0 bytes of code budget while it stays below that boundary (tools/build_m25_48.sh checks HTABN stays put).
FL_KMAX equ 4                  ; half-cell lines nearer than 4 cells (beyond that they compress into the horizon: checker)
fl_set: ld a,(fl_ph)
        rlca
        rlca
        rlca
        rlca
        and 15
        ld c,a                 ; C = phase 0..15 (1/16 cell)
        ld hl,FL_D4+24
        ld de,cl_fl            ; first floor push = word 23 (rows 95,94) ... last = word 0 (rows 49,48)
        ld ix,cl_cl+34         ; M2.6: written byte of ceiling word 23 = cl_cl + 6*5 + 4 (slot layout above)
        ld a,(hl)
        add a,c
        ld b,a                 ; B = bottom edge of word 23, shifted (no overflow: FL_D4 <= 240, p <= 15)
fl_lp:  dec hl
        ld a,(hl)
        add a,c                ; A = top edge of word w, shifted
        push af
        xor b
        and 0xF8
        jr z,fl_f              ; both edges in the same half-cell interval: no grid line crosses this word -> fill
        ld a,b
fl_k:   cp FL_KMAX*16          ; tests poke fl_k+1 = 0 to switch the lines off (walls-only geometry check)
        jr nc,fl_f             ; k >= FL_KMAX: too far, keep the fill
        ld a,0xE5              ; floor line: push hl (HL = 0xFF00, odd row solid)
        ld (de),a
        bit 1,l
        jr z,fl_w              ; ceiling 1-byte slot: E5 = push hl' (0x00FF, even row solid)
        xor a                  ; ceiling 2-byte slot: 00 E5 = nop + push hl'
        jr fl_w
fl_f:   ld a,0xD5              ; push de = fill word of the even words (FL_D4 is 4-aligned, so bit 0 of L == w & 1)
        bit 0,l
        jr z,fl_f2
        ld a,0xC5              ; push bc = fill word of the odd words
fl_f2:  ld (de),a
        bit 1,l
        jr z,fl_w              ; ceiling w&3 in {0,1}: the same opcode (DE' 0x8041 / BC' 0x2214)
        ld a,0xDD              ; w&3 = 2: prefix of push ix (0x0814)
        bit 0,l
        jr z,fl_w
        ld a,0xFD              ; w&3 = 3: prefix of push iy (0x2241)
fl_w:   ld (ix+0),a
        inc de
        dec ix
        ld a,l
        rrca
        xor l
        and 1
        jr nz,fl_n             ; w&3 in {1,2}: the next word's byte is 1 below
        dec ix                 ; w&3 in {0,3}: 2 below (an E5 byte of a 2-byte slot lies between)
fl_n:   pop af
        ld b,a                 ; this top edge is the bottom edge of the next (farther) word
        ld a,l
        cp low FL_D4
        jr nz,fl_lp
        ret
fl_adv: ld a,(fl_ph)           ; B = signed step (38 / -38 / 0); called by move_by after each stored axis
        add a,b
        ld (fl_ph),a
        ret
fl_ph:  defb 0                 ; forward distance walked, 1/256 cell, wraps
; M2.6 apply_opts (moved here from kea48.asm, same contract): opt_detail 1 -> the six CLRBUF fill words (D5 ceiling DE'/BC'/IX/IY,
; floor diamonds DE/BC); 0 -> all six 0x0000 = plain black floor + ceiling (the distance lines stay: HL 0xFF00 / HL' 0x00FF are
; constants). Written straight into the ld immediates of CLRBUF: cl_ce+1, cl_cb+1, cl_cx+2, cl_cy+2, cl_de+1, cl_bc+1.
apply_opts:
        ld hl,FILL_HI
        ld a,(opt_detail)
        or a
        jr nz,ao_cp
        ld hl,FILL_LO
ao_cp:  ld de,cl_ce+1          ; cl_ce: ld de,nn / cl_cb: ld bc,nn (3 bytes each, consecutive)
        ldi
        ldi
        inc de
        ldi
        ldi
        ld de,cl_cx+2          ; cl_cx: ld ix,nn / cl_cy: ld iy,nn (4 bytes each) / cl_de: ld de,nn / cl_bc: ld bc,nn
        ldi
        ldi
        inc de
        inc de
        ldi
        ldi
        inc de
        ldi
        ldi
        inc de
        ldi
        ldi
        ret
FILL_HI: defw 0x8041, 0x2214, 0x0814, 0x2241, 0x0100, 0x1000
FILL_LO: defw 0, 0, 0, 0, 0, 0
        if ($ and 3)
        defs 4 - ($ and 3)     ; M2.6: FL_D4 4-aligned (fl_set reads w and 3 from bits 0..1 of L)
        endif
FL_D4:  defb 240,240,192,128,96,77,64,55,48,43,38,35,32,30,27,26,24,23,21,20,19,18,17,17,16   ; round(384/w), w = 0..24; 240 = far
fl_end:
