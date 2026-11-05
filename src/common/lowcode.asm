; lowcode.asm - M2.6 P2E (2 Nov 2026): sprite colour marks, in the free tail of the low block (level_data + 1081 .. 0x7FFF).
; RAM page 5 on the 128K as well (fixed at 0x4000..0x7FFF) and no loader writes here: tape / bank-1 level loads are exactly
; 1081 bytes at level_data. tools/build_m25_48.sh gates low_end <= 0x8000.
;
; Marks (state.asm CMIN, 24 x 2 B, cleared by things_init): per byte column c (0..23) of the window, CMIN[2c] = 12 - the first
; cell row that received white sprite pixels this frame (0 = none) and CMX[2c+1] = ink << 4 | last such cell row + 1.
; CMX bit 7 (ds_ink 0x80, set with the ink by blood.asm ds_inkl for corpses) = write that ink WITHOUT BRIGHT (M2.6 blood 3 stain).
; sprites_f.asm records per ray column the rows of its white runs (dc_white -> dc_wlo .. dc_whi) and calls dc_mark once per
; ray column that drew white pixels; attr.asm (attr_write, after COPYBUF) turns the marks into attribute writes and clears them.

; ds_inkl (draw_sprite's ink lookup) lives in ../common/blood.asm since M2.6 blood 1 (3 Nov 2026): it grew by 12 bytes
; for the red flash and this low block had 4 bytes left. INKTAB and ds_ink below stay here.

; dc_white: sprites_f.asm dc_run_l, white run of B rows from buffer row C (B, C, DE, HL kept): widen this ray column's white
; rows. Runs are visited top -> bottom, so the first white run gives dc_wlo and the last one dc_whi. Returns with Z set
; (the caller's white / black branch follows the call).
dc_white:
        ld a,(dc_wlo)
        inc a
        jr nz,dw1              ; 255 = no white run yet in this ray column
        ld a,c
        ld (dc_wlo),a          ; first white row
dw1:    ld a,c
        add a,b
        ld (dc_whi),a          ; end row (exclusive) of the last white run
        cp a                   ; Z
        ret

; dc_mark: sprites_f.asm dc_next, A = dc_wlo + 1 (non-zero: this ray column drew white rows dc_wlo .. dc_whi-1 in byte column
; dc_bcol). Widens CMIN / CMX of that byte column and stores the sprite's ink (vis is drawn far -> near: the nearest wins).
dc_mark:
        dec a
        ld c,a                 ; C = first white row (0..95)
        ld a,255
        ld (dc_wlo),a          ; the next ray column starts with no white rows
        ld a,(ds_ink)
        or a
        ret z                  ; this sprite colours nothing
        ld e,a
        ld a,(dc_bcol)
        add a,a
        add a,CMIN and 255
        ld l,a
        ld h,CMIN/256          ; HL -> CMIN[c] (48 B in one page)
        ld a,c
        rrca
        rrca
        rrca
        and 15                 ; first cell row (0..11)
        ld d,a
        ld a,12
        sub d                  ; 12 - first (1..12): larger = higher on screen
        cp (hl)
        jr c,dm1               ; the stored first row is higher: keep it
        ld (hl),a
dm1:    inc l                  ; HL -> CMX[c]
        ld a,(dc_whi)
        dec a
        rrca
        rrca
        rrca
        and 15                 ; last cell row
        inc a                  ; + 1 (1..12)
        ld d,a
        ld a,(hl)
        and 15
        cp d
        jr nc,dm2              ; the stored last row is lower or equal: keep it
        ld a,d
dm2:    or e                   ; ink of the sprite drawn last (nearest) in this column
        ld (hl),a
        ret

; INKTAB[type and 31] = ink << 4 (0 = keeps the window ink). Enemies (sprites_b.asm THSPR): 1 / 7 imp BRIGHT magenta,
; 2..6 zombie BRIGHT green. Items: 16 health red, 17 ammo yellow, 18 red key, 19 blue key, 20 shield cyan; 21..23 barrel /
; lamp none. Types are < 24 (THSPR has 24 entries); attr_write adds BRIGHT (0x40).
INKTAB: defb 0,0x30,0x40,0x40,0x40,0x40,0x40,0x30
        defb 0,0,0,0,0,0,0,0
        defb 0x20,0x60,0x20,0x10,0x50,0,0,0
ds_ink:  defb 0                ; ink << 4 of the sprite being drawn (0 = none)
dc_bcol: defb 0                ; byte column of the ray column being blitted
dc_wlo:  defb 255              ; first row of white sprite pixels in this ray column (255 = none yet)
dc_whi:  defb 0                ; end row (exclusive) of the last white run in this ray column
msg_clear: defb "LEVEL CLEARED",0   ; M2.8 (3 Nov 2026): hud_message strings of game_d.asm, moved here (23 B) to pay for strafe
msg_dead:  defb "YOU DIED",0
low_end equ $                  ; must stay <= 0x8000 (build gate)
