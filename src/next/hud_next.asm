; hud_next.asm - lane N2 (5 Nov 2026): the HUD of edition B as a LoRes band (brief section 4 FALLBACK path: hardware sprites
; were not attempted in the time budget - written down in N2_result.out). Rows 88..95 of the 128x96 frame, drawn after the
; sprites and the weapon by game_frame (sprites_next.asm):
;   background: band colour = message state (0 none: dark 226 ; 1 NEED A KEY: gold 140 ; 2 YOU DIED: blood 172 ; 3 LEVEL
;   CLEARED: moss 92), then 3x5 digits (rows 89..93) HEALTH at columns 2.. (3 digits, blood 175), SHIELD at 18.. (2 digits,
;   water 190, only when > 0), AMMO at 44.. (2 digits, gold 143), KILLS at 84.. (2 digits, bone 223), key icons 4x5 at
;   columns 112 (red key, blood 175) and 120 (blue key, bluestone 254): filled when held, a 1-px frame (dark 228) when not.
; lane N4 (8 Nov 2026, bug 1 "HUD flash", build/night/N4_result.out item 2): the band is NOT cleared every frame any more.
;   The engine never writes rows 88..95 while the HUD is on (walk_b.asm wb_rmax = 88, set by game_frame), so the band
;   persists between frames. hud_draw paints the band background + every field once (g_hud_valid = 0: level start, after a
;   frame without the HUD, g_msg change = band colour change) and afterwards only the fields whose value changed since the
;   shadow copy (hud_sh_*): the field's 5 rows are cleared to the band colour, then the digits are drawn.
; Z80N: add hl,a = db 0EDh,031h
HUD_ROW     equ 88
HUD_BG      equ 226             ; dark level 2
HUD_FRAME   equ 228             ; dark level 4
; shadows (main_b_vars.inc: 5E22h..5EDFh free; FPSHUD uses 5EE0h..5EE4h; the test hook 5EF0h..). Bank 5 is zero at load.
hud_sh_msg    equ 5EC0h         ; byte  g_msg of the band on screen
hud_sh_health equ 5EC1h         ; byte  shadows of the fields drawn (0FFh = not drawn: forces a redraw)
hud_sh_shield equ 5EC2h
hud_sh_ammo   equ 5EC3h
hud_sh_kills  equ 5EC4h
hud_sh_kkeys  equ 5EC5h
hud_sh_fps    equ 5EC6h
g_hud_valid   equ 5EC7h         ; byte  1 = the band on screen is complete (game_frame clears it when the HUD is not drawn)

hud_draw:
        ld a,(g_hud_valid)
        or a
        jr nz,hd_check_msg
hd_full:
        call hud_band_fill      ; band background + all shadows invalidated
        ld a,1
        ld (g_hud_valid),a
        IF DEFINED MOUSE_B
        ld a,0FFh
        ld (hud_sh_mouse),a     ; lane N5: the band was repainted -> redraw the mouse indicator too
        ENDIF
        jr hd_fields
hd_check_msg:
        ld a,(g_msg)
        ld hl,hud_sh_msg
        cp (hl)
        jr nz,hd_full           ; band colour changed: repaint everything
hd_fields:
        ld a,(g_health)         ; HEALTH 3 digits
        ld hl,hud_sh_health
        cp (hl)
        jr z,hd_shield
        ld (hl),a
        ld e,2
        ld b,12
        call hud_field_clear
        ld a,(g_health)               ; HF1 (8 Nov 2026, found by lane N6): hud_field_clear returns A = HUD_ROW+6 (94): N4's code draws "94" in every field
        ld c,175
        call hud_num3
hd_shield:
        ld a,(g_shield)         ; SHIELD 2 digits when > 0
        ld hl,hud_sh_shield
        cp (hl)
        jr z,hd_ammo
        ld (hl),a
        ld e,18
        ld b,8
        call hud_field_clear
        ld a,(g_shield)
        or a
        jr z,hd_ammo
        ld c,190
        call hud_num2
hd_ammo:
        ld a,(g_ammo)
        ld hl,hud_sh_ammo
        cp (hl)
        jr z,hd_kills
        ld (hl),a
        ld e,44
        ld b,8
        call hud_field_clear
        ld a,(g_ammo)               ; HF1 (8 Nov 2026, found by lane N6): hud_field_clear returns A = HUD_ROW+6 (94): N4's code draws "94" in every field
        ld c,143
        call hud_num2
hd_kills:
        ld a,(g_kills)
        ld hl,hud_sh_kills
        cp (hl)
        jr z,hd_fps
        ld (hl),a
        ld e,84
        ld b,8
        call hud_field_clear
        ld a,(g_kills)               ; HF1 (8 Nov 2026, found by lane N6): hud_field_clear returns A = HUD_ROW+6 (94): N4's code draws "94" in every field
        ld c,223
        call hud_num2
hd_fps:
        if defined FPSHUD
; ---- lane H1 (7 Nov 2026): fps readout for the real-hardware session, ONLY in builds made with `--equ FPSHUD=1`
; (tools/nx_build.py pass-through -> build/next/killemall_b_fps.nex). The default build has no byte of this block.
; fps = frames rendered in the last 50 ticks: hud_draw runs once per frame (after walk_frame_b incremented frames), so
; when ticks - fps_tick >= 50 the frame count since the previous sample is latched and the sample point moves on by 50
; (not to 'now', so the windows tile the tick axis). Two digits (bone 223) at HUD columns 100..107, free between KILLS
; (84..91) and the key icons (112..). Variables in free bank 5 RAM 5EE0h..5EE4h (main_b_vars.inc: 5E22h..5EEFh unused;
; the test hook starts at 5EF0h), zero at load (bank 5 is zero in the .nex):
;   fps_tick    equ 5EE0h   ; word  ticks value at the start of the current 50-tick window
;   fps_frames  equ 5EE2h   ; word  frames value at the start of the current window
;   fps_val     equ 5EE4h   ; byte  frames counted in the last complete window (0..99 shown; capped at 99)
        ld hl,(ticks)
        ld de,(5EE0h)
        or a
        sbc hl,de                       ; HL = ticks since the window start
        ld a,h
        or a
        jr nz,hf_cap                    ; >= 256 ticks (first frame after a long load): resync without a reading
        ld a,l
        cp 50
        jr c,hf_show
        ld hl,(5EE2h)
        ex de,hl
        ld hl,(frames)
        ld (5EE2h),hl                   ; the window starts again at the current frame count
        or a
        sbc hl,de                       ; HL = frames in the window
        ld a,h
        or a
        jr nz,hf_99
        ld a,l
        cp 100
        jr c,hf_store
hf_99:  ld a,99
hf_store:
        ld (5EE4h),a
        ld hl,(5EE0h)
        ld de,50
        add hl,de
        ld (5EE0h),hl
        jr hf_show
hf_cap:
        ld hl,(ticks)
        ld (5EE0h),hl
        ld hl,(frames)
        ld (5EE2h),hl
hf_show:
        ld a,(5EE4h)                    ; lane N4: redrawn only when the reading changed
        ld hl,hud_sh_fps
        cp (hl)
        jr z,hd_keys
        ld (hl),a
        ld e,100
        ld b,8
        call hud_field_clear
        ld a,(5EE4h)                    ; HF1 (8 Nov 2026, found by lane N6): reload the reading (hud_field_clear destroys A)
        ld c,223
        call hud_num2
        endif
hd_keys:
        IF DEFINED MOUSE_B
; ---- lane N5 (8 Nov 2026): mouse indicator, a 4x5 "M" (bone 223) at HUD columns 94..97 (free between KILLS 84..91 and the
; FPSHUD digits 100..107), drawn when opt_mouse_b = 1, cleared to the band colour when 0; dirty-flag like every other field.
hud_sh_mouse equ 5EC8h          ; byte  opt_mouse_b value of the indicator on screen (0FFh = not drawn)
        ld a,(opt_mouse_b)
        ld hl,hud_sh_mouse
        cp (hl)
        jr z,hd_keys2
        ld (hl),a
        ld e,94
        ld b,4
        call hud_field_clear
        ld a,(opt_mouse_b)
        or a
        jr z,hd_keys2
        ld hl,hud_glyph_m
        ld c,223
        ld e,94
        call hud_glyph4
        jr hd_keys2
hud_glyph_m: db 09h,0Fh,0Fh,09h,09h
hd_keys2:
        ENDIF
        ld a,(g_kkeys)          ; key icons
        ld hl,hud_sh_kkeys
        cp (hl)
        ret z
        ld (hl),a
        ld e,112
        ld b,12
        call hud_field_clear
        ld a,(g_kkeys)
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
        IF DEFINED HWSPR_B
        call hw_pat_addr        ; lane N6: HL = HW_PBUF (row D, col E) - the band is a sprite pattern buffer
        ELSE
        call scr_addr           ; HL = screen (row D, col E)
        ENDIF
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
        IF DEFINED HWSPR_B
        call hw_pat_addr        ; lane N6
        ELSE
        call scr_addr
        ENDIF
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

; hud_band_fill (lane N4): band background 8 rows x 128 bytes from SCR_BOT + (88-48)*128 = 6000h + 1400h = 7400h in the
; colour of g_msg; stores hud_sh_msg and sets every field shadow to 0FFh (no field value is 255: health <= 100, ammo/kills
; <= 99, shield <= 99, kkeys <= 3, fps <= 99) so the next hud_draw repaints all of them. destroys A, BC, DE, HL
hud_band_fill:
        ld a,(g_msg)
        ld (hud_sh_msg),a
        ld hl,hud_band_col
        db 0EDh,031h
        ld a,(hl)
        IF DEFINED HWSPR_B
        ld hl,HW_PBUF           ; lane N6: the band lives in the pattern buffer; every band sprite must be uploaded
        ld de,HW_PBUF+1
        ld (hl),a
        ld bc,8*128-1
        ldir
        ld a,0FFh
        ld (hw_dirty),a
        ELSE
        ld hl,7400h
        ld de,7401h
        ld (hl),a
        ld bc,8*128-1
        ldir
        ENDIF
        ld hl,hud_sh_health
        ld de,hud_sh_shield
        ld (hl),0FFh
        ld bc,5                 ; health, shield, ammo, kills, kkeys, fps
        ldir
        ret

; hud_field_clear (lane N4): rows HUD_ROW+1..+5 (89..93), columns E .. E+B-1 = band colour of g_msg. keeps E. destroys A, B, C, D, HL
hud_field_clear:
        IF DEFINED HWSPR_B
        call hw_mark_dirty      ; lane N6: the band sprites covering columns E..E+B-1 need an upload after this field
        ENDIF
        ld a,(g_msg)
        ld hl,hud_band_col
        db 0EDh,031h
        ld c,(hl)               ; C = band colour
        ld d,HUD_ROW+1
hfc_r:  push bc
        push de
        ld a,e
        ld b,d
        IF DEFINED HWSPR_B
        call hw_pat_addr        ; lane N6
        ELSE
        call scr_addr           ; HL = screen (row D, col E)
        ENDIF
        pop de
        pop bc
        push bc
hfc_px: ld (hl),c
        inc hl
        djnz hfc_px
        pop bc
        inc d
        ld a,d
        cp HUD_ROW+6
        jr nz,hfc_r
        ret
