; frontend.asm - Kill'em all, front end (lane T2). Hand Z80, pasmo. Contracts: ARCH_M2.md.
; Externals: state.asm (opt_music opt_sfx opt_detail opt_joy in_break), input.asm (in_read in_keys in_scan
;            in_wait_key in_keyname), T3 snd_fx / snd_menu_tick, T1 hud_message. Font: ROM (0 bytes RAM), see fe_font.
;
; fe_run      main menu over whatever is on screen: pixel rows 128..191 and attribute rows 16..23 are cleared and used,
;             rows 0..15 are never touched. Items: START GAME, MUSIC, SOUND FX, DETAIL, CONTROLS, REDEFINE KEYS
;             (+ a key hint on row 23). M2.2: the FPS COUNTER item is gone (no fps line in the game any more). Returns A = 0 when START GAME is chosen, options written to state.asm.
; fe_pause    same menu for the in-game BREAK: RESUME replaces START GAME, QUIT TO MENU is added (7 rows, no hint).
;             Returns A = 0 RESUME, A = 1 QUIT TO MENU. (Extension to the contract: ARCH only names fe_run.)
;             Both return with every key released; the caller redraws rows 16..23 (HUD) itself - nothing is saved.
; fe_message  HL = text -> hud_message (forward only).
; Controls:   Q / 7 / joystick up / the forward key = up, A / 6 / joystick down / the back key = down, SPACE / ENTER /
;             fire / use = select or toggle; everything edge-triggered, BREAK (CAPS+SPACE) is swallowed. Each frame:
;             ei, halt (needs the IM2 ISR of the caller), snd_menu_tick, keys. snd_fx 6 on every move / toggle.
; Redefine:   8 actions in 2 columns (rows 16..19), prompt on row 21, "BREAK = CANCEL" on row 23. Keys are collected
;             into fe_tmpk and copied to in_keys only after the 8th key; BREAK leaves in_keys unchanged.
; Attributes: FE_ANORM plain rows, FE_AHI bright bar on the current row, FE_AFLASH on the chosen cell (value text of
;             an option / label of an action / key name being redefined). The FLASH bit does the blinking (no CPU).
; Registers:  all routines destroy AF BC DE HL; no IX/IY/alternates. Stack use <= 8 bytes. T-states: tools/test_frontend.py.

FE_ANORM equ 0x07               ; black paper, white ink
FE_AHI   equ 0x4F               ; bright, blue paper, white ink
FE_AFLASH equ 0xCE              ; flash, bright, blue paper, yellow ink
FE_PIX   equ 0x5000             ; pixel address of attribute row 16, line 0
FE_ATTR  equ 0x5A00             ; attribute address of row 16
        IF DEFINED MOUSE
FE_N     equ 7                  ; lane M (128K/Next, pasmo --equ MOUSE=1): main menu items incl. MOUSE: OFF/ON = rows 16..22
        ELSE                    ; + hint row 23; pause menu FE_N+1 = 8 rows 16..23 (it has no hint). QUIT TO MENU is item FE_N,
FE_N     equ 6                  ; RESUME is string FE_N+1 of fe_s_items. Without MOUSE every byte below is as before (6/7/6/7).
        ENDIF

fe_begin:
fe_run: xor a
        ld (fe_mode),a
        ld a,FE_N
        jr fe_menu
fe_pause:
        ld a,1
        ld (fe_mode),a
        ld a,FE_N+1
fe_menu:
        ld (fe_count),a
        xor a
        ld (fe_cur),a
fe_menu_redraw:
        call fe_draw_all
        ld a,0xFF
        ld (fe_prev),a         ; nothing counts as newly pressed until it has been released once
fe_loop:
        ei
        halt
fe_frame:
        call snd_menu_tick
        call fe_keys           ; A = b0 up, b1 down, b2 select; in_break updated
        ld e,a
        ld d,0
        ld a,(in_break)
        or a
        ld a,0xFF
        jr nz,fe_setp          ; BREAK held: swallow everything (SPACE is part of it)
        ld a,(fe_prev)
        cpl
        and e                  ; newly pressed bits
        ld d,a
        ld a,e
fe_setp:
        ld (fe_prev),a
        ld a,d
        rra
        jr c,fe_up
        rra
        jr c,fe_down
        rra
        jr c,fe_sel
        jr fe_loop

fe_up:  ld a,(fe_cur)
        or a
        jr nz,fup1
        ld a,(fe_count)
fup1:   dec a
        jr fe_move
fe_down:
        ld a,(fe_cur)
        inc a
        ld hl,fe_count
        cp (hl)
        jr c,fe_move
        xor a
fe_move:
        ld hl,fe_cur
        ld e,(hl)              ; old row
        ld (hl),a              ; new row
        push de
        call fe_draw_row       ; new row gets the bar
        pop de
        ld a,e
        call fe_draw_row       ; old row goes plain
        call fe_tick
        jr fe_loop

fe_sel: ld a,(fe_cur)
        or a
        jr z,fe_exit0          ; START GAME / RESUME
        cp 5
        jp z,fe_redef
        cp FE_N
        jr z,fe_quit
        ld c,a
        add a,a
        add a,c
        ld l,a
        ld h,0
        ld bc,fe_items+1
        add hl,bc
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                 ; HL = option byte
        ld a,(hl)
        xor 1
        ld (hl),a
        ld a,(fe_cur)
        call fe_draw_row
        call fe_tick
        jr fe_loop
fe_quit:
        ld a,1
        jr fe_exit
fe_exit0:
        xor a
fe_exit:
        push af
fex1:   call in_scan
        jr nz,fex1             ; return only once every key is up
        IF DEFINED MOUSE
        ld a,(opt_mouse)       ; lane M: mouse ON -> re-base the X counter here (START / RESUME / QUIT), so the mouse moved
        or a                   ; while the menu was up (mouse_look is not called there) does not turn the view on the first frame
        jr z,fex2
        ld bc,0FBDFh
        in a,(c)
        ld (mouse_last),a
fex2:
        ENDIF
        pop af
        ret

fe_tick:
        ld a,6
        jp snd_fx

fe_message:
        jp hud_message

; ---------------------------------------------------------------- menu keys
fe_keys:                ; -> A: b0 up, b1 down, b2 select (level, not edge). Calls in_read (updates in_break).
        call in_read
        ld e,a
        and 3                  ; forward / back (redefined keys and joystick up / down)
        ld d,a
        ld a,e
        and 0x30               ; fire / use (and joystick fire)
        jr z,fk1
        set 2,d
fk1:    ld a,0xFB
        in a,(0xFE)
        rra
        jr c,fk2
        set 0,d                ; Q
fk2:    ld a,0xFD
        in a,(0xFE)
        rra
        jr c,fk3
        set 1,d                ; A
fk3:    ld a,0xEF
        in a,(0xFE)
        bit 3,a
        jr nz,fk4
        set 0,d                ; 7 (cursor up)
fk4:    bit 4,a
        jr nz,fk5
        set 1,d                ; 6 (cursor down)
fk5:    ld a,0x7F
        in a,(0xFE)
        rra
        jr c,fk6
        set 2,d                ; SPACE
fk6:    ld a,0xBF
        in a,(0xFE)
        rra
        jr c,fk7
        set 2,d                ; ENTER
fk7:    ld a,d
        ret

; ---------------------------------------------------------------- drawing
fe_draw_all:            ; clears rows 16..23 and draws every item (+ the hint on row 23 in the main menu)
        call fe_clr_bottom
        xor a
fda1:   push af
        call fe_draw_row
        pop af
        inc a
        ld hl,fe_count
        cp (hl)
        jr c,fda1
        ld a,(fe_mode)
        or a
        ret nz
        ld hl,fe_s_hint
        ld de,FE_PIX+7*32
        jp fe_print

fe_draw_row:            ; A = item index: clears the pixel row, prints label (+ value), sets the row's attributes
        ld (fe_row),a
        rrca
        rrca
        rrca                   ; A*32 (index < 8)
        ld e,a
        ld d,high FE_PIX
        call fe_clr_row
        inc e
        inc e                  ; column 2
        ld a,e
        ld (fe_vcol),a         ; flashing cells start at the label (action items)
        ld a,(fe_row)
        or a
        jr nz,fdr1
        ld a,(fe_mode)
        or a
        jr z,fdr1              ; main menu: item 0 = START GAME
        ld a,FE_N+1            ; pause menu: RESUME
fdr1:   ld hl,fe_s_items
        call fe_nth
        call fe_print
        ld a,(fe_row)
        ld c,a
        add a,a
        add a,c                ; *3
        ld l,a
        ld h,0
        ld bc,fe_items
        add hl,bc
        ld a,(hl)              ; value pair index
        inc hl
        ld c,(hl)
        inc hl
        ld h,(hl)
        ld l,c                 ; HL = option address (0 = action)
        ld c,a
        ld a,h
        or l
        jr z,fdr2
        ld a,e
        ld (fe_vcol),a         ; option: flashing cells = the value text
        ld a,(hl)
        and 1
        add a,c
        ld hl,fe_s_vals
        call fe_nth
        call fe_print
fdr2:   ld a,e
        ld (fe_vend),a
        ld a,(fe_row)
        rrca
        rrca
        rrca
        ld l,a
        ld h,high FE_ATTR
        ld a,(fe_cur)
        ld c,a
        ld a,(fe_row)
        cp c
        ld a,FE_ANORM
        ld b,32
        jp nz,fe_attr          ; not the current row: plain bar
        ld a,FE_AHI
        call fe_attr
        ld a,(fe_vcol)
        ld l,a
        ld a,(fe_vend)
        sub l
        ld b,a
        ld a,FE_AFLASH
        jp fe_attr

fe_attr:                ; HL = attribute address, B = cells, A = attribute (A preserved)
        ld (hl),a
        inc l
        djnz fe_attr
        ret

fe_clr_row:             ; DE = pixel address (line 0, column 0 of a char row): zero 8 lines x 32 bytes, keeps DE
        push de
        ld b,8
fcr1:   ld h,d
        ld l,e
        ld c,b
        ld b,32
        xor a
fcr2:   ld (hl),a
        inc l
        djnz fcr2
        ld b,c
        inc d
        djnz fcr1
        pop de
        ret

fe_clr_bottom:          ; pixel rows 128..191 = 0, attribute rows 16..23 = FE_ANORM
        ld hl,FE_PIX
        ld de,FE_PIX+1
        ld bc,2047
        ld (hl),0
        ldir
        ld hl,FE_ATTR
        ld de,FE_ATTR+1
        ld bc,255
        ld (hl),FE_ANORM
        ldir
        ret

fe_nth:                 ; HL = sequential 0-terminated strings, A = index -> HL = start of string A
        or a
        ret z
        ld b,a
fn1:    ld a,(hl)
        inc hl
        or a
        jr nz,fn1
        djnz fn1
        ret

fe_print:               ; HL = 0-terminated string, DE = screen address -> DE advanced past the text
        ld a,(hl)
        or a
        ret z
        inc hl
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl              ; code*8
        ld bc,(fe_font)
        add hl,bc
        ld b,8
fp1:    ld a,(hl)
        ld (de),a
        inc hl
        inc d
        djnz fp1
        ld a,d
        sub 8
        ld d,a
        inc e
        pop hl
        jr fe_print

fe_prkey:               ; A = key name code (ASCII; 1..4 = SPC ENT CAP SYM; 0 = unknown), DE = screen address: 3 cells
        or a
        jr nz,fpk0
        ld a,'?'
fpk0:   cp 32
        jr c,fpk1
        ld (fe_kbuf),a
        ld hl,fe_kbuf
        jp fe_print
fpk1:   dec a
        add a,a
        add a,a
        ld hl,fe_s_knames
        add a,l
        ld l,a
        jr nc,fpk2
        inc h
fpk2:   jp fe_print

; ---------------------------------------------------------------- redefine keys
fe_redef:
        ld hl,in_keys
        ld de,fe_tmpk
        ld bc,16
        ldir
        call fe_clr_bottom
        ld hl,fe_s_rd1
        ld de,FE_PIX+5*32      ; row 21
        call fe_print
        ld hl,fe_s_rd2
        ld de,FE_PIX+7*32      ; row 23
        call fe_print
        xor a
frd1:   ld (fe_row),a
        call fe_rd_entry
        ld a,(fe_row)
        inc a
        cp 8
        jr c,frd1
        xor a
frd2:   ld (fe_row),a
        ld a,FE_AHI
        call fe_rd_attr
        call in_wait_key       ; B = port high byte, C = mask, A = name; carry = BREAK
        jr c,frd_abort
        push af
        ld a,(fe_row)
        add a,a
        ld hl,fe_tmpk
        add a,l
        ld l,a
        jr nc,frd3
        inc h
frd3:   ld (hl),b
        inc hl
        ld (hl),c
        ld a,(fe_row)
        call fe_rd_pos
        ld a,e
        add a,11
        ld e,a
        pop af
        call fe_prkey
        call fe_tick
        ld a,FE_ANORM
        call fe_rd_attr
        ld a,(fe_row)
        inc a
        cp 8
        jr c,frd2
        ld hl,fe_tmpk
        ld de,in_keys
        ld bc,16
        ldir
frd_abort:
        jp fe_menu_redraw

fe_rd_pos:              ; A = entry 0..7 -> DE = pixel address of its label (rows 16..19, column 0 or 16); A, BC kept
        ld d,a
        and 3
        rrca
        rrca
        rrca                   ; (i AND 3)*32
        ld e,a
        ld a,d
        and 4
        add a,a
        add a,a                ; 16 for entries 4..7
        add a,e
        ld e,a
        ld a,d
        ld d,high FE_PIX
        ret

fe_rd_entry:            ; (fe_row) = entry: prints the action name and the key currently held in fe_tmpk
        ld a,(fe_row)
        call fe_rd_pos
        push de
        ld hl,fe_s_acts
        call fe_nth
        call fe_print
        pop de
        ld a,e
        add a,11
        ld e,a
        ld a,(fe_row)
        add a,a
        ld hl,fe_tmpk
        add a,l
        ld l,a
        jr nc,fre1
        inc h
fre1:   ld b,(hl)
        inc hl
        ld c,(hl)
        push de
        call in_keyname        ; A = name code (destroys DE)
        pop de
        jp fe_prkey

fe_rd_attr:             ; A = attribute for the 16 cells of entry (fe_row); FE_AHI also flashes the 3 key-name cells
        ld c,a
        ld a,(fe_row)
        call fe_rd_pos
        ld h,high FE_ATTR
        ld l,e
        ld a,c
        ld b,16
        call fe_attr
        cp FE_AHI
        ret nz
        ld a,l
        sub 5                  ; name cells = label + 11..13
        ld l,a
        ld b,3
        ld a,FE_AFLASH
        jp fe_attr

; ---------------------------------------------------------------- data
fe_items:               ; per item: value pair index into fe_s_vals, dw option byte (0 = action)
        defb 0
        defw 0                 ; START GAME / RESUME
        defb 0
        defw opt_music
        defb 0
        defw opt_sfx
        defb 2
        defw opt_detail
        defb 4
        defw opt_joy
        defb 0
        defw 0                 ; REDEFINE KEYS
        IF DEFINED MOUSE
        defb 0
        defw opt_mouse         ; lane M: MOUSE: OFF/ON (pair 0), item 6; QUIT TO MENU becomes item 7 (128K/Next builds only)
        ENDIF
        defb 0
        defw 0                 ; QUIT TO MENU
fe_s_items:
        defb "START GAME",0
        defb "MUSIC: ",0
        defb "SOUND FX: ",0
        defb "DETAIL: ",0
        defb "CONTROLS: ",0
        defb "REDEFINE KEYS",0
        IF DEFINED MOUSE
        defb "MOUSE: ",0
        ENDIF
        defb "QUIT TO MENU",0
        defb "RESUME",0
fe_s_vals:
        defb "OFF",0,"ON",0,"LOW",0,"HIGH",0,"KEYBOARD",0,"KEMPSTON",0
fe_s_acts:
        defb "FORWARD",0,"BACK",0,"TURN LEFT",0,"TURN RIGHT",0,"FIRE",0,"USE/OPEN",0,"STRAFE L",0,"STRAFE R",0
fe_s_knames:
        defb "SPC",0,"ENT",0,"CAP",0,"SYM",0
fe_s_hint:
        defb "Q/A/CURSORS MOVE  SPACE SELECTS",0
fe_s_rd1:
        defb "PRESS THE KEY FOR EACH ACTION",0
fe_s_rd2:
        defb "BREAK (CAPS+SPACE) = CANCEL",0
fe_font: defw 15616-256         ; font base - 256 (code*8 indexes it directly); 128K build may repoint it
fe_mode: defb 0                 ; 0 main menu, 1 pause menu
fe_count: defb 6
fe_cur:  defb 0
fe_prev: defb 0
fe_row:  defb 0
fe_vcol: defb 0
fe_vend: defb 0
fe_kbuf: defb 32,32,32,0
; fe_tmpk: 16 B -> DRAM (state.asm, M2.2)
fe_end:
