; input.asm - Kill'em all, keyboard + Kempston input (lane T2). Hand Z80, pasmo. Contracts: ARCH_M2.md.
; Externals (state.asm): opt_joy (0 keyboard, 1 Kempston), in_break (written here).
;
; in_read      -> A = action bits: b0 forward, b1 back, b2 turn left, b3 turn right, b4 fire, b5 use/open,
;                 b6 strafe left, b7 strafe right. Keyboard half-rows via the in_keys table (always) ORed with the
;                 Kempston byte (port 31: b0 right, b1 left, b2 down, b3 up, b4 fire, active high) mapped through
;                 in_joytab when opt_joy <> 0; a port-31 value >= 0x20 (no interface / floating bus) is ignored.
;                 in_break = 1 while CAPS+SPACE are both held, else 0.
;                 Preserves BC, HL (T1's stub does too); destroys AF, DE. Unrolled, no loops:
;                 530 T keyboard, 589 T Kempston, 562 T Kempston-absent (counted; tools/test_frontend.py measures).
; in_keys      8 x [port high byte, bit mask] in action-bit order, defaults Q A O P SPACE M Z X (M2.3: SPACE fires, M opens). 16-byte aligned
;                 (in_read walks it with inc l); the padding is counted in the size numbers of the report.
; in_scan      -> Z: no key down. NZ: B = port high byte, C = single bit mask, E = key index 0..39 (row*5+bit) of the
;                 lowest bit of the first half-row with a key down (rows FE FD FB F7 EF DF BF 7F). Destroys AF BC E.
; in_wait_key  -> waits until every key is up, then for one key: press, 22 ms debounce re-scan (same key), release.
;                 Returns NC: B = port high byte, C = mask, A = name code. Returns C (carry set) when CAPS+SPACE
;                 (BREAK) were held at any time while the key was down -> the caller aborts. Destroys AF BC DE HL.
;                 Blocking, no HALT, interrupts untouched. Joystick is not scanned here (keys only).
; in_keyname   B = port high byte, C = mask -> A = name code, 0 if the pair is not one single key. Destroys AF BC DE HL.
; name codes:  ASCII for letters/digits; 1 = SPACE, 2 = ENTER, 3 = CAPS SHIFT, 4 = SYMBOL SHIFT.

in_begin:
in_read:
        push hl
        ld hl,in_keys
        rept 7
        ld a,(hl)              ; port high byte
        inc l
        ld d,(hl)              ; mask
        inc l
        in a,(0xFE)
        and d
        cp d                   ; carry = key down (row bit low -> A = 0 < mask)
        rr e
        endm
        ld a,(hl)
        inc l
        ld d,(hl)
        in a,(0xFE)
        and d
        cp d
        rr e                   ; E = 8 action bits, first table entry in b0
        ld a,0x7F
        in a,(0xFE)            ; b0 = SPACE
        ld d,a
        ld a,0xFE
        in a,(0xFE)            ; b0 = CAPS
        or d
        cpl
        and 1
        ld (in_break),a        ; 1 = BREAK held
        ld a,(opt_joy)
        or a
        jr z,ir_kb
        ld a,31
        in a,(31)              ; Kempston: b0 R, b1 L, b2 D, b3 U, b4 fire
        cp 0x20
        jr nc,ir_kb            ; bits 5..7 set: no interface answering -> ignore
        add a,low in_joytab
        ld l,a
        ld h,high in_joytab    ; table never crosses a page (guarded below)
        ld a,(hl)
        or e
        IF DEFINED MOUSE
        ld e,a
ir_kb:  ld a,(opt_mouse)       ; lane M (128K/Next): mouse ON -> OR the click latch (b4 fire, b5 use) into the result, clear it
        or a
        ld a,e
        jr z,ir_nm
        ld hl,mouse_btn
        or (hl)
        ld (hl),0
ir_nm:  pop hl
        ret
        ELSE
        pop hl
        ret
ir_kb:  ld a,e
        pop hl
        ret
        ENDIF

        IF DEFINED MOUSE
; ---------------------------------------------------------------- lane M (5 Nov 2026): mouse look, 128K / Next builds only
; mouse_look   called once per RENDERED frame by the main loop (kea48.asm `call mouse_look` before `call steps`), not per
;              game step: latency = one frame. opt_mouse = 0: ret, nothing touched (28 T). Else: Kempston mouse X counter
;              (port 0FBDFh, 8-bit, grows moving right; the Next's PS/2 mouse answers on the same ports): dx = X - mouse_last
;              (signed, wraps), mouse_last = X; (angle:mouse_frac) += dx * MSENS as one 16-bit value, so slow movements
;              accumulate in the fraction and the integer part turns the view (angle + = right, like the P key). With GLIDE
;              the step-start angle oang moves by the same amount so the camera shows the turn at once (both lerp ends shift).
;              Buttons (port 0FADFh, active low, b0 RIGHT, b1 LEFT - the classic Kempston quirk; Next wheel bits ignored):
;              left -> fire (action b4), right -> use/open (b5), ORed into the latch mouse_btn; in_read ORs the latch into
;              its result and clears it, so a click between two game steps is never lost and fire/door cooldowns stay in
;              game_tick. Mouse Y (0FFDFh) is ignored: no pitch in this engine. Destroys AF BC HL E. 28 T when OFF,
;              330..350 T when ON (tools/m_mouse_test.py measures both), once per frame.
;              Never auto-detected: a Spectrum without the interface returns floating-bus junk on these ports.
MSHIFT  equ 6                  ; sensitivity: 2^MSHIFT / 256 angle units per count -> 6 = 1/4 unit, 1024 counts = one full turn
mouse_look:
        ld a,(opt_mouse)
        or a
        ret z
        ld bc,0FBDFh
        in a,(c)               ; X counter
        ld hl,mouse_last
        ld e,a
        sub (hl)               ; dx (signed 8-bit, wraps correctly: 7Fh->80h = +1, FFh->00h = +1)
        ld (hl),e
        ld l,a
        rla
        sbc a,a
        ld h,a                 ; HL = dx sign-extended
        rept MSHIFT
        add hl,hl              ; HL = dx * 2^MSHIFT (s16: high byte = whole angle units, low = 1/256 units)
        endm
        ld a,(mouse_frac)
        add a,l
        ld (mouse_frac),a
        ld a,h
        adc a,0                ; A = whole units to turn, including the fraction carry
        ld h,a
        ld a,(angle)
        add a,h
        ld (angle),a
        IF DEFINED GLIDE
        ld a,(oang)            ; game_d.asm glide: the step-start angle turns too -> no glide lag on mouse turns
        add a,h
        ld (oang),a
        ENDIF
        ld b,0FAh              ; C = 0DFh still
        in a,(c)               ; buttons, active low: b0 right, b1 left
        ld hl,mouse_btn
        rra                    ; carry = right button bit (1 = up)
        jr c,ml_r
        set 5,(hl)             ; right -> use/open (action b5)
ml_r:   rra
        jr c,ml_l
        set 4,(hl)             ; left -> fire (action b4); latched until in_read consumes it
ml_l:   ret
mouse_last: defb 0             ; X counter at the last frame
mouse_frac: defb 0             ; 1/256 angle units not yet turned
mouse_btn:  defb 0             ; click latch (action bits b4 / b5)
        ENDIF

; ---------------------------------------------------------------- scanning (menu / redefine; not time critical)
in_scan:
        ld b,0xFE              ; half rows FE FD FB F7 EF DF BF 7F (rlc b walks them, carry clears after 7F)
        ld e,0
is_row: ld a,b
        in a,(0xFE)
        cpl
        and 0x1F
        jr nz,is_hit
        ld a,e
        add a,5
        ld e,a
        rlc b
        jr c,is_row
        xor a                  ; Z = nothing down
        ret
is_hit: ld c,a
        neg
        and c                  ; lowest set bit
        ld c,a
is_bit: rra
        jr c,is_fin
        inc e
        jr is_bit
is_fin: ld a,c
        or a                   ; NZ
        ret

in_wait_key:
        call in_scan
        jr nz,in_wait_key      ; wait until every key is up
wk_prs: call in_scan
        jr z,wk_prs            ; wait for a key
        ld h,e                 ; remember the key index
        ld de,3000             ; 3000 x 26 T = 78,000 T (22 ms) debounce
wk_dly: dec de
        ld a,d
        or e
        jr nz,wk_dly
        call in_scan
        jr z,wk_prs            ; bounced off -> restart
        ld a,e
        cp h
        jr nz,wk_prs           ; a different key -> restart
        push bc                ; B = port high byte, C = mask of the accepted key
wk_hld: ld a,0x7F
        in a,(0xFE)
        ld d,a
        ld a,0xFE
        in a,(0xFE)
        or d
        and 1
        jr z,wk_brk            ; CAPS+SPACE both down -> abort
        call in_scan
        jr nz,wk_hld           ; accepted on release of every key
        pop bc
        ld e,h
        ld d,0
        ld hl,in_names
        add hl,de
        ld a,(hl)
        or a                   ; NC
        ret
wk_brk: pop bc
        scf
        ret

in_keyname:
        ld e,0
kn_row: rr b
        jr nc,kn_bit
        ld a,e
        add a,5
        ld e,a
        cp 40
        jr c,kn_row
        xor a                  ; no zero bit in the port byte
        ret
kn_bit: ld d,5
kn_b1:  rr c
        jr c,kn_ok
        inc e
        dec d
        jr nz,kn_b1
        xor a                  ; mask has no bit in 0..4
        ret
kn_ok:  ld hl,in_names
        ld d,0
        add hl,de
        ld a,(hl)
        ret

; ---------------------------------------------------------------- data
        defs (16 - ($ AND 15)) AND 15   ; in_keys 16-byte aligned (see in_read)
in_keys:
        defb 0xFB,0x01         ; Q  forward
        defb 0xFD,0x01         ; A  back
        defb 0xDF,0x02         ; O  turn left
        defb 0xDF,0x01         ; P  turn right
        defb 0x7F,0x01         ; SPACE fire (M2.3; was M)
        defb 0x7F,0x04         ; M  use/open (M2.3; was SPACE)
        defb 0xFE,0x02         ; Z  strafe left
        defb 0xFE,0x04         ; X  strafe right
        if ($ AND 255) GT 224
        defs 256 - ($ AND 255)          ; keep in_joytab inside one 256-byte page
        endif
in_joytab:                     ; Kempston byte (b0 R b1 L b2 D b3 U b4 F) -> action bits (b0 fwd b1 back b2 L b3 R b4 fire)
        defb 0x00,0x08,0x04,0x0C,0x02,0x0A,0x06,0x0E,0x01,0x09,0x05,0x0D,0x03,0x0B,0x07,0x0F
        defb 0x10,0x18,0x14,0x1C,0x12,0x1A,0x16,0x1E,0x11,0x19,0x15,0x1D,0x13,0x1B,0x17,0x1F
in_names:                      ; key index = row*5 + bit; rows FE FD FB F7 EF DF BF 7F
        defb 3,"ZXCV"          ; CAPS Z X C V
        defb "ASDFG"
        defb "QWERT"
        defb "12345"
        defb "09876"
        defb "POIUY"
        defb 2,"LKJH"          ; ENTER L K J H
        defb 1,4,"MNB"         ; SPACE SYM M N B
in_end:
