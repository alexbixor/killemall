; hud_next.asm - lane N2 (5 Nov 2026): the HUD of edition B as a LoRes band (brief section 4 FALLBACK path: hardware sprites
; were not attempted in the time budget - written down in N2_result.out). Rows 88..95 of the 128x96 frame, drawn after the
; sprites and the weapon by game_frame (sprites_next.asm):
;   background: band colour = message state (0 none: dark 226 ; 1 NEED A KEY: gold 140 ; 2 YOU DIED: blood 172 ; 3 LEVEL
;   CLEARED: moss 92), then 3x5 digits (rows 89..93) HEALTH at columns 2.. (3 digits, blood 175), SHIELD at 18.. (2 digits,
;   water 190, only when > 0), AMMO at 44.. (2 digits, gold 143), KILLS at 84.. (2 digits, bone 223), key icons 4x5 at
;   columns 112 (red key, blood 175) and 120 (blue key, bluestone 254): filled when held, a 1-px frame (dark 228) when not.
; Z80N: add hl,a = db 0EDh,031h
HUD_ROW     equ 88
HUD_BG      equ 226             ; dark level 2
HUD_FRAME   equ 228             ; dark level 4

hud_draw:
        ; band background: 8 rows x 128 bytes from SCR_BOT + (88-48)*128 = 6000h + 1400h = 7400h
        ld a,(g_msg)
        ld hl,hud_band_col
        db 0EDh,031h
        ld a,(hl)
        ld hl,7400h
        ld de,7401h
        ld (hl),a
        ld bc,8*128-1
        ldir
        ld a,(g_health)         ; HEALTH 3 digits
        ld c,175
        ld e,2
        call hud_num3
        ld a,(g_shield)         ; SHIELD 2 digits when > 0
        or a
        jr z,hd_ammo
        ld c,190
        ld e,18
        call hud_num2
hd_ammo:
        ld a,(g_ammo)
        ld c,143
        ld e,44
        call hud_num2
        ld a,(g_kills)
        ld c,223
        ld e,84
        call hud_num2
        ld a,(g_kkeys)          ; key icons
        ld hl,hud_key_frame
        ld c,HUD_FRAME
        bit 0,a
        jr z,hk_red
        ld hl,hud_key_fill
        ld c,175
hk_red: ld e,112
        push af
        call hud_glyph4
        pop af
        ld hl,hud_key_frame
        ld c,HUD_FRAME
        bit 1,a
        jr z,hk_blue
        ld hl,hud_key_fill
        ld c,254
hk_blue:
        ld e,120
        ; fall into hud_glyph4
; hud_glyph4: HL -> 5 rows (bit 3 = leftmost of 4 pixels), C = colour, E = column: rows HUD_ROW+1..+5. destroys A, B, D, HL
hud_glyph4:
        ld d,HUD_ROW+1
        ld b,5
hg_r:   push bc
        push hl
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca                    ; bit 7 = leftmost
        ld b,d
        push af
        ld a,e
        call scr_addr           ; HL = screen (row D, col E)
        pop af
        ld b,4
hg_px:  rla
        jr nc,hg_np
        ld (hl),c
hg_np:  inc hl
        djnz hg_px
        pop hl
        inc hl
        pop bc
        inc d
        djnz hg_r
        ret
hud_key_frame: db 0Fh,09h,09h,09h,0Fh
hud_key_fill:  db 0Fh,0Fh,0Fh,0Fh,0Fh

; hud_num3: A = value 0..255, C = colour, E = first column: hundreds, tens, units (4 columns per digit). destroys A, B, D, HL
hud_num3:
        ld d,0
hn3_h:  cp 100
        jr c,hn3_t
        sub 100
        inc d
        jr hn3_h
hn3_t:  push af
        ld a,d
        call hud_digit
        pop af
        ; fall into hud_num2
; hud_num2: A = value 0..99, C = colour, E = first column
hud_num2:
        ld d,0
hn2_t:  cp 10
        jr c,hn2_u
        sub 10
        inc d
        jr hn2_t
hn2_u:  push af
        ld a,d
        call hud_digit
        pop af
        ; fall into hud_digit (units)
; hud_digit: A = digit 0..9, C = colour, E = column -> 3x5 at rows 89..93 (bits 7..5 of each font byte), E += 4. destroys A, B, D, HL
hud_digit:
        ld l,a
        ld h,0
        ld d,h
        ld a,l
        add hl,hl
        add hl,hl
        db 0EDh,031h            ; add hl,a : HL = digit*5
        ld a,e
        ld de,hud_font
        add hl,de
        ld e,a
        ld d,HUD_ROW+1
        ld b,5
hd_r:   push bc
        push hl
        ld a,(hl)
        ld b,d
        push af
        ld a,e
        call scr_addr
        pop af
        ld b,3
hd_px:  rla
        jr nc,hd_np
        ld (hl),c
hd_np:  inc hl
        djnz hd_px
        pop hl
        inc hl
        pop bc
        inc d
        djnz hd_r
        ld a,e
        add a,4
        ld e,a
        ret
; 3x5 font, bit 7 = leftmost of 3 pixels (bits 7..5), one byte per row
hud_font:
        db 0E0h,0A0h,0A0h,0A0h,0E0h     ; 0
        db 040h,0C0h,040h,040h,0E0h     ; 1
        db 0E0h,020h,0E0h,080h,0E0h     ; 2
        db 0E0h,020h,060h,020h,0E0h     ; 3
        db 0A0h,0A0h,0E0h,020h,020h     ; 4
        db 0E0h,080h,0E0h,020h,0E0h     ; 5
        db 0E0h,080h,0E0h,0A0h,0E0h     ; 6
        db 0E0h,020h,020h,020h,020h     ; 7
        db 0E0h,0A0h,0E0h,0A0h,0E0h     ; 8
        db 0E0h,0A0h,0E0h,020h,0E0h     ; 9
hud_band_col:
        db HUD_BG,140,172,92            ; g_msg 0 none, 1 NEED A KEY, 2 YOU DIED, 3 LEVEL CLEARED
