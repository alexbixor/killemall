; hud.asm (T1, M2.2) - TTT-style dashboard below the 3D window: rows 13..23, non-bright inks on black paper.
; Static (hud_init, data in dash_data.asm): red frame round the window (M2.5C: x 31 / x 224 / y 7), red rail y 104, red dividers
; x 83 / x 171 (y 105..167), bold red labels AMMO HEALTH KEYS (row 14), SHIELD KILLS (row 18), PISTOL (row 19, white).
; Dynamic (hud_update, each instrument redrawn only when its value changes):
;   AMMO   10 pips cols 0..9 rows 16-17 (1 pip = 10 rounds: white lead head / yellow brass case), value row 14 cols 8..9
;   HEALTH framed 72x10 bar at (88,128): fill 70*h/100 px, empty part 50 % checker trough; white, red at h <= 33
;          (bar cells + value); value row 14 cols 18..20
;   SHIELD same bar at (88,160), cyan; value row 18 cols 18..20
;   KEYS   16x8 pills R (176,128) B (200,128): filled with a black letter = held, outline = missing
;   KILLS  value row 18 cols 28..30
; Message line: row 22 cols 2..29 (hud_message HL, <= 28 chars, auto-clears after 100 frames). Weapon graphic: hud_b.asm.
ROW14   equ 18624              ; 0x48C0 = pixel address of text row 14, line 0
ROW18   equ 20544              ; 0x5040
ROW22   equ 20672              ; 0x50C0
HBAR    equ 0x500B             ; health bar: col 11, y 128
SBAR    equ 0x508B             ; shield bar: col 11, y 160
hud_init:
        ld a,255
        IF DEFINED FLIP
        ld (hud_dirty),a       ; lane F rule F6: the HUD rows are redrawn -> mirror them into bank 7 at the next frame
        ENDIF
        ld (hud_health),a
        ld (hud_ammo),a
        ld (hud_keys),a
        ld (hud_kills),a
        ld (hud_shield),a
        xor a
        ld (msg_timer),a
; DASH_RUNS: (address, count, byte) runs of attributes and static pixel lines (rail, top frame line); address 0 ends
        ld hl,DASH_RUNS
hi_r:   ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,d
        or e
        jr z,hi_l
        ld b,(hl)
        inc hl
        ld c,(hl)
        inc hl
        push hl
        ex de,hl
hi_r1:  ld (hl),c
        inc hl
        djnz hi_r1
        pop hl
        jr hi_r
; DASH_LABELS: (address, text, 0) bold labels; address 0 ends (follows the runs terminator)
hi_l:   ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,d
        or e
        jr z,hi_v
        call print_bold
        inc hl
        jr hi_l
; frame sides x 31 / x 224 (rows 1..12, M2.5C) and dividers x 83 / x 171 (y 105..167)
hi_v:   ld hl,0x4023           ; row 1 line 0, col 3
        ld bc,96*256+1         ; 96 lines, left byte 0x01
        ld de,25*256+128       ; right column +25 (col 28), byte 0x80
        call vline2
        ld hl,0x49AA           ; y 105, col 10
        ld bc,63*256+0x10      ; 63 lines, bit 3
        ld de,11*256+0x10      ; col 21
        call vline2
        ld hl,22528+32+3       ; frame sides red: rows 1..12, cols 3 and 28 (M2.5C)
        ld d,25
        ld c,12
        call attr_pair
        ld hl,22528+14*32+10   ; dividers red: rows 14..20, cols 10 and 21 (row 13 is the red rail)
        ld d,11
        ld c,7
        call attr_pair
        jp hud_update
; vline2: HL = screen address, B = lines, C = byte for this column, D = column delta, E = byte for the other column
vline2: ld (hl),c
        ld a,l
        add a,d
        ld l,a
        ld (hl),e
        sub d
        ld l,a
        call down_line
        djnz vline2
        ret
; attr_pair: HL = attribute cell, D = column delta, C = rows -> both cells red in C rows
attr_pair:
        ld (hl),2
        ld a,l
        add a,d
        ld l,a
        ld (hl),2
        sub d
        add a,32
        ld l,a
        jr nc,$+3
        inc h
        dec c
        jr nz,attr_pair
        ret
; down_line: HL -> same column, one pixel line down (any screen third)
down_line:
        inc h
        ld a,h
        and 7
        ret nz
        ld a,l
        add a,32
        ld l,a
        ret c
        ld a,h
        sub 8
        ld h,a
        ret
; print_bold: HL = 0-terminated text, DE = screen address; ROM font with each row OR row >> 1. Returns HL at the 0.
print_bold:
        ld a,(hl)
        or a
        ret z
        push hl
        push de
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,ROMFONT
        add hl,bc
        ld b,8
pb1:    ld a,(hl)
        ld c,a
        srl a
        or c
        ld (de),a
        inc hl
        inc d
        djnz pb1
        pop de
        pop hl
        inc e
        inc hl
        jr print_bold
hud_update:
        ld a,(health)
        ld hl,hud_health
        cp (hl)
        jr z,hu1
        ld (hl),a
        call health_draw
hu1:    ld a,(ammo)
        ld hl,hud_ammo
        cp (hl)
        jr z,hu2
        ld (hl),a
        call ammo_draw
hu2:    ld a,(shield)
        ld hl,hud_shield
        cp (hl)
        jr z,hu3
        ld (hl),a
        push af
        ld de,ROW18+18
        call print_num3
        pop af
        ld hl,SBAR
        call bar_draw
hu3:    ld a,(keys)
        ld hl,hud_keys
        cp (hl)
        jr z,hu4
        ld (hl),a
        call keys_draw
hu4:    ld a,(kills)
        ld hl,hud_kills
        cp (hl)
        jr z,hu5
        ld (hl),a
        ld de,ROW18+28
        call print_num3
hu5:    ld a,(msg_timer)
        or a
        ret z
        dec a
        ld (msg_timer),a
        ret nz
        ld hl,msg_blank
        jp hud_text
; health_draw: A = health -> value, colour of value + bar cells (white, red at <= 33), bar
health_draw:
        push af
        ld de,ROW14+18
        call print_num3
        pop af
        push af
        ld c,7
        cp 34
        jr nc,hd1
        ld c,2
hd1:    ld hl,22528+14*32+18   ; value cells
        ld (hl),c
        inc l
        ld (hl),c
        inc l
        ld (hl),c
        ld hl,22528+16*32+11   ; bar cells rows 16..17, cols 11..19
        call fill9
        ld l,(17*32+11) and 255
        call fill9
        pop af
        ld hl,HBAR
        jp bar_draw
fill9:  ld b,9
f9:     ld (hl),c
        inc l
        djnz f9
        ret
; bar_draw: A = 0..100, HL = screen address of the top-left byte: framed 72 x 10 bar (frame 1 px), fill 70*A/100 px,
; empty part = 50 % checker ((x + y) even = ink). Rows: frame, 8 fill lines, frame.
bar_draw:
        push hl
        call bar_f
        inc a                  ; + left frame pixel
        ld (bd_f),a
        ld a,0x55              ; first fill line y is odd: ink on odd x (x 88 = bit 7 is even)
        ld (bd_chk),a
        pop hl
        push hl
        call bar_line_ff
        pop hl
        ld c,8
bd_l:   push bc
        call down_line
        push hl
        call bar_fill_line
        pop hl
        ld a,(bd_chk)
        cpl
        ld (bd_chk),a
        pop bc
        dec c
        jr nz,bd_l
        call down_line
bar_line_ff:
        ld b,9
blf:    ld (hl),255
        inc l
        djnz blf
        ret
; bar_fill_line: HL = line address (col 11): bd_f pixels of ink from the left, checker bd_chk in the rest, right frame bit
bar_fill_line:
        ld a,(bd_f)
        ld d,a
        ld a,(bd_chk)
        ld e,a
        ld b,9
bfl:    ld a,d
        cp 8
        jr c,bfl_p
        sub 8
        ld d,a
        ld a,255
        jr bfl_w
bfl_p:  push hl
        ld hl,LMASK
        add a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,(hl)
        pop hl
        ld c,a
        cpl
        and e
        or c
        ld d,0
bfl_w:  ld (hl),a
        inc l
        djnz bfl
        dec l
        set 0,(hl)
        ret
; bar_f: A = 0..100 -> A = 70*A/100 exactly: 7*(A/10) + BARTAB[A mod 10]
bar_f:  ld c,0
barf_l: cp 10
        jr c,barf_r
        sub 10
        inc c
        jr barf_l
barf_r: ld hl,BARTAB
        add a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,(hl)
        inc c
barf_m: dec c
        ret z
        add a,7
        jr barf_m
; ammo_draw: A = ammo (0..99) -> 2-digit value, pips: lit = (ammo + 9) / 10 from the left
ammo_draw:
        push af
        call num3
        ld hl,num_txt+1
        ld de,ROW14+8
        call print
        pop af
        add a,9
        ld c,0
ad_q:   cp 10
        jr c,ad_d
        sub 10
        inc c
        jr ad_q
ad_d:   ld b,10
ad_k:   push bc
        ld de,PIPFULL
        ld a,c
        or a
        jr nz,ad_f
        ld de,PIPEMPTY
ad_f:   ld a,10
        sub b
        ld l,a
        ld h,0x52              ; y 130 (row 16 line 2) + col
        push hl
        ld b,6
ad_p1:  ld a,(de)
        ld (hl),a
        inc de
        inc h
        djnz ad_p1
        pop hl
        ld a,l
        add a,0x20
        ld l,a
        ld h,0x50              ; y 136 (row 17 line 0) + col
        ld b,7
ad_p2:  ld a,(de)
        ld (hl),a
        inc de
        inc h
        djnz ad_p2
        pop bc
        ld a,c
        or a
        jr z,$+3
        dec c
        djnz ad_k
        ret
; keys_draw: A = keys (b0 red, b1 blue) -> pills
keys_draw:
        ld c,a
        ld de,PILLS            ; R held
        bit 0,c
        jr nz,$+5
        ld de,PILLS+16         ; R missing
        ld hl,0x5016           ; (176,128): row 16 line 0, col 22
        call pill_draw
        ld de,PILLS+32         ; B held
        bit 1,c
        jr nz,$+5
        ld de,PILLS+48
        ld hl,0x5019           ; (200,128): col 25
pill_draw:                     ; DE = 8 rows x 2 bytes, HL = screen address
        ld b,8
        IF DEFINED FLIP
        ld a,b
        ld (hud_dirty),a       ; lane F rule F6
        ENDIF
pd_l:   ld a,(de)
        ld (hl),a
        inc de
        inc l
        ld a,(de)
        ld (hl),a
        inc de
        dec l
        inc h
        djnz pd_l
        ret
; hud_message: HL = 0-terminated text (<= 28 chars), shown for 100 frames on row 22
hud_message:
        ld a,100
        ld (msg_timer),a
hud_text:                      ; print HL at row 22 col 2, space-padded to 28 chars
        ld de,ROW22+2
        ld b,28
ht_l:   ld a,(hl)
        or a
        jr z,ht_pad
        inc hl
        call print_char
        djnz ht_l
        ret
ht_pad: ld a,32
        call print_char
        djnz ht_pad
        ret
; print_num3: A = 0..255 -> 3 digits at DE (ROM font); num3: digits into num_txt only
print_num3:
        call num3
        ld hl,num_txt
        jp print
num3:   ld hl,num_txt
        ld (hl),48
        inc hl
        ld (hl),48
        inc hl
        ld (hl),48
        ld hl,num_txt
pn_h:   cp 100
        jr c,pn_t
        sub 100
        inc (hl)
        jr pn_h
pn_t:   inc hl
pn_t1:  cp 10
        jr c,pn_u
        sub 10
        inc (hl)
        jr pn_t1
pn_u:   inc hl
        add a,(hl)
        ld (hl),a
        ret
LMASK:  defb 0,128,192,224,240,248,252,254,255
BARTAB: defb 0,0,1,2,2,3,4,4,5,6
PIPFULL:  defb 16,56,124,124,124,124,124,124,124,124,124,124,124
PIPEMPTY: defb 16,40,68,68,68,68,124,68,68,68,68,68,124
num_txt:    defb "000",0
msg_blank:  defb 0
hud_health: defb 255
hud_ammo:   defb 255
hud_keys:   defb 255
hud_kills:  defb 255
hud_shield: defb 255
msg_timer:  defb 0
bd_f:       defb 0
bd_chk:     defb 0
