; mouse_next.asm - lane N5 (8 Nov 2026): Kempston / Next PS/2 mouse look + VERTICAL LOOK (y-shear) for edition B.
; Every byte of this file is inside IF DEFINED MOUSE_B (pasmo --equ MOUSE_B=1, tools/nx_build.py --equ); the default build has
; none of it and is byte-identical to the pre-N5 program (build/night/N5_identity.out). Included from main_b.asm in the
; 0A200h block (after hud_next.asm): the main code image ends 139 bytes below PALETTE (9E00h), too little for this file.
; Port of lane M's src/common/input.asm mouse_look (128K) to the Next's 0..1023 angle:
;   X counter port 0FBDFh (8-bit, grows moving right, wraps), Y counter 0FFDFh (8-bit, grows moving UP in ZEsarUX - see
;   N5_live.out), buttons 0FADFh active LOW, b0 RIGHT, b1 LEFT (the classic Kempston quirk), Next wheel bits 4..7 ignored.
;   The Next's PS/2 mouse answers on these ports (next-docs: io-port-system/registers.txt "bit 13 = port fadf,fbdf,ffdf mouse",
;   config.txt "Kempston mouse (kmouse)").  Never auto-detected: floating-bus junk without an interface -> opt_mouse_b defaults 0.
; mouse_look_b  once per rendered frame (main_loop, before read_keys / tick). opt_mouse_b = 0: ret, nothing touched, no port
;               read (28 T). ON: dx = X - mouse_last (signed 8-bit, wraps), (ang:mouse_frac) += dx << MSHIFT_B as one 16-bit
;               value (fraction kept: slow moves accumulate), ang wraps 0..1023 (and 3 on H), g_moved = 1 when the whole part
;               changed (main_loop then calls setup_camera_b before the frame).  dy = Y - mouse_ylast likewise into
;               (horizon_row:vl_frac) += dy << VSHIFT_B, clamped VL_MIN..VL_MAX (set_horizon_b).  Buttons: left -> KEY_FIRE,
;               right -> KEY_USE into the latch mouse_btn; read_keys ORs the latch into g_keys and clears it only in a frame
;               that runs a game step (ticks - g_step_t >= STEP_B), so a click between two steps is never lost.
; look_keys_b   once per frame: I (row 0DFh bit 2, unused by read_keys) toggles opt_mouse_b, one toggle per press (DBNC_B
;               frames released before the next), re-basing both counters on ON so the view does not jump; W (row 0FBh bit 1)
;               = look up (horizon moves down the screen, +1 row/frame), S (row 0FDh bit 1) = look down, E (row 0FBh bit 2) =
;               re-centre to VL_DEF. Doom-style: nothing auto-centres.
; horizon_row   (main_b_vars.inc, word horizon_q8 = row*256 via the zero pad byte below it) is the ONE shear variable: walk_b.asm
;               wb_yproj_r (y_q8 = horizon_q8 - (h - eye) * R), sprites_next.asm feet projection and draw_b.asm dr_row_params
;               (dy = 2*(y - horizon_row) + 1) project through it, so walls, floor/ceiling runs, VOID runs and sprites shift
;               together. The HUD band (rows 88..95, wb_rmax = 88) and the weapon never move: VL_MAX = 80 keeps the horizon
;               above the band.
        IF DEFINED MOUSE_B
MSHIFT_B equ 8                 ; 2^MSHIFT_B / 256 angle units per count: 8 -> 1 unit per count, 1024 counts = one full turn
                               ; (lane M: 2^6/256 = 1/4 of a 256-unit turn per count = 1024 counts/turn: the same feel)
VSHIFT_B equ 7                 ; 2^VSHIFT_B / 256 horizon rows per Y count: 7 -> 1/2 row per count (the 90-degree view is 256
                               ; angle units over 128 columns = 2 counts per pixel sideways; 2 counts per row matches it)
DBNC_B   equ 10                ; frames the I key must be released before the next toggle

mouse_look_b:
        ld a,(opt_mouse_b)
        or a
        ret z                           ; OFF: 13 + 4 + 11 = 28 T, no port read
        ld bc,0FBDFh
        in a,(c)                        ; X counter
        ld hl,mouse_last
        ld e,a
        sub (hl)                        ; dx (signed 8-bit; 7Fh->80h = +1, FFh->00h = +1)
        ld (hl),e
        ld l,a
        rla
        sbc a,a
        ld h,a                          ; HL = dx sign-extended
        rept MSHIFT_B
        add hl,hl                       ; HL = dx * 2^MSHIFT_B (high byte = whole units, low = 1/256 units)
        endm
        ld a,(mouse_frac)
        add a,l
        ld (mouse_frac),a
        ld a,h
        adc a,0                         ; A = whole units to turn (int8) including the fraction carry
        jr z,ml_noturn
        ld e,a
        rla
        sbc a,a
        ld d,a                          ; DE = units sign-extended
        ld hl,(ang)
        add hl,de
        ld a,h
        and 3
        ld h,a                          ; wrap 0..1023
        ld (ang),hl
        ld a,1
        ld (g_moved),a                  ; main_loop: setup_camera_b before the frame
ml_noturn:
        ld b,0FFh                       ; C = 0DFh still
        in a,(c)                        ; Y counter
        ld hl,mouse_ylast
        ld e,a
        sub (hl)                        ; dy (signed 8-bit)
        ld (hl),e
        ld l,a
        rla
        sbc a,a
        ld h,a
        rept VSHIFT_B
        add hl,hl                       ; HL = dy * 2^VSHIFT_B
        endm
        ld a,(vl_frac)
        add a,l
        ld (vl_frac),a
        ld a,(horizon_row)
        adc a,h                         ; mouse up (Y grows) -> look up -> the horizon moves DOWN the screen (+rows)
        call set_horizon_b
        ld b,0FAh
        in a,(c)                        ; buttons, active low: b0 right, b1 left (wheel bits 4..7 fall off the two rra)
        ld hl,mouse_btn
        rra                             ; carry = right button (1 = up)
        jr c,ml_r
        set KB_USE,(hl)                 ; right -> use/open
ml_r:   rra
        jr c,ml_l
        set KB_FIRE,(hl)                ; left -> fire; latched until read_keys consumes it in a frame with a game step
ml_l:   ret

; look_keys_b - I toggle (debounced), W / S / E vertical look. destroys A, C, HL
look_keys_b:
        ld a,0DFh
        in a,(0FEh)                     ; P O I U Y
        bit 2,a                         ; I
        ld hl,mouse_dbnc
        jr nz,lk_i_up
        ld a,(hl)
        or a
        jr nz,lk_vert                   ; held, or released for less than DBNC_B frames: no toggle
        ld (hl),DBNC_B
        ld a,(opt_mouse_b)
        xor 1
        ld (opt_mouse_b),a
        jr z,lk_vert
        ld bc,0FBDFh                    ; ON: re-base both counters so the first frame does not jump
        in a,(c)
        ld (mouse_last),a
        ld b,0FFh
        in a,(c)
        ld (mouse_ylast),a
        jr lk_vert
lk_i_up:
        ld a,(hl)
        or a
        jr z,lk_vert
        dec (hl)                        ; counts down only while the key is released
lk_vert:
        ld a,0FBh
        in a,(0FEh)                     ; Q W E R T
        ld c,a
        ld a,(horizon_row)
        bit 1,c                         ; W = look up: horizon down the screen
        jr nz,lk_no_w
        inc a
lk_no_w:
        bit 2,c                         ; E = re-centre
        jr nz,lk_no_e
        ld a,VL_DEF
lk_no_e:
        ld c,a
        ld a,0FDh
        in a,(0FEh)                     ; A S D F G
        bit 1,a                         ; S = look down
        ld a,c
        jr nz,set_horizon_b
        dec a
        ; fall into set_horizon_b
; set_horizon_b: A = wanted horizon row (int8 arithmetic: -48..144 possible) -> clamped VL_MIN..VL_MAX into horizon_row. destroys A
set_horizon_b:
        cp VL_MIN
        jr c,sh_min
        cp VL_MAX+1
        jr c,sh_ok
        cp 128
        jr c,sh_max                     ; VL_MAX+1..127 -> VL_MAX
sh_min: ld a,VL_MIN                     ; < VL_MIN, or negative (128..255)
        jr sh_ok
sh_max: ld a,VL_MAX
sh_ok:  ld (horizon_row),a
        ret
mouse_next_end:
        ENDIF
