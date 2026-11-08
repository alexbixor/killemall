; dma_next.asm - lane N7 (8 Nov 2026): zxnDMA / zxnDDMA plane PRE-FILL for the flat tier of the Spectrum Next edition B.
; EVERYTHING here is inside IF DEFINED DMAFILL (pasmo --equ DMAFILL=1): the DMAFILL-undefined build is byte-identical.
; Included by main_b.asm in the org 0A200h block (after hwspr_next.asm, before hud_end). Needs draw_b.asm (dr_scr_addr,
; dr_row_params, dr_* scratch), walk_b_vars.inc (wb_rmax, wb_wclip, wb_ceil), main_b_vars.inc (horizon_row under MOUSE_B).
;
; Design (build/night/N7_measure.out, N7_QUESTIONS.md): in the flat tier the plane colour of a pixel depends only on its ROW
; (colour = material*16 + 12 - 3*s, s from d = (|eye - h| * RD[|dy|]) >> 6, dy from the row and horizon_row; rows above the
; horizon are ceiling rows (h = CEIL), rows below are floor rows (h = 0); d > 4095 -> palette index 0). So a 96-entry table
; dmf_coltab[y] = the colour every plane span of row y would be painted with exists; it depends only on (horizon_row, wb_ceil)
; and is rebuilt only when that key changes. Per frame (from planes_reset, i.e. before the column loop of walk_frame_b):
; rows [0, dmf_rmax) are DMA-filled band by band (runs of equal colour, split at row 48 where the two screen halves are 8 KB
; apart), then dr_span_fill (draw_b.asm) skips every span whose colour equals dmf_coltab[row] for rows < dmf_rmax. Walls,
; VOID columns, the weapon, sprites and the HUD are painted exactly as before, so the frame is pixel-identical by construction.
; dmf_rmax = wb_rmax (0 -> 96; 88 with the HUD band on) but 64 (DMF_WROW) while the pistol clip (wb_wclip) is active: the
; pre-fill never writes rows 64..87, where the pistol's protected columns 48..79 live (N4 bug 1), so it can never flash the
; weapon. g_dma = 0 -> dmf_rmax = 0 (nothing skipped, CPU path = today's pixels).
; Hardware/emulator: g_dma 2 = zxnDDMA fill mode lists (hwtest.asm fill_ddma2, 846 us / 12 KB on Paul's core 3.03), g_dma 1 =
; plain zxnDMA fixed-source lists (hwtest.asm fill_zxndma, 2605 us / 12 KB), both verbatim byte lists with the address/length
; fields patched per band. ZEsarUX: the probe says NOT FOUND -> g_dma 1, DMA writes land correctly in zero emulated time (fps
; OPTIMISTIC); --equ FORCE_FOUND=1 forces g_dma 2 (the emulator ignores DFh/F7h: the fill bytes are wrong, no hang).
; --equ DMAFORCE=n forces g_dma = n after the probe (oracles: DMAFORCE=0 = CPU fallback on a DMAFILL build).
; Start-up: dma_detect (hwtest.asm detect_dma, verbatim bytes) sets g_dma and shows it as the BORDER colour (0 black, 1 blue,
; 2 red) so Paul can read the detected value on a CRT.
        IF DEFINED DMAFILL

DMF_PORT    equ 6Bh                     ; zxnDMA / zxnDDMA port
DMF_MARKER  equ 5Ah                     ; detection marker byte (hwtest.asm MARKER default)
DMF_WROW    equ 64                      ; first pistol row: the pre-fill stops here while wb_wclip is active

; ---- variables (bank 5, free area 5E22h..5EBFh of main_b_vars.inc; zero at load)
g_dma       equ 5E2Bh                   ; byte  0 none / 1 plain zxnDMA / 2 zxnDDMA (N4 reserved this address)
dmf_rmax    equ 5E2Ch                   ; byte  rows [0, dmf_rmax) are pre-filled this frame (0 = none: g_dma 0)
dmf_key     equ 5E2Dh                   ; word  L = horizon row, H = CEIL of the table in dmf_coltab (0 = never built)
dmf_y       equ 5E2Fh                   ; byte  scratch row
dmf_coltab  equ 5E30h                   ; 96 B  5E30h..5E8Fh: pre-fill colour of row y

; ---- data first (pasmo wants the probe offsets known where they are used; hwtest.asm does the same)
; zxnddma_compare.asm detect_dma, verbatim (hwtest.asm lines 118..136): a zxnDDMA copies the marker through PHYSICAL
; addresses (port A 04xxxx = 16K bank 2 = this code; port B 0Bxxxx = 8K page DMF_PROBE_PAGE), a plain zxnDMA ignores the
; D7/DB/DF bytes and copies it to the MMU address dmf_probe_to instead.
dmf_detect:
        db 83h,0C3h                 ; stop, reset
        db 0D7h,04h                 ; zxnDDMA: port A bits 23:16 (16K bank 2 = physical 048000h..04BFFFh)
        db 0DBh,0Bh                 ; zxnDDMA: port B bits 23:16: 0B0000h + dmf_probe_to
        db 0DFh,01h                 ; zxnDDMA: physical addresses
        db 83h,83h,83h,83h          ; finish anything a plain DMA was left
        db 83h,83h,83h,83h          ; in the middle of
        db 7Dh                      ; WR0: A to B, port A address, length
        dw dmf_probe_from
        dw 1                        ;   one byte
        db 14h,10h                  ; WR1, WR2: memory, increment
        db 0ADh                     ; WR4: continuous, port B address follows
        dw dmf_probe_to
        db 82h                      ; WR5: stop at the end
        db 0CFh,87h                 ; load, go
dmf_detect_end:
DMF_DETECT_LEN equ dmf_detect_end-dmf_detect
dmf_probe_from:
        db DMF_MARKER
dmf_probe_to:
        db 0                        ; a plain DMA writes the marker here
DMF_PROBE_OFF  equ dmf_probe_to and 1FFFh
DMF_PROBE_PAGE equ (dmf_probe_to/2000h)+56      ; 8K page of physical 0B0000h + dmf_probe_to: page p is at 40000h + p*2000h (61 here)

; plain zxnDMA fill list (hwtest.asm dma_plain, verbatim; the length and destination are patched per band)
dmf_plain:
        db 83h,0C3h                 ; stop, reset (guide note 1)
        db 7Dh                      ; WR0: A to B, port A address and length follow
        dw dmf_val
dmf_plain_len:
        dw 0
        db 24h                      ; WR1: port A memory, fixed address (the source of a fill)
        db 10h                      ; WR2: port B memory, up
        db 0ADh                     ; WR4: continuous, port B address follows
dmf_plain_dst:
        dw 0
        db 82h                      ; WR5: stop at the end
        db 0CFh,87h                 ; load, go
dmf_plain_end:
DMF_PLAIN_LEN equ dmf_plain_end-dmf_plain
dmf_val:
        db 0                        ; the fill byte (fixed source)

; zxnDDMA fill-mode list, 2-cycle timing (hwtest.asm dma_ddma2, verbatim; value, length, destination patched per band)
dmf_ddma2:
        db 83h,0C3h
        db 0DFh,08h                 ; zxnDDMA mode flags: fill (bit 3) only
        db 0F7h                     ; zxnDDMA fill value:
dmf_ddma2_val:
        db 0
        db 65h                      ; WR0: A to B, block length follows (fill mode never reads port A)
dmf_ddma2_len:
        dw 0
        db 54h,02h                  ; WR1: memory, up, timing byte: 2 cycles
        db 50h,02h                  ; WR2: memory, up, timing byte: 2 cycles
        db 0ADh
dmf_ddma2_dst:
        dw 0
        db 82h
        db 0CFh,87h
dmf_ddma2_end:
DMF_DDMA2_LEN equ dmf_ddma2_end-dmf_ddma2

; ---------------------------------------------------------------------------------------------------------------
; dma_detect - start-up (di, slot 7 = FLOOR_BANK): g_dma = 2 / 1 / 0, border = g_dma. hwtest.asm detect, verbatim logic.
; ---------------------------------------------------------------------------------------------------------------
dma_detect:
        xor a
        ld (g_dma),a
        ld (dmf_probe_to),a
        db 0EDh,091h,57h,DMF_PROBE_PAGE ; nextreg 57h,page : slot 7 = the physical page the zxnDDMA probe writes
        ld (0E000h+DMF_PROBE_OFF),a
        ld hl,dmf_detect
        ld bc,DMF_DETECT_LEN*256+DMF_PORT
        otir
        ld a,(0E000h+DMF_PROBE_OFF)
        ld c,a
        db 0EDh,091h,57h,FLOOR_BANK     ; restore slot 7 = floor textures (main_b.asm start-up value)
        ld a,c
        cp DMF_MARKER
        ld a,2
        jr z,dd_set                     ; marker arrived through the physical address: zxnDDMA
        ld a,(dmf_probe_to)
        cp DMF_MARKER
        ld a,1
        jr z,dd_set                     ; marker at the MMU address: plain zxnDMA
        xor a                           ; nothing: no DMA
dd_set:
        IF DEFINED FORCE_FOUND
        ld a,2                          ; oracle E: run the zxnDDMA lists on the emulator (HARDWARE-UNVERIFIED path)
        ENDIF
        IF DEFINED DMAFORCE
        ld a,DMAFORCE                   ; oracles: force g_dma (0 = CPU fallback)
        ENDIF
        ld (g_dma),a
        out (0FEh),a                    ; border 0 black / 1 blue / 2 red = the detected value, readable on a CRT
        ret

; ---------------------------------------------------------------------------------------------------------------
; dma_prefill - per frame from planes_reset (draw_b.asm): dmf_rmax, the colour table (cached), the DMA bands.
; destroys A, BC, DE, HL (planes_reset's caller walk_frame_b saves nothing across it)
; ---------------------------------------------------------------------------------------------------------------
dma_prefill:
        ld a,(g_dma)
        or a
        jr nz,dpf_on
        ld (dmf_rmax),a                 ; g_dma 0: nothing pre-filled, nothing skipped
        ret
dpf_on:
        ld a,(wb_rmax)                  ; 0 (engine-only programs, first frame) -> 96 ; 88 with the HUD band on
        or a
        jr nz,dpf_r1
        ld a,96
dpf_r1: ld c,a
        ld hl,(wb_wclip)
        ld a,h
        or l
        ld a,c
        jr z,dpf_r2
        cp DMF_WROW+1                   ; pistol clip active: never write rows >= 64 (its protected columns 48..79)
        jr c,dpf_r2
        ld a,DMF_WROW
dpf_r2: ld (dmf_rmax),a
        IF DEFINED MOUSE_B
        ld a,(horizon_row)              ; lane N5: the horizon moves with vertical look
        ELSE
        ld a,48
        ENDIF
        ld l,a
        ld a,(wb_ceil)
        ld h,a                          ; HL = key (horizon row, CEIL)
        ld de,(dmf_key)
        or a
        sbc hl,de
        jr z,dpf_fill                   ; same key: the table is valid
        add hl,de
        ld (dmf_key),hl
        call dmf_build
dpf_fill:
        xor a                           ; A = y0 = first row of the next band
dpf_band:
        ld hl,dmf_rmax
        cp (hl)
        ret nc                          ; y0 >= rmax: done
        ld (dmf_y),a
        ld hl,dmf_coltab
        db 0EDh,031h                    ; add hl,a
        ld c,(hl)                       ; C = colour of the band
        ld b,a                          ; B = y1 (exclusive end, grows)
dpf_ext:
        inc b
        ld a,b
        cp 48
        jr z,dpf_end                    ; the two screen halves are 8 KB apart: split at row 48
        ld hl,dmf_rmax
        cp (hl)
        jr nc,dpf_end
        ld hl,dmf_coltab
        db 0EDh,031h                    ; add hl,a
        ld a,(hl)
        cp c
        jr z,dpf_ext                    ; same colour: extend the band
dpf_end:                                ; rows dmf_y .. B-1 get colour C
        ld a,(dmf_y)
        ld e,a
        ld a,b
        sub e                           ; rows (1..48)
        push bc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                       ; HL = rows * 128 = bytes
        ex de,hl                        ; DE = length
        ld a,(dmf_y)
        call dr_scr_addr                ; HL = screen address of (0, y0) (destroys A, HL only)
        ld a,c
        call dmf_dma                    ; fill DE bytes at HL with A
        pop bc
        ld a,b
        jr dpf_band

; dmf_dma: HL = destination, DE = length, A = value -> one DMA transfer (the CPU is held until the DMA finishes)
dmf_dma:
        ld (dmf_val),a
        ld a,(g_dma)
        cp 2
        jr z,dmf_d2
        ld (dmf_plain_dst),hl
        ex de,hl
        ld (dmf_plain_len),hl
        ld hl,dmf_plain
        ld bc,DMF_PLAIN_LEN*256+DMF_PORT
        otir
        ret
dmf_d2:
        ld (dmf_ddma2_dst),hl
        ex de,hl
        ld (dmf_ddma2_len),hl
        ld a,(dmf_val)
        ld (dmf_ddma2_val),a
        ld hl,dmf_ddma2
        ld bc,DMF_DDMA2_LEN*256+DMF_PORT
        otir
        ret

; dmf_build: dmf_coltab[y] for y = 0..95 with dr_row_params and the dr_span_draw colour rule (draw_b.asm), rows < horizon
; row as ceiling spans (h = CEIL), the rest as floor spans (h = 0); d > 4095 -> 0.
dmf_build:
        xor a
dmb_loop:
        ld (dmf_y),a
        ld (dr_y),a
        ld hl,dmf_key                   ; L = horizon row
        cp (hl)
        ld a,0                          ; floor: h = 0 (flags kept)
        jr nc,dmb_h
        ld a,(wb_ceil)                  ; ceiling: h = CEIL
dmb_h:  ld (dr_h),a
        call dr_row_params              ; flat tier: dr_far, dr_s
        ld a,(dr_far)
        or a
        ld a,0
        jr nz,dmb_store                 ; too far: palette index 0
        ld a,(dr_h)
        ld c,a
        ld a,(eye)
        sub c                           ; eye - h: floor when >= 0 (dr_span_draw's rule)
        ld a,FLAT_FLOOR_MAT*16+12
        jp p,dmb_mat
        ld a,FLAT_CEIL_MAT*16+12
dmb_mat:
        ld c,a
        ld a,(dr_s)
        ld b,a
        add a,a
        add a,b                         ; 3*s
        ld b,a
        ld a,c
        sub b                           ; colour
dmb_store:
        ld c,a
        ld hl,dmf_coltab
        ld a,(dmf_y)
        db 0EDh,031h                    ; add hl,a
        ld (hl),c
        inc a
        cp 96
        jr c,dmb_loop
        ret

        ENDIF
