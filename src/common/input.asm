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
        pop hl
        ret
ir_kb:  ld a,e
        pop hl
        ret

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
