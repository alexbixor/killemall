; sprites_e.asm (T1) - draw the vis list (far -> near): per sprite ROWTAB (25 clamped rows), then per ray column a zbuf
; test and run-list blit through the SCHAIN (ld a,(de)/and c/or b/ld (de),a/inc e per row; B/C select white or black).
vis_sort_draw:
        ld a,(nvis)
        or a
        ret z
        ld b,a
        ld hl,vis
vsd_l:  push bc
        push hl
        call draw_sprite
        pop hl
        ld bc,6
        add hl,bc
        pop bc
        djnz vsd_l
        ret
; draw_sprite: HL -> vis entry (hv, c0, nc, data ptr, thing).
draw_sprite:
        ld a,(hl)
        ld (ds_hv),a
        inc hl
        ld a,(hl)
        ld (ds_c0),a
        inc hl
        ld a,(hl)
        ld (ds_nc),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (ds_spr),de
        inc hl
        ld a,(hl)              ; thing index -> type (bit 4: item) for the enemy height rule (M2.5: no ink lookup, one ink)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,things
        add hl,de
        ld a,(hl)
        and 31
        ld c,a
        call ds_inkl           ; M2.6 P2E: ds_ink = INKTAB[type] << 4 (0 for corpses / decor), HL and C kept (lowcode.asm)
        ld a,(ds_hv)
        bit 4,c
        call z,enemy_h         ; M2.2: enemies 0.8 x (items keep hv)
        and 254                ; even: step VSTEP[hd/2] and top = base - hd describe the same height
        ld (ds_hd),a
; ROWTAB[v] = clamp(top + v*hd/24, 0, 96), v = 0..24; top = 48 + hv/2 - hd (feet on the floor line), step = VSTEP[hd/2]
        ld l,a
        ld h,0
        ld de,VSTEP
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)              ; DE = step 8.8
        ld (ds_step),de
        ld a,(ds_hv)
        srl a
        add a,48
        ld h,a
        ld l,0                 ; HL = (48 + hv/2) << 8
        ld a,(ds_hd)
        ld d,a
        ld e,0
        or a
        sbc hl,de              ; HL = top 8.8 (s16)
        ex de,hl               ; DE = acc (top)
        ld hl,(ds_step)
        ld hl,ROWTAB
        ld b,25
rt_l:   ld a,d                 ; integer row (s8)
        bit 7,d
        jr z,rt1
        xor a                  ; negative -> 0
        jr rt2
rt1:    cp 97
        jr c,rt2
        ld a,96
rt2:    ld (hl),a
        inc hl
        push hl
        ld hl,(ds_step)
        add hl,de
        ex de,hl
        pop hl
        djnz rt_l
; column range: c = max(c0,0) .. min(c0+nc,64); u accumulator starts at (c-c0)*STEPTAB[nc]
        ld a,(ds_nc)
        add a,a
        ld l,a
        ld h,0
        ld de,STEPTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (ds_ustep),de
        ld hl,0
        ld (ds_uacc),hl
        ld a,(ds_c0)
        bit 7,a
        jr z,ds_c0ok
        neg                    ; columns skipped on the left
        ex de,hl               ; HL = ustep
        call mul168            ; A:HL = skipped * ustep (< 4096)
        ld (ds_uacc),hl
        xor a
ds_c0ok:
        ld (ds_c),a            ; first column
        ld a,(ds_c0)
        ld c,a
        ld a,(ds_nc)
        add a,c                ; c0 + nc (s8; may be <= 64 or beyond)
        jp m,ds_end64
        cp 64
        jr c,ds_cst
ds_end64:
        ld a,64
ds_cst: ld (ds_cend),a
        jp ds_cols
ds_hv:  defb 0
ds_hd:  defb 0
ds_c0:  defb 0
ds_nc:  defb 0
ds_spr: defw 0
ds_step: defw 0
ds_ustep: defw 0
ds_uacc: defw 0
ds_c:   defb 0
ds_cend: defb 0
; M2.5: TYPEINK / ds_ink removed - the whole window has one ink (0x07), sprites are masked white/black
