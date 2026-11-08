; hwspr_next.asm - lane N6 (8 Nov 2026): HUD band + weapon as Spectrum Next HARDWARE SPRITES (spec v0.2 section 7 design
; intent: "HUD and weapon = Next hardware sprites, zero CPU, always above the view"). Every byte of this file is inside
; IF DEFINED HWSPR_B (pasmo --equ HWSPR_B=1): the HWSPR_B-undefined build is byte-identical to killemall_b.nex (oracle A).
; Included by main_b.asm in the 0A200h block after mouse_next.asm (below PLANES 0A800h). Variables: main_b_vars.inc (HW_*).
;
; Geometry (the LoRes layer is 128x96 scaled 2x to 256x192; sprite coordinates are screen pixels with the 32-px border
; origin): LoRes pixel (col, row) -> sprite x = 32 + 2*col, y = 32 + 2*row. Every sprite here is an 8-bit anchor at 2x/2x
; scale (attribute 4 = 0Ah: X scale 01, Y scale 01), so ONE pattern pixel = ONE LoRes pixel and the art stays on the LoRes grid.
;   weapon  = sprites 0..3, 2x2 of 16x16 patterns covering LoRes (48..79, 64..95): (48,64) (64,64) (48,80) (64,80) ->
;             sprite (128,160) (160,160) (128,192) (160,192); patterns 0..3 = idle, 4..7 = fire (art rows 24..31 are the
;             zero pad of sprites_b.bin -> transparent, the band sprites show through at rows 88..95).
;   band    = sprites 4..11, 8 sprites of 16x16 patterns 8..15 at LoRes (16*i, 88) -> sprite (32 + 32*i, 208); only the
;             top 8 pattern rows (LoRes rows 88..95) are inside the 256x192 paper, rows 8..15 fall in the bottom border and
;             are clipped (nextreg 15h bit 1 = 0: no sprites over the border), so the RAM pattern buffer keeps 8 rows x 16 px
;             = 128 B per band sprite (HW_PBUF, 1 KB) and the upload sends the 128 B twice (the invisible half = a copy).
;   palette = the game palette (PALETTE 9E00h) copied into the sprites' first palette (nextreg 43h = 20h) so the HUD
;             colours and the pistol art use the same indices; transparency index 0 (nextreg 4Bh), as the software sprites.
;   layers  = nextreg 15h = 81h: LoRes on, sprites on, S L U priority (sprites above the LoRes layer), no border sprites.
;   clip    = nextreg 19h: x 0..255, y 0..191 (the full paper; the index is reset through nextreg 1Ch bit 1 first).
; Frame path (game_frame, sprites_next.asm): wb_rmax = 96 (the view takes all 96 rows: horizon 48 is the centre again),
; wb_wclip = 0, draw_weapon is not called; hwspr_frame flips the 12 attribute-3 bytes only when g_wframe or the draw mask
; changed (0 nextreg writes otherwise: ~73 T + call). hud_draw paints into HW_PBUF through hw_pat_addr instead of scr_addr
; and hw_band_upload sends only the band sprites whose field changed (hw_dirty bit per sprite, port 5Bh, 256 outs each).
; Z80N opcodes as db: nextreg r,v = 0EDh,091h,r,v ; nextreg r,a = 0EDh,092h,r
        IF DEFINED HWSPR_B
HW_SPR_W0   equ 0               ; first weapon sprite
HW_SPR_B0   equ 4               ; first band sprite
HW_PAT_FIRE equ 4               ; pattern base of the fire frame (idle = 0)
HW_PAT_B0   equ 8               ; first band pattern
HW_A4       equ 0Ah             ; attribute 4: 8-bit anchor, X scale 2x (bits 4:3 = 01), Y scale 2x (bits 2:1 = 01), Y8 = 0

; ---------------------------------------------------------------------------------------------------------------
; hwspr_init - called once by start (main_b.asm) with interrupts disabled, after the LoRes palette upload and the MMU set-up
; (slot 7 = FLOOR_BANK, restored at the end): sprite palette, transparency, clip window, the 8 weapon patterns from the
; pistol art of 8K bank 27 (idle E000h, fire E400h: 32 columns x 32 B column-major, tools/nx_sprites_b.py), the 12 sprite
; attribute sets, the shadows, then nextreg 15h = 81h. destroys everything
; ---------------------------------------------------------------------------------------------------------------
hwspr_init:
        db 0EDh,091h,43h,20h            ; nextreg 43h,20h : sprites first palette for writing, auto-increment on
        db 0EDh,091h,40h,00h            ; nextreg 40h,0 : index 0
        ld hl,PALETTE
        ld b,0
hwi_pal:
        ld a,(hl)
        inc hl
        db 0EDh,092h,44h                ; nextreg 44h,a : RRRGGGBB
        ld a,(hl)
        inc hl
        db 0EDh,092h,44h                ; nextreg 44h,a : blue lsb
        djnz hwi_pal
        db 0EDh,091h,43h,00h            ; nextreg 43h,0 : back to the ULA palette for writing, first palettes displayed
        db 0EDh,091h,4Bh,00h            ; nextreg 4Bh,0 : sprite transparency index 0 (the software sprites' 0 = skip)
        db 0EDh,091h,1Ch,02h            ; nextreg 1Ch,2 : reset the sprite clip window index
        db 0EDh,091h,19h,00h            ; nextreg 19h : X1 0
        db 0EDh,091h,19h,0FFh           ;               X2 255
        db 0EDh,091h,19h,00h            ;               Y1 0
        db 0EDh,091h,19h,0BFh           ;               Y2 191
        ; ---- weapon patterns 0..7: pattern e <- art pixel (x, y) = base(e) + x*32 + y, 16 rows of 16 (row-major pattern)
        ;      base(e) = E000h + (e & 4)*256 (fire art at +400h) + (e & 1)*512 (right half: columns 16..31) + (e & 2)*8 (rows 16..31)
        db 0EDh,091h,57h,SPR_BANK1      ; slot 7 = 8K bank 27 (pistol art)
        ld e,0
hwi_pat:
        ld bc,303Bh
        out (c),e                       ; pattern index e (and sprite index e: unused, attributes go through nextregs)
        ld a,e
        and 1
        add a,a                         ; (e & 1) * 2 pages
        ld h,a
        ld a,e
        and 4
        add a,h
        add a,0E0h
        ld h,a                          ; H = E0h + (e & 4) + (e & 1)*2
        ld a,e
        and 2
        add a,a
        add a,a
        add a,a
        ld l,a                          ; L = (e & 2) * 8 = row 16 of the art for the lower patterns
        ld d,16                         ; 16 pattern rows
hwi_row:
        push hl
        ld b,16                         ; 16 pixels per row: art columns x = 0..15 of the half, stride 32
        ld c,5Bh
hwi_px:
        ld a,(hl)
        out (c),a                       ; port 5Bh (decoded on the low byte: B is the loop counter, as the Next's otir idiom)
        ld a,l
        add a,32
        ld l,a
        jr nc,hwi_px1
        inc h
hwi_px1:
        djnz hwi_px
        pop hl
        inc hl                          ; next art row
        dec d
        jr nz,hwi_row
        inc e
        ld a,e
        cp 8
        jr nz,hwi_pat
        db 0EDh,091h,57h,FLOOR_BANK     ; slot 7 = floor textures again
        ; ---- band pattern RAM is zero (bank 5 at load): patterns 8..15 are uploaded by hud_draw's first hw_band_upload
        ;      (g_hud_valid = 0 -> hud_band_fill -> hw_dirty = 0FFh); the sprites are visible from the start with pattern
        ;      RAM content = whatever the FPGA had (ZEsarUX: E3h = transparent-ish junk) for the frames before the first
        ;      hud_draw -> upload 8 x 256 B of zeros now so the band is transparent until the HUD paints it.
        ld e,HW_PAT_B0
hwi_zpat:
        ld bc,303Bh
        out (c),e
        ld bc,005Bh                     ; B = 0 -> 256 outs
        xor a
hwi_z:  out (c),a
        djnz hwi_z
        inc e
        ld a,e
        cp HW_PAT_B0+8
        jr nz,hwi_zpat
        ; ---- attributes: 12 sprites from hw_attr_tab (x lo, y, attr2, attr3) + attribute 4 = HW_A4
        ld hl,hw_attr_tab
        xor a
hwi_attr:
        db 0EDh,092h,34h                ; nextreg 34h,a : sprite number
        push af
        ld a,(hl)
        inc hl
        db 0EDh,092h,35h                ; attribute 0: x low 8 bits
        ld a,(hl)
        inc hl
        db 0EDh,092h,36h                ; attribute 1: y low 8 bits
        ld a,(hl)
        inc hl
        db 0EDh,092h,37h                ; attribute 2: palette offset 0, no mirror/rotate, bit 0 = x msb
        ld a,(hl)
        inc hl
        db 0EDh,092h,38h                ; attribute 3: visible | attribute 4 enabled | pattern
        db 0EDh,091h,39h,HW_A4          ; attribute 4: 2x / 2x anchor
        pop af
        inc a
        cp HW_SPR_B0+8
        jr nz,hwi_attr
        ld a,6                          ; shadows: key = mask bits 1,2 set, idle (g_wframe 0 at start) -> matches the table
        ld (hw_key),a
        xor a
        ld (hw_dirty),a
        db 0EDh,091h,15h,81h            ; nextreg 15h,81h : LoRes on, sprites on, S L U, no border sprites
        ret

; (x lo, y, attr2, attr3) per sprite 0..11; attribute 3 = 80h visible | 40h attribute 4 present | pattern
hw_attr_tab:
        db 128,160,0,0C0h+0             ; weapon (48,64)  idle pattern 0
        db 160,160,0,0C0h+1             ; weapon (64,64)
        db 128,192,0,0C0h+2             ; weapon (48,80)
        db 160,192,0,0C0h+3             ; weapon (64,80)
        db  32,208,0,0C0h+HW_PAT_B0+0   ; band (0,88)
        db  64,208,0,0C0h+HW_PAT_B0+1   ; band (16,88)
        db  96,208,0,0C0h+HW_PAT_B0+2   ; band (32,88)
        db 128,208,0,0C0h+HW_PAT_B0+3   ; band (48,88)
        db 160,208,0,0C0h+HW_PAT_B0+4   ; band (64,88)
        db 192,208,0,0C0h+HW_PAT_B0+5   ; band (80,88)
        db 224,208,0,0C0h+HW_PAT_B0+6   ; band (96,88)
        db   0,208,1,0C0h+HW_PAT_B0+7   ; band (112,88): x = 256 -> x lo 0, attribute 2 bit 0 = x msb

; ---------------------------------------------------------------------------------------------------------------
; hwspr_update - game_frame (sprites_next.asm) computes the key inline once per drawn frame (g_draw_off = 0, after
; walk_frame_b): key = g_draw_mask bits 2 (HUD) and 1 (weapon) | 80h when g_wframe = 1 (fire) - 68 T, and calls this only
; when it differs from hw_key (A = key, HL = hw_key). Rewrites attribute 3 of the 12 sprites (visible iff the mask bit,
; pattern = HW_PAT_FIRE + n for the fire frame): 12 x 2 nextreg writes. destroys A, B, C
; ---------------------------------------------------------------------------------------------------------------
hwspr_update:
        ld (hl),a
        ld c,a
        ; weapon sprites 0..3: attr3 = (bit 1 ? 80h : 0) | 40h | (bit 7 ? 4 : 0) | n
        ld b,40h
        bit 1,c
        jr z,hwf_w1
        set 7,b
hwf_w1: bit 7,c
        jr z,hwf_w2
        set 2,b
hwf_w2: xor a
hwf_wl: db 0EDh,092h,34h                ; nextreg 34h,a : sprite n
        or b
        db 0EDh,092h,38h                ; nextreg 38h,a : attribute 3
        and 3
        inc a
        cp 4
        jr nz,hwf_wl
        ; band sprites 4..11: attr3 = (bit 2 ? 80h : 0) | 40h | (HW_PAT_B0 + i)
        ld b,40h+HW_PAT_B0-HW_SPR_B0    ; + sprite number n (4..11) = pattern 8..15
        bit 2,c
        jr z,hwf_b1
        set 7,b
hwf_b1: ld a,HW_SPR_B0
hwf_bl: db 0EDh,092h,34h                ; nextreg 34h,a : sprite n
        add a,b
        db 0EDh,092h,38h                ; nextreg 38h,a : attribute 3
        sub b
        inc a
        cp HW_SPR_B0+8
        jr nz,hwf_bl
        ret

; ---------------------------------------------------------------------------------------------------------------
; hw_pat_addr - the HUD painters' address function under HWSPR_B (replaces scr_addr): B = row 88..95, A = column 0..127 ->
; HL = HW_PBUF + (row - 88) * 128 + col. HW_PBUF (1 KB, 7C00h..7FFFh) is a LINEAR copy of the band rows 88..95 with the
; screen's 128-byte stride, so hud_next.asm's painters (inc hl along a row) are unchanged; hw_band_upload re-packs the 16-byte
; slices into the 16x16 patterns. keeps B, C, D, E ; destroys A
; ---------------------------------------------------------------------------------------------------------------
hw_pat_addr:
        ld l,a
        ld a,b
        sub HUD_ROW
        srl a                           ; A = (row - 88) >> 1, carry = row & 1
        jr nc,hpa_even
        set 7,l                         ; odd row: + 128 (col < 128: no carry)
hpa_even:
        add a,HW_PBUF/256
        ld h,a
        ret

; ---------------------------------------------------------------------------------------------------------------
; hw_mark_dirty - E = first column, B = width of a field being repainted: set the hw_dirty bits of the band sprites it
; touches (E >> 4 .. (E + B - 1) >> 4; ammo 44..51 and the mouse M 94..97 straddle two). keeps B, C, D, E ; destroys A, HL
; hw_band_upload - after hud_draw: for every set bit i of hw_dirty upload pattern HW_PAT_B0 + i: port 303Bh = index, then
;                  rows 0..7 = 8 x 16 bytes from HW_PBUF + r*128 + i*16 (otir), then the same 8 slices again = pattern rows
;                  8..15 (below the paper, never shown). ~6k T per dirty sprite; game_frame skips the call when hw_dirty = 0.
;                  destroys A, B, C, D, E, HL
; ---------------------------------------------------------------------------------------------------------------
hw_mark_dirty:
        push bc
        ld a,e
        add a,b
        dec a
        rrca
        rrca
        rrca
        rrca
        and 7
        ld c,a                          ; last sprite
        ld a,e
        rrca
        rrca
        rrca
        rrca
        and 7                           ; first sprite
        ld hl,hw_bits
        db 0EDh,031h                    ; add hl,a
        sub c
        neg
        inc a
        ld b,a                          ; count = last - first + 1
        ld a,(hw_dirty)
hmd_l:  or (hl)
        inc hl
        djnz hmd_l
        ld (hw_dirty),a
        pop bc
        ret
hw_bits: db 1,2,4,8,16,32,64,128

hw_band_upload:                         ; entered with A = hw_dirty != 0 (game_frame tests it inline)
        ld d,a
        xor a
        ld (hw_dirty),a
        ld e,HW_PAT_B0
        ld hl,HW_PBUF
hbu_l:  srl d                           ; bit i -> carry
        jr nc,hbu_next
        ld bc,303Bh
        out (c),e                       ; pattern index HW_PAT_B0 + i
        call hbu_half                   ; rows 0..7
        call hbu_half                   ; rows 8..15 = the same bytes (off the paper)
hbu_next:
        ld a,l
        add a,16
        ld l,a                          ; HL -> slice of the next sprite (same row 0)
        inc e
        ld a,e
        cp HW_PAT_B0+8
        jr nz,hbu_l
        ret
hbu_half:
        push hl
        ld a,8
hbh_r:  ld bc,1000h+5Bh                 ; B = 16 bytes, port 5Bh
        otir                            ; HL += 16
        push af
        ld a,l
        add a,128-16
        ld l,a
        jr nc,hbh_1
        inc h
hbh_1:  pop af
        dec a
        jr nz,hbh_r
        pop hl
        ret
hwspr_end:
        ENDIF
