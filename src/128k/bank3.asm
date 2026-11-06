; bank3.asm - Kill'em all 128K, lane S (6 Nov 2026): HI-RES (2-px column) zombie blitter PROTOTYPE, pasmo --equ HIRES=1 builds only.
; Lives in RAM BANK 3 (build/bank3.bin, loaded by a second mktap128 stub at F000h), paged at C000h ONLY inside hr_pass
; (src/common/lowcode.asm, fixed low block) per zombie of the vis list, with interrupts ON: FDFDh / FE00h..FF00h below mirror the
; IM2 vector + table (rule F2 of shim128.asm) so a tick during the pass reaches isr (fixed area); BANKM names bank 3 while it is
; paged so snd_isr's fl_pgb returns here (rule F1/F2). Assembled standalone: pasmo --bin bank3.asm with --equ for every fixed-area
; symbol it touches (tools/build128_hires.sh reads them from build/kea128_hires.sym): zbuf, BUF, CHJ, spr_table, dc_white, dc_mark,
; dc_wlo, ds_ink, dc_bcol, isr. Nothing in bank 0 is reachable from here (enemy_h, VSTEP, COLBASE, mul168 are re-done below).
; Entry hr_entry (F000h): HL -> vis entry (hv, c0, nc, data ptr, thing). Returns E = 1 handled (zombie frames spr_4..spr_7, drawn
; or culled) / E = 0 not a zombie (hr_pass then runs the old draw_sprite). Design: build/night/S_design.md.
        org 0F000h
hr_entry:
        push hl
        inc hl
        inc hl
        inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                 ; HL = run-list table of the 16x24 sprite (spr_table[id])
        ld bc,spr_table+8      ; spr_table[4..7] = zombie walk A / walk B / attack / dead
        ld d,0
hr_fl:  ld a,(bc)
        cp l
        jr nz,hr_fn
        inc bc
        ld a,(bc)
        dec bc
        cp h
        jr z,hr_found
hr_fn:  inc bc
        inc bc
        inc d
        ld a,d
        cp 4
        jr c,hr_fl
        pop hl
        ld e,0                 ; not a zombie
        ret
hr_found:
        ld a,d
        add a,a
        ld l,a
        ld h,0
        ld de,HRFRM
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (hr_frm),de         ; 32 column pointers of the 32x48 frame
        ld a,040h
        ld (ds_ink),a          ; zombie green for the colour marks (dc_mark); flash / corpse stain not reproduced (spike)
        pop hl
        ld a,(hl)
        ld (hr_hv),a
        inc hl
        ld a,(hl)              ; c0 (s8 ray column)
        ld c,a
        inc hl
        ld a,(hl)              ; nc (ray columns)
        srl a
        add a,c                ; cx = c0 + nc/2 (the projection's centre ray column)
        ld (hr_cx),a
; hd = enemy_h(hv) and 254 = (hv - hv/4 + hv/16) and 254 (sprites_c.asm enemy_h, re-done: bank 0 is paged out)
        ld a,(hr_hv)
        ld c,a
        srl c
        srl c
        sub c
        srl c
        srl c
        add a,c
        and 254
        ld (hr_hd),a
; ROWTAB2[v] = clamp(top + v*VSTEP2[hd/2], 0, 96), v = 0..48, top = 48 + hv/2 - hd (same rule as sprites_e.asm rt_l, 49 rows)
        ld l,a
        ld h,0
        ld de,VSTEP2
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (hr_step),de
        ld a,(hr_hv)
        srl a
        add a,48
        ld h,a
        ld l,0
        ld a,(hr_hd)
        ld d,a
        ld e,0
        or a
        sbc hl,de
        ex de,hl               ; DE = acc (top, 8.8 s16)
        ld hl,ROWTAB2
        ld b,49
hr_rt:  ld a,d
        bit 7,d
        jr z,hr_r1
        xor a
        jr hr_r2
hr_r1:  cp 97
        jr c,hr_r2
        ld a,96
hr_r2:  ld (hl),a
        inc l
        push hl
        ld hl,(hr_step)
        add hl,de
        ex de,hl
        pop hl
        djnz hr_rt
; columns: n2 = NC2[hd] 2-px columns, ustep = USTEP2[n2]; k0 = (3*cx + 1 - n2) >> 1 (s16), kend = min(k0 + n2, 96)
        ld a,(hr_hd)
        ld l,a
        ld h,NC2/256
        ld a,(hl)
        ld (hr_n2),a
        add a,a
        ld l,a
        ld h,0
        ld de,USTEP2
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (hr_ustep),de
        ld a,(hr_cx)
        ld l,a
        rla
        sbc a,a
        ld h,a                 ; HL = cx (s16)
        ld e,l
        ld d,h
        add hl,hl
        add hl,de
        inc hl                 ; 3cx + 1
        ld a,(hr_n2)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        sra h
        rr l                   ; HL = k0
        ld (hr_k0),hl
        add hl,de              ; HL = kend
        bit 7,h
        jp nz,hr_done          ; whole sprite left of the window
        ld a,h
        or a
        jr nz,hr_k96
        ld a,l
        or a
        jp z,hr_done
        cp 97
        jr c,hr_ke
hr_k96: ld a,96
hr_ke:  ld (hr_kend),a
        ld hl,0
        ld (hr_uacc),hl
        ld hl,(hr_k0)
        bit 7,h
        jr z,hr_kpos
        xor a
        sub l                  ; columns skipped on the left (< n2 <= 43)
        ld hl,(hr_ustep)
        call hr_mul            ; HL = skipped * ustep (< 8192)
        ld (hr_uacc),hl
        xor a
        jr hr_kset
hr_kpos:
        ld a,l                 ; H = 0 here (k0 < kend <= 96)
        cp 96
        jp nc,hr_done
hr_kset:
        ld (hr_k),a
        ld c,a
        ld a,(hr_kend)
        sub c
        jp z,hr_done
        jp c,hr_done
        ld (hr_cnt),a
; ---- per 2-px column k: depth test on its ray column, run list of source column u = uacc >> 8, blit through SCHAIN (fixed)
hr_cl:  ld a,(hr_k)
        add a,HRRAY and 255
        ld l,a
        ld h,HRRAY/256
        ld a,(hl)              ; ray column of this 2-px column
        add a,zbuf and 255
        ld l,a
        ld h,zbuf/256
        ld a,(hl)              ; wall virtual height there (0 = none)
        ld hl,hr_hv
        cp (hl)
        jr z,hr_vis            ; equal (both at the 128 cap) -> sprite in front
        jp nc,hr_next          ; wall nearer -> skip column
hr_vis: ld a,(hr_uacc+1)
        and 31
        add a,a
        ld hl,(hr_frm)
        add a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (hr_run),hl
        ld a,(hr_k)
        ld l,a
        ld h,HRBLO/256
        ld e,(hl)
        add a,HRBHI and 255
        ld l,a
        ld d,(hl)
        ld (hr_buf),de         ; BUF + 96 * (k >> 2)
        ld a,(hr_k)
        ld l,a
        ld h,HRMSK/256
        ld a,(hl)
        ld (hr_msk),a          ; 2-px slot bits
        ld a,(hr_k)
        rrca
        rrca
        and 31
        ld (dc_bcol),a         ; byte column for the colour marks (lowcode.asm dc_mark)
        xor a
        ld (hr_v0),a
hr_rl:  ld hl,(hr_run)
        ld a,(hl)
        or a
        jp z,hr_next
        inc hl
        ld (hr_run),hl
        ld c,a
        and 3
        ld (hr_code),a         ; 0 transparent, 1 black, 3 white
        ld a,c
        rrca
        rrca
        and 63                 ; v_end 1..48
        ld c,a
        ld hl,hr_v0
        ld l,(hl)              ; L = v0
        ld (hr_v0),a
        ld a,(hr_code)
        or a
        jr z,hr_rl
        ld h,ROWTAB2/256
        ld a,(hl)              ; r0
        ld l,c
        ld b,(hl)              ; r1
        ld c,a
        ld a,b
        sub c
        jr z,hr_rl
        ld b,a                 ; B = rows, C = r0
        ld a,(hr_code)
        cp 3
        call z,dc_white        ; fixed area (lowcode.asm): white rows of this column -> dc_wlo / dc_whi (B C DE HL kept)
        ld hl,(hr_buf)
        ld a,l
        add a,c
        ld l,a
        jr nc,$+3
        inc h
        ex de,hl               ; DE = BUF column + r0
        ld a,b
        add a,a
        add a,CHJ and 255
        ld l,a
        ld h,CHJ/256
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                 ; HL = SCHAIN entry for B rows (CHJ, fixed RAM)
        ld a,(hr_msk)
        ld b,a
        ld c,255               ; white: or slot, and 255
        ld a,(hr_code)
        cp 3
        jr z,hr_go
        ld a,b
        cpl
        ld c,a                 ; black: and not slot, or 0
        ld b,0
hr_go:  call hr_jphl
        jr hr_rl
hr_jphl: jp (hl)
hr_next:
        ld a,(dc_wlo)
        inc a
        call nz,dc_mark        ; fixed area: this column drew white rows -> colour mark of its byte column
        ld hl,(hr_uacc)
        ld de,(hr_ustep)
        add hl,de
        ld (hr_uacc),hl
        ld hl,hr_k
        inc (hl)
        ld hl,hr_cnt
        dec (hl)
        jp nz,hr_cl
hr_done:
        ld e,1
        ret
hr_mul:                        ; HL = HL * A (low 16 bits)
        ld e,l
        ld d,h
        ld hl,0
        ld b,8
hm_l:   add hl,hl
        rla
        jr nc,hm_n
        add hl,de
hm_n:   djnz hm_l
        ret
hr_hv:  defb 0
hr_hd:  defb 0
hr_cx:  defb 0
hr_n2:  defb 0
hr_k:   defb 0
hr_kend: defb 0
hr_cnt: defb 0
hr_v0:  defb 0
hr_code: defb 0
hr_msk: defb 0
hr_k0:  defw 0
hr_step: defw 0
hr_ustep: defw 0
hr_uacc: defw 0
hr_frm: defw 0
hr_run: defw 0
hr_buf: defw 0
hr_code_end:
; ---- tables (gen/hires_tabs.asm, tools/gen_hires.py). HRBLO/HRBHI F300h/F360h: BUF byte-column base per 2-px column k
; (BUF + 96*(k>>2)); HRMSK F400h: slot bits (C0h,30h,0Ch,03h); HRRAY F460h: ray column of pixel 2k = 8*(2k div 24) +
; PXRAY[2k mod 24] (M2.5C 3,3,2,4,4,2,3,3-px rays, tools/test_game_sprites.py PXRAY)
        include "gen/hires_tabs.asm"
        org 0F500h
ROWTAB2: defs 49               ; RAM: rebuilt per sprite
        org 0F600h
        include "gen/hires_art.asm"   ; NC2 (page aligned), USTEP2, VSTEP2, HRFRM, 4 frames of 32 run lists
hires_end:
        org 0FDFDh
        jp isr                 ; ISRVEC mirror (fixed-area isr)
        org 0FE00h
        defs 257,0FDh          ; IM2 TABLE mirror
        end
