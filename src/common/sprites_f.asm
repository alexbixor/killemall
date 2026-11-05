; sprites_f.asm (T1) - per-column sprite blit, M2.5 masked blit (one ink for the whole window: zero attribute clash).
; Column c (0..63): zbuf[c] <= hv (no nearer wall) -> visible. Buffer byte column 3*(c>>3) + ADJTAB[c&7] (M2.5C, 3-px rays),
; slot bits SLOTM[c&7]. Each run
; (v0..v1 source rows, code 1 black / 3 white; tools/gen48.py runs16 adds a 1-px black halo round the ink) maps through
; ROWTAB to rows r0..r1 and goes through the SCHAIN with n = r1 - r0 rows: B = or-bits (slot for white, 0 for black),
; C = and-mask (255 for white, not slot for black). Transparent runs leave the wall pixels. No attribute work at all.
ds_cols:
        ld a,(ds_c)
        ld c,a
        ld a,(ds_cend)
        sub c
        ret z
        ret c
        ld (ds_cnt),a
dc_l:   ld a,(ds_c)
        ld hl,zbuf
        add a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,(hl)              ; wall virtual height in this column (0 = none)
        ld hl,ds_hv
        cp (hl)
        jr z,dc_vis            ; equal (both at the 128 cap) -> sprite in front
        jp nc,dc_next          ; wall nearer -> skip column
dc_vis:
; source column u = uacc >> 8 (0..15) -> run list pointer
        ld a,(ds_uacc+1)
        and 15
        add a,a
        ld hl,(ds_spr)
        add a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (dc_run),hl
; buffer address (M2.5C): DE = COLBASE[3*(c>>3) + ADJTAB[c&7]] ; slot mask SLOTM[c&7]
        ld a,(ds_c)
        ld c,a
        and 7
        ld b,a                 ; B = c & 7
        add a,ADJTAB and 255
        ld l,a
        ld h,ADJTAB/256
        ld a,c
        rrca
        rrca
        rrca
        and 7                  ; c >> 3
        ld e,a
        add a,a
        add a,e
        add a,(hl)             ; bytecol
        ld (dc_bcol),a         ; M2.6 P2E: byte column of this ray column (dc_mark)
        add a,a
        add a,COLBASE and 255
        ld l,a
        ld h,COLBASE/256
        ld e,(hl)
        inc l
        ld d,(hl)
        ld (dc_buf),de
        ld a,b
        add a,SLOTM and 255
        ld l,a
        ld h,SLOTM/256
        ld a,(hl)
        ld (dc_slot),a
        xor a
        ld (dc_v0),a           ; previous run end (source row)
dc_run_l:
        ld hl,(dc_run)
        ld a,(hl)
        or a
        jp z,dc_next
        inc hl
        ld (dc_run),hl
        ld c,a
        and 7
        ld (dc_code),a         ; 0 transparent, 1 black, 3 white
        ld a,c
        rrca
        rrca
        rrca
        and 31                 ; v_end (1..24)
        ld c,a
        ld hl,dc_v0
        ld l,(hl)              ; L = v0
        ld (dc_v0),a           ; next run starts at v_end
        ld a,(dc_code)
        or a
        jr z,dc_run_l          ; transparent run
        ld h,ROWTAB/256
        ld a,(hl)              ; r0 = ROWTAB[v0]
        ld l,c
        ld b,(hl)              ; r1 = ROWTAB[v_end]
        ld c,a
        ld a,b
        sub c
        jr z,dc_run_l          ; no rows
        ld b,a                 ; B = n rows
        ld a,(dc_code)
        cp 3
        call z,dc_white        ; M2.6 P2E: white run of B rows from row C -> dc_wlo / dc_whi (lowcode.asm, B C HL DE kept)
        ld hl,(dc_buf)
        ld a,l
        add a,c
        ld l,a
        jr nc,$+3
        inc h                  ; M2.5C: 16-bit (stride 96, a column may cross a page)
        ex de,hl               ; DE = BUF column + r0
        ld a,b
        add a,a
        add a,CHJ and 255
        ld l,a
        ld h,CHJ/256           ; HL -> CHJ[n]
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                 ; HL = chain entry (n rows)
        ld a,(dc_slot)
        ld b,a                 ; B = slot bits (or), C = 255: white
        ld c,255
        ld a,(dc_code)
        cp 3
        jr z,dc_go
        ld a,b
        cpl
        ld c,a                 ; black: and not slot, or 0
        ld b,0
dc_go:  call jp_hl
        jr dc_run_l
jp_hl:  jp (hl)
dc_next:
        ld a,(dc_wlo)
        inc a
        call nz,dc_mark        ; M2.6 P2E: this ray column drew white rows -> mark its byte column (lowcode.asm)
        ld hl,(ds_uacc)
        ld de,(ds_ustep)
        add hl,de
        ld (ds_uacc),hl
        ld hl,ds_c
        inc (hl)
        ld hl,ds_cnt
        dec (hl)
        jp nz,dc_l
        ret
dc_run: defw 0
dc_buf: defw 0
dc_slot: defb 0
dc_v0:  defb 0
dc_code: defb 0
ds_cnt: defb 0
