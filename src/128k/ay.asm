; ay.asm - Kill'em all, 128K sound (lane T3): AY-3-8912 music player (format tools/music/FORMAT.md) + AY SFX.
; Contracts (ARCH_M2.md):
;   snd_isr       called from the IM2 ISR once per frame (<= 4,000 T; measured max in build/t3_report.md).
;                 Advances the music (if playing) and the SFX (if any), then writes AY registers R0..R10.
;   snd_fx        A = 1..10 (ids as beeper.asm). Enqueues the SFX (one slot, newest wins); the ISR plays it on
;                 channel C, pre-empting the music on C (the music's C envelope is frozen meanwhile and resumes
;                 after the SFX). Honours opt_sfx. Non-blocking (~135 T).
;   snd_music     A = 0 stop, 1 menu track, 2 game track. Honours opt_music (1/2 with opt_music = 0 -> stop).
;                 Non-blocking; the ISR picks the request up on its next call; the first row sounds 4 frames later.
;   snd_menu_tick ret (on 128K the menu music comes from the ISR).
; Externals: opt_music, opt_sfx (state.asm); music_menu, music_game, ay_notes (src/gen/music_data.asm - the
;            including build must include that file too; it is not included here so T4 may place the data anywhere
;            that is paged in during interrupts).
; Everything here must be reachable whenever an interrupt can occur (T4: below 0C000h or in the ISR's bank).
; Registers: snd_isr saves/restores AF BC DE HL (no IX/IY, no alternates). snd_fx destroys AF E HL; snd_music AF E.
; Ports: register select OUT (0FFFDh), data OUT (0BFFDh).
;
; Player design (keeps the ISR peak low): rows are decoded one channel per frame AHEAD of time into a spare
; channel block (A on the frame after a row, then B, then C), and on the row frame the spare block becomes the live
; block by a pointer swap ("commit"). Per frame the live blocks drive the software envelopes. Needs speed >= 3
; (compile_music.py enforces it); speed >= 4 avoids catch-up decodes on the row frame.

AY_REG  equ 0FFFDh
AY_DAT  equ 0BFFDh

snd_menu_tick:
        ret

; ---------------------------------------------------------------- API (main loop side)
snd_music:
        ld e,a
        ld a,(opt_music)
        or a
        jr z,snd_m0
        ld a,e
snd_m0: or 080h
        ld (mus_req),a          ; bit 7 = request pending; low bits: 0 stop, 1 menu, 2 game
        ret

snd_fx:
        ld e,a
        ld a,(opt_sfx)
        or a
        ret z
        ld a,e
        dec a
        cp 10
        ret nc
        add a,a
        ld hl,aysfx_tab
        add a,l
        ld l,a
        jr nc,snd_fx1
        inc h
snd_fx1:
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (sfx_req),hl         ; pointer to the segment list (the ISR starts it); 0 = none pending
        ret

; ---------------------------------------------------------------- ISR side
snd_isr:
        push af
        push bc
        push de
        push hl
        ld hl,mus_req
        ld a,(hl)
        or a
        jp p,isr_m1             ; bit 7 clear: no request
        and 07Fh
        ld (hl),0
        call mus_start          ; A = 0 stop, 1 menu, 2 game
isr_m1: ld hl,(sfx_req)
        ld a,h
        or l
        jr z,isr_s1
        ld (sfx_ptr),hl
        ld hl,0
        ld (sfx_req),hl
        xor a
        ld (sfx_left),a         ; 0 frames left -> fetch the first segment this frame
isr_s1: ld a,(mus_on)
        or a
        call nz,mus_frame
isr_s2: ld hl,(sfx_ptr)
        ld a,h
        or l
        call nz,sfx_frame
        ; ---- write R0..R10 from the shadow block (R11 too: harmless, keeps the loop 3 x 4 registers)
        ld hl,ay_regs
        ld d,0FFh
        ld e,0
        ld c,0FDh
isr_wr: ld b,d
        out (c),e               ; select register E (port FFFDh)
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a               ; data (port BFFDh)
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld b,d
        out (c),e
        inc e
        ld b,0BFh
        ld a,(hl)
        inc hl
        out (c),a
        ld a,e
        cp 12
        jr nz,isr_wr
        pop hl
        pop de
        pop bc
        pop af
        ret

; ---------------------------------------------------------------- music: start (A = 1 menu, 2 game) / stop (A = 0)
mus_start:
        dec a
        jr z,mus_st1
        dec a
        jr z,mus_st2
mus_stop:
        xor a
        ld (mus_on),a
        ld hl,ay_regs+8         ; volumes 0
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ld a,03Fh
        ld (ay_regs+7),a        ; all tones and noises off in the mixer
        ret
mus_st1:
        ld hl,music_menu
        jr mus_st
mus_st2:
        ld hl,music_game
mus_st: ld a,(hl)
        ld (mus_speed),a
        inc hl
        ld a,(hl)
        ld (mus_rows),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (mus_order),de
        ld (mus_opos),de
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (mus_pats),de
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (mus_insts),de
        ld hl,cs_init           ; channel stream state: 3 x CS_SIZE bytes (pointers, tone bits, zeroed counters)
        ld de,cs_a
        ld bc,3*CS_SIZE
        ldir
        xor a
        ld (blk_a0),a           ; all six channel blocks: ON = 0 (nothing else matters while off)
        ld (blk_a1),a
        ld (blk_b0),a
        ld (blk_b1),a
        ld (blk_c0),a
        ld (blk_c1),a
        ld (mus_phase),a
        ld (mus_rowleft),a      ; first decode step fetches the first pattern
        ld (mus_noise),a
        ld a,03Fh
        ld (mus_mix),a
        ld (ay_regs+7),a
        ld a,4
        ld (mus_tick),a         ; this frame: setup only; decode A, B, C on the next 3 frames; first row on the 4th
        ld a,1
        ld (mus_on),a
        pop hl                  ; skip this frame's mus_frame (return to snd_isr past the 'call nz,mus_frame')
        jp isr_s2

; ---------------------------------------------------------------- music: one frame
mus_frame:
        ld hl,mus_tick
        dec (hl)
        jr z,mf_row
        ld a,(mus_phase)        ; between rows: decode one channel per frame (phase 0 = A, 1 = B, 2 = C)
        cp 3
        call c,mus_decstep
        jr mf_env
mf_row: ld a,(mus_speed)
        ld (hl),a
mf_catch:
        ld a,(mus_phase)        ; catch-up for speed 3 (C not decoded yet)
        cp 3
        jr nc,mf_commit
        call mus_decstep
        jr mf_catch
mf_commit:
        xor a
        ld (mus_phase),a
        ld hl,cs_a+CS_STAGE
        call mus_commit
        ld hl,cs_b+CS_STAGE
        call mus_commit
        ld hl,cs_c+CS_STAGE
        call mus_commit
mf_env: ld a,(mus_mix)
        ld (ay_regs+7),a
        ld a,(mus_noise)
        ld (ay_regs+6),a
        ld hl,(cs_a+CS_CUR)
        call mus_chenv
        ld (ay_regs+0),hl
        ld (ay_regs+8),a
        ld hl,(cs_b+CS_CUR)
        call mus_chenv
        ld (ay_regs+2),hl
        ld (ay_regs+9),a
        ld hl,(sfx_ptr)
        ld a,h
        or l
        ret nz                  ; SFX owns channel C: its envelope is frozen (sfx_frame writes R4/R5/R10)
        ld hl,(cs_c+CS_CUR)
        call mus_chenv
        ld (ay_regs+4),hl
        ld (ay_regs+10),a
        ret

; ---- decode step: channel (mus_phase) decodes its next row into its spare block; phase++
mus_decstep:
        ld a,(mus_phase)
        or a
        jr nz,ds1
        ld a,(mus_rowleft)      ; channel A goes first: new pattern needed?
        or a
        call z,mus_nextpat
        ld hl,cs_a
        call mus_chdec
        jr ds_end
ds1:    dec a
        jr nz,ds2
        ld hl,cs_b
        call mus_chdec
        jr ds_end
ds2:    ld hl,cs_c
        call mus_chdec
        ld hl,mus_rowleft
        dec (hl)
ds_end: ld hl,mus_phase
        inc (hl)
        ret

; ---- next pattern from the order list -> stream pointers of the three channels
mus_nextpat:
        ld a,(mus_rows)
        ld (mus_rowleft),a
        ld hl,(mus_opos)
mus_ord:
        ld a,(hl)
        cp 0FFh
        jr nz,mus_ord1
        inc hl
        ld a,(hl)               ; loop index
        ld hl,(mus_order)
        add a,l
        ld l,a
        jr nc,mus_ord
        inc h
        jr mus_ord
mus_ord1:
        inc hl
        ld (mus_opos),hl
        ld l,a                  ; HL = pattern index * 6
        ld h,0
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld de,(mus_pats)
        add hl,de
        ld de,cs_a
        call mus_np1
        ld de,cs_b
        call mus_np1
        ld de,cs_c
mus_np1:
        ldi                     ; stream pointer -> CS_PTR
        ldi
        xor a
        ld (de),a               ; CS_WAIT = 0: row due at the next decode
        ret

; ---- decode one row of channel HL (-> cs block) into its spare block
mus_chdec:
        inc hl
        inc hl                  ; -> CS_WAIT
        ld a,(hl)
        or a
        jr z,dc0
        dec (hl)                ; inside an empty-rows run
        ret
dc0:    dec hl
        ld d,(hl)
        dec hl
        ld e,(hl)               ; DE = stream pointer, HL -> CS_PTR
dc_tok: ld a,(de)
        inc de
        cp 080h
        jr nc,dc_prefix
        ld (hl),e               ; terminator: store the stream pointer
        inc hl
        ld (hl),d
        inc hl                  ; -> CS_WAIT
        cp 060h
        jr c,dc_note
        jr z,dc_off
        sub 061h
        ld (hl),a               ; n-1 further empty rows
        ret
dc_off: ld bc,CS_STAGE-CS_WAIT
        add hl,bc
        ld (hl),2               ; stage: note off
        ret
dc_prefix:
        cp 090h
        jr c,dc_inst
        jr z,dc_arp
        ld a,(de)               ; 91h: pitch slide -> spare block CH_SLIDE, flag bit 1
        inc de
        ld c,a
        push hl
        ld b,CH_SLIDE
        call dc_spare
        ld (hl),c
        pop hl
        push hl
        ld bc,CS_FLAGS
        add hl,bc
        set 1,(hl)
        pop hl
        jr dc_tok
dc_arp: ld a,(de)               ; 90h: arpeggio -> spare block CH_ARP, flag bit 0
        inc de
        ld c,a
        push hl
        ld b,CH_ARP
        call dc_spare
        ld (hl),c
        pop hl
        push hl
        ld bc,CS_FLAGS
        add hl,bc
        set 0,(hl)
        pop hl
        jr dc_tok
dc_inst:
        and 0Fh                 ; 80h+i: instrument
        push hl
        inc hl
        inc hl
        inc hl                  ; -> CS_INST
        ld (hl),a
        pop hl
        jr dc_tok
dc_spare:                       ; HL -> CS_PTR -> HL = spare block + B (destroys A)
        ld a,l
        add a,CS_ALT
        ld l,a
        jr nc,dc_sp1
        inc h
dc_sp1: ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,b
        add a,l
        ld l,a
        ret nc
        inc h
        ret
dc_note:                        ; A = note, HL -> CS_WAIT
        ld c,a
        inc hl                  ; -> CS_INST
        ld a,(hl)
        inc hl                  ; -> CS_FLAGS
        ld b,(hl)
        ld (hl),0
        push bc                 ; B = prefix flags, C = note
        inc hl                  ; -> CS_TBIT
        ld c,(hl)
        inc hl
        inc hl                  ; -> CS_STAGE
        ld (hl),1               ; stage: note on
        inc hl
        inc hl
        inc hl                  ; -> CS_ALT
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = spare block
        add a,a                 ; instrument header
        ld hl,(mus_insts)
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL -> header: mix, len, loop, env...
        ld b,(hl)               ; B = mix
        inc hl                  ; -> len
        push hl
        ld hl,CH_MIXON
        add hl,de               ; HL -> spare CH_MIXON
        xor a
        bit 6,b
        jr nz,dn1
        or c                    ; tone on bit
dn1:    bit 7,b
        jr z,dn2
        rlc c
        rlc c
        rlc c
        or c                    ; noise on bit
dn2:    ld (hl),a               ; CH_MIXON
        inc hl
        ld a,b
        and 01Fh
        ld (hl),a               ; CH_NOISE
        ex de,hl                ; HL = spare block (CH_ON)
        pop de                  ; DE -> header len
        ld (hl),1               ; ON
        inc hl
        ld (hl),0               ; EPOS
        inc hl                  ; -> ELEN
        ex de,hl
        ldi                     ; ELEN
        ldi                     ; ELOOP
        ex de,hl                ; HL -> ENV, DE -> envelope data
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl                  ; -> NOTE
        pop bc
        ld (hl),c
        inc hl                  ; -> ARP
        bit 0,b
        jr nz,dn3
        ld (hl),0               ; no arp prefix on this row: arp off
dn3:    inc hl
        ld (hl),0               ; ARPP
        inc hl                  ; -> SLIDE
        bit 1,b
        jr nz,dn4
        ld (hl),0               ; no slide prefix: slide off
dn4:    inc hl
        ld (hl),0               ; ACC
        inc hl
        ld (hl),0
        ret

; ---- commit (row frame): HL -> CS_STAGE. 1 = swap live/spare block + mixer update, 2 = note off
mus_commit:
        ld a,(hl)
        or a
        ret z
        ld (hl),0
        dec a
        jr nz,cm_off
        inc hl                  ; -> CS_CUR
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl                  ; -> CS_ALT
        ld e,(hl)
        ld (hl),c
        inc hl
        ld d,(hl)
        ld (hl),b               ; ALT = old live, DE = new live
        dec hl
        dec hl
        dec hl
        ld (hl),e
        inc hl
        ld (hl),d               ; CUR = new live
        dec hl
        dec hl
        dec hl                  ; -> CS_BOTH
        ld c,(hl)
        ld hl,CH_MIXON
        add hl,de
        ld a,(mus_mix)
        or c                    ; this channel's tone and noise off ...
        xor (hl)                ; ... then on as the instrument says
        ld (mus_mix),a
        inc hl
        ld a,(hl)
        or a
        ret z
        ld (mus_noise),a
        ret
cm_off: inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; live block
        ld (hl),0               ; ON = 0
        ret

; ---- per-frame envelope/effects for the live block HL -> HL = tone period, A = volume (0..15)
mus_chenv:
        ld a,(hl)               ; ON
        or a
        jr nz,ce_on
        ld h,a
        ld l,a                  ; off: period 0, volume 0
        ret
ce_on:  inc hl                  ; -> EPOS
        ld c,(hl)
        inc hl                  ; -> ELEN
        ld a,c
        inc a
        cp (hl)
        inc hl                  ; -> ELOOP
        jr c,ce1
        ld a,(hl)               ; past the end: continue from the loop frame
ce1:    dec hl
        dec hl
        ld (hl),a               ; EPOS = next frame
        inc hl
        inc hl
        inc hl                  ; -> ENV
        ld a,(hl)
        add a,c
        ld e,a
        inc hl
        ld a,(hl)
        adc a,0
        ld d,a                  ; DE -> envelope byte
        ld a,(de)
        ld (ce_vol+1),a         ; (semitone offset << 4) | volume
        inc hl                  ; -> NOTE
        rrca
        rrca
        rrca
        rrca
        and 0Fh
        add a,(hl)
        ld c,a                  ; C = note + instrument offset
        inc hl                  ; -> ARP
        ld a,(hl)
        inc hl                  ; -> ARPP
        or a
        jr z,ce_noarp
        ld d,a                  ; D = xy
        ld a,(hl)               ; phase 0,1,2
        inc (hl)
        or a
        jr z,ce_noarp           ; phase 0: base note
        dec a
        ld a,d
        jr z,ce_arp1            ; phase 1: +x
        ld (hl),0               ; phase 2: +y, next phase 0
        and 0Fh
        jr ce_arp2
ce_arp1:
        rrca
        rrca
        rrca
        rrca
        and 0Fh
ce_arp2:
        add a,c
        ld c,a
ce_noarp:
        inc hl                  ; -> SLIDE
        ld a,c                  ; note index 0..125 (ay_notes has 128 entries, no clamp needed)
        add a,a
        add a,low ay_notes
        ld e,a
        adc a,high ay_notes
        sub e
        ld d,a                  ; DE -> period entry
        ex de,hl
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = period
        ex de,hl                ; HL -> SLIDE
        ld a,(hl)
        or a
        jr z,ce_nosl
        inc hl                  ; -> ACC
        ld e,a
        rla
        sbc a,a
        ld d,a                  ; DE = sign-extended slide
        ld a,(hl)
        add a,e
        ld (hl),a
        ld e,a
        inc hl
        ld a,(hl)
        adc a,d
        ld (hl),a
        ld d,a                  ; DE = accumulated slide
        ex de,hl
        add hl,bc               ; HL = period + slide
        ld a,h
        and 0F0h
        jr z,ce_vol
        ld hl,0FFFh             ; clamp (also catches negative periods)
        jr ce_vol
ce_nosl:
        ld h,b
        ld l,c
ce_vol: ld a,0                  ; envelope byte (self-modified)
        and 0Fh
        ret

; ---------------------------------------------------------------- SFX on channel C (pre-empts the music on C)
; Segment (9 bytes): db frames, dw period, dw dperiod (signed, per frame), db vol (4.4 fixed), db dvol (signed 4.4
; per frame), db noise period (0 = no noise), db flags (bit 0 = tone on). frames = 0 ends the SFX.
sfx_frame:
        ld a,(sfx_left)
        or a
        jr nz,sfx_run
        ld hl,(sfx_ptr)         ; fetch the next segment
        ld a,(hl)
        or a
        jr z,sfx_end
        ld (sfx_left),a
        inc hl
        ld de,sfx_per
        ld bc,8
        ldir                    ; period, dperiod, vol, dvol, noise, flags
        ld (sfx_ptr),hl
sfx_run:
        dec a
        ld (sfx_left),a
        ld hl,(sfx_per)
        ld a,h
        and 0Fh
        ld (ay_regs+5),a
        ld a,l
        ld (ay_regs+4),a
        ld de,(sfx_dper)
        add hl,de
        bit 7,d
        jr z,sfx_r1
        bit 7,h                 ; went negative -> clamp to 1
        jr z,sfx_r1
        ld hl,1
sfx_r1: ld (sfx_per),hl
        ld a,(sfx_vol)
        rrca
        rrca
        rrca
        rrca
        and 0Fh
        ld (ay_regs+10),a
        ld a,(sfx_vol)
        ld c,a
        ld a,(sfx_dvol)
        ld b,a
        add a,c
        jr c,sfx_r2
        bit 7,b
        jr z,sfx_r3
        xor a                   ; dvol < 0 and no carry: below 0 -> clamp 0
        jr sfx_r3
sfx_r2: bit 7,b
        jr nz,sfx_r3
        ld a,255                ; dvol >= 0 and carry: above 255 -> clamp
sfx_r3: ld (sfx_vol),a
        ld a,(ay_regs+7)
        or 024h                 ; C tone + noise off
        ld c,a
        ld a,(sfx_flags)
        bit 0,a
        jr z,sfx_r4
        res 2,c                 ; tone C on
sfx_r4: ld a,(sfx_noise)
        or a
        jr z,sfx_r5
        ld (ay_regs+6),a
        res 5,c                 ; noise C on
sfx_r5: ld a,c
        ld (ay_regs+7),a
        ret
sfx_end:
        ld hl,0
        ld (sfx_ptr),hl
        xor a
        ld (ay_regs+10),a       ; C silent this frame; the music writes it again next frame
        ld a,(ay_regs+7)
        or 024h
        ld (ay_regs+7),a
        ret

; ---------------------------------------------------------------- AY SFX data
aysfx_tab:
        dw aysfx_1,aysfx_2,aysfx_3,aysfx_4,aysfx_5,aysfx_6,aysfx_7,aysfx_8,aysfx_9,aysfx_10
; frames, period, dperiod, vol(4.4), dvol, noise, flags
aysfx_1:                        ; shot: noise burst + low tone thud
        db 3
        dw 300,60
        db 0F0h,-20,3,1
        db 6
        dw 500,30
        db 0B0h,-28,12,1
        db 0
aysfx_2:                        ; door: tone sliding up over 14 frames
        db 14
        dw 1400,-80
        db 0C0h,-6,0,1
        db 0
aysfx_3:                        ; pickup: rising arpeggio C6 E6 G6 C7 (3 frames each)
        db 3
        dw 106,0
        db 0E0h,-16,0,1
        db 3
        dw 84,0
        db 0E0h,-16,0,1
        db 3
        dw 71,0
        db 0E0h,-16,0,1
        db 4
        dw 53,0
        db 0F0h,-40,0,1
        db 0
aysfx_4:                        ; player hurt: low buzz with noise
        db 10
        dw 1800,25
        db 0F0h,-14,20,1
        db 0
aysfx_5:                        ; enemy die: falling tone + noise tail
        db 12
        dw 200,40
        db 0E0h,-10,0,1
        db 5
        dw 900,60
        db 090h,-28,16,1
        db 0
aysfx_6:                        ; menu tick: click
        db 1
        dw 100,0
        db 0E0h,0,0,1
        db 1
        dw 100,0
        db 060h,0,0,1
        db 0
aysfx_7:                        ; locked / no ammo: dull double click
        db 2
        dw 600,0
        db 0C0h,-60,0,1
        db 2
        dw 600,0
        db 000h,0,0,0
        db 2
        dw 600,0
        db 0C0h,-60,0,1
        db 0
aysfx_8:                        ; enemy attack: growl (noise + sliding tone)
        db 8
        dw 700,35
        db 0D0h,-12,10,1
        db 0
aysfx_9:                        ; level clear: 3-note fanfare G5 C6 E6
        db 5
        dw 141,0
        db 0F0h,-8,0,1
        db 5
        dw 106,0
        db 0F0h,-8,0,1
        db 10
        dw 84,0
        db 0F0h,-12,0,1
        db 0
aysfx_10:                       ; player death: long fall
        db 24
        dw 250,30
        db 0F0h,-8,0,1
        db 6
        dw 1200,0
        db 080h,-20,24,0
        db 0

; ---------------------------------------------------------------- state
; channel block (live or spare), CH_SIZE bytes
CH_ON    equ 0
CH_EPOS  equ 1
CH_ELEN  equ 2
CH_ELOOP equ 3
CH_ENV   equ 4                  ; word: envelope data
CH_NOTE  equ 6
CH_ARP   equ 7
CH_ARPP  equ 8
CH_SLIDE equ 9
CH_ACC   equ 10                 ; word: slide accumulator
CH_MIXON equ 12                 ; mixer bits this instrument turns on (tone bit, noise bit)
CH_NOISE equ 13                 ; noise period (0 = none)
CH_SIZE  equ 14
; channel stream state, CS_SIZE bytes
CS_PTR   equ 0                  ; word: stream pointer
CS_WAIT  equ 2                  ; empty rows remaining
CS_INST  equ 3
CS_FLAGS equ 4                  ; bit 0 arp prefix seen, bit 1 slide prefix seen (this row)
CS_TBIT  equ 5                  ; mixer tone bit (1,2,4)
CS_BOTH  equ 6                  ; tone bit | noise bit
CS_STAGE equ 7                  ; 0 nothing staged, 1 note on (spare block ready), 2 note off
CS_CUR   equ 8                  ; word: live block
CS_ALT   equ 10                 ; word: spare block
CS_SIZE  equ 12

cs_init:                        ; copied over cs_a..cs_c at song start
        dw 0
        db 0,0,0,1,9,0
        dw blk_a0,blk_a1
        dw 0
        db 0,0,0,2,18,0
        dw blk_b0,blk_b1
        dw 0
        db 0,0,0,4,36,0
        dw blk_c0,blk_c1
cs_a:   ds CS_SIZE,0
cs_b:   ds CS_SIZE,0
cs_c:   ds CS_SIZE,0
blk_a0: ds CH_SIZE,0
blk_a1: ds CH_SIZE,0
blk_b0: ds CH_SIZE,0
blk_b1: ds CH_SIZE,0
blk_c0: ds CH_SIZE,0
blk_c1: ds CH_SIZE,0
ay_regs:
        db 0,0,0,0,0,0,0,03Fh,0,0,0,0
mus_req:
        db 0
mus_on: db 0
mus_speed:
        db 1
mus_rows:
        db 1
mus_tick:
        db 1
mus_rowleft:
        db 0
mus_phase:
        db 0
mus_mix:
        db 03Fh
mus_noise:
        db 0
mus_order:
        dw 0
mus_opos:
        dw 0
mus_pats:
        dw 0
mus_insts:
        dw 0
sfx_req:
        dw 0
sfx_ptr:
        dw 0
sfx_left:
        db 0
sfx_per:
        dw 0
sfx_dper:
        dw 0
sfx_vol:
        db 0
sfx_dvol:
        db 0
sfx_noise:
        db 0
sfx_flags:
        db 0
ay_end:
