; hwtest.asm - lane H1 (7 Nov 2026): Spectrum Next HARDWARE TEST for the friend's real Next (core 3.03.00, "Zero Wait State
; 28 MHz", zxnDDMA). Prints every number in 8x8 ROM-font characters on the ULA screen (photographs well) AND stores it in the
; result block at 5F80h (read over ZRCP by tools/nx_hwtest.py). Built by tools/nx_hwtest.py -> build/next/hwtest.nex
; (16K bank 2 = this code at 8000h, 16K bank 5 = screen + variables, SP 5F00h, PC 8000h).
; Options (pasmo --equ): PROBE_MARK=nn (the detection marker byte, default 5Ah; mutation control), FORCE_FOUND=1 (treat the
; zxnDDMA as present whatever the probe says, to exercise the (d)/(e) fill code on a plain-DMA machine).
; Sources: /home/ubuntu/work/next-docs/zxnddma_guide.txt (nodes REGISTERS, WR6, DDMACMDS, NOTES; detect = node EX4 =
; docs/zxnDDMA/examples/zxnddma_compare.asm lines 178-220, translated verbatim to pasmo), BLITTER_NOTE.md sections 2/3/5,
; registers.txt (nextreg 00h machine id, 01h core major.minor nibbles, 0Eh sub-minor, 0Fh board, 03h bits 6:4 display timing,
; 05h bit 2 = 60 Hz, 07h speed, 1Eh/1Fh video line, 50h..57h MMU).
;
; Screen lines (row: text):
;  0  KILLEMALL NEXT HWTEST H1 RUN n
;  2  MACHINE mm CORE m.nn.ss BOARD b        nextreg 00h, 01h (hi nibble . lo nibble), 0Eh, 0Fh, all decimal
;  3  VIDEO lll LINES TIMING t 50HZ|60HZ    lll = measured lines per frame (wait for line 0, read the max line until it wraps),
;                                            t = nextreg 03h bits 6:4 (1 = 48K timing: 224 T per line = 64 us; 2/3 = 128K/+3
;                                            timing: 228 T per line = 65.14 us; anything else is treated as 224), 05h bit 2
;  4  ZXNDDMA FOUND | ZXNDDMA NOT FOUND (PLAIN DMA OK) | ZXNDDMA NOT FOUND (NO DMA) | ZXNDDMA FORCED
;  5  CPU LOOP     llll LN  mm.m MHZ        register-only loop, T_CPU T-states (below), timed in video lines
;  6  MEM SRAM     llll LN  mm.m MHZ        8-way unrolled ld (hl),a ; inc l loop, code AND target in 16K bank 2 (SRAM)
;  7  MEM BLOCKRAM llll LN  mm.m MHZ        the SAME loop copied to 5B00h (16K bank 5 = block RAM), target 7000h..70FFh
;  9..18  FILL <CPU|LDIR|ZXNDMA|DDMA3|DDMA2> <SRAM|BLK> nnnnn US [BAD] | SKIPPED   12,288 bytes to C000h..EFFFh:
;        SRAM = 16K bank 3 (nextreg 56h,6 / 57h,7), BLK = 16K bank 7 (block RAM, nextreg 56h,14 / 57h,15); BAD = the first,
;        middle or last byte does not hold the fill value afterwards; SKIPPED = zxnDDMA not found ((d) and (e) only)
; 20  WARNING 60 HZ VIDEO                   only when nextreg 05h bit 2 = 1
; 22  PRESS R TO REPEAT
;
; MHz x 10 = round(K / lines), K = round(T_total x 35 / Tline) (Tline = 224 -> T x 10 / 64), 32/16 division below.
; Fill microseconds = lines x Tline x 2 / 7 (224 -> lines x 64). pasmo evaluates expressions in 16 bits, so every 32-bit
; constant is written as two words (lo, hi) with its derivation in a comment; tools/nx_hwtest.py recomputes all of them.
;
; T-state accounting (standard Z80 timings, no contention at 28 MHz; the Next's Z80N keeps them):
;  cpu_chunk  (incl. the call 17): ld c,15 7 ; 15 x [ld b,0 7 ; djnz $ 255x13+8 = 3323 ; dec c 4 ; jr nz 12] - 5 (last jr 7)
;             ; ret 10  = 17 + 7 + (15 x 3346 - 5) + 10 = 50219
;  mem_chunk  (incl. call): ld hl,buf 10 ; ld a,v 7 ; ld c,15 7 ; 15 x [ld b,32 7 ; 32 x 8 x (ld (hl),a 7 + inc l 4) = 2816 ;
;             djnz 31x13+8 = 411 ; dec c 4 ; jr nz 12] - 5 ; ret 10 = 17 + 24 + (15 x 3250 - 5) + 10 = 48796
;  timed_run loop body without the chunk (per iteration, no-wrap path): read_line 179 (call 17 + 162) ; ld de,(prev) 20 ;
;             ld (prev),hl 16 ; or a 4 ; sbc hl,de 15 ; jr nc 12 ; ld hl,(n) 16 ; dec hl 6 ; ld (n),hl 16 ; ld a,h 4 ; or l 4 ;
;             jr nz 12 = 304. A wrap iteration costs 38 more (about 9 of 100 iterations: 342 T = 0.2 lines); the first line-0
;             detection has up to 1 line of phase; the sum of these is below 1 line of 2,800 -> ignored.
;  N_CHUNKS = 100:  T_CPU = 100 x (50219 + 304) = 5,052,300 = 004D178Ch ; T_MEM = 100 x (48796 + 304) = 4,910,000 = 004AEBB0h
;  K (MHz x 10 numerators): CPU 224: 789422 = 000C0BAEh ; CPU 228: 775574 = 000BD596h ; MEM 224: 767188 = 000BB4D4h ;
;             MEM 228: 753728 = 000B8040h
;  fill_cpu   (incl. call): ld de,C000h 10 ; ld c,48 7 ; 48 x [ld b,32 7 ; 32 x 8 x (ld (de),a 7 + inc e 4) = 2816 ; djnz 411 ;
;             inc d 4 ; dec c 4 ; jr nz 12] - 5 ; ret 10 = 17 + 17 + (48 x 3254 - 5) + 10 = 156231 -> 5580 us at 28.0 MHz
;  fill_ldir  (incl. call): ld hl 10 ; ld de 10 ; ld (hl),a 7 ; ld bc 10 ; ldir 12286 x 21 + 16 = 258022 ; ret 10 = 258086
;             -> 9217 us at 28.0 MHz
;
; Result block at 5F80h (words unless noted; tools/nx_hwtest.py reads it over ZRCP):
;  5F80 R_DONE     1 when a run has finished (0 while running)         5F82 R_MACH   nextreg 00h
;  5F84 R_CORE     nextreg 01h                                          5F86 R_SUB    nextreg 0Eh
;  5F88 R_BOARD    nextreg 0Fh                                          5F8A R_DDMA   0 not found, 1 found, 2 forced
;  5F8C R_PROBE    lo = probe_to byte after the probe, hi = the 8K page 60 byte (E000h + (probe_to and 1FFFh))
;  5F8E R_LPF      measured lines per frame                             5F90 R_TIMING lo = nextreg 03h, hi = nextreg 05h
;  5F92 R_TLINE    T per line used (224 or 228)                         5F94 R_CPU_LN  CPU loop lines
;  5F96 R_CPU_MHZ  MHz x 10                                             5F98 R_SRAM_LN 5F9A R_SRAM_MHZ 5F9C R_BLK_LN 5F9E R_BLK_MHZ
;  5FA0 R_FILL     10 entries x 6 bytes in screen order (CPU SRAM, CPU BLK, LDIR SRAM, LDIR BLK, ZXNDMA SRAM, ZXNDMA BLK,
;                  DDMA3 SRAM, DDMA3 BLK, DDMA2 SRAM, DDMA2 BLK): +0 lines (word), +2 us (word), +4 status (0 OK, 1 BAD,
;                  2 SKIPPED), +5 the byte at F000h after the fill (sentinel just past the region; should stay = NOT value)
;  5FDC R_SPEED    nextreg 07h read back after writing 3                5FDE R_RUNS   run counter (1 = first run)
;  5FE0 R_TCPU     T_CPU as two words (lo, hi)                          5FE4 R_TMEM   T_MEM as two words (lo, hi)
;  5FE8 R_MARK     lo = the probe marker byte used, hi = FORCE_FOUND (0/1)
; Z80N opcodes as db: nextreg r,v = 0EDh,091h,r,v ; nextreg r,a = 0EDh,092h,r.
        org 8000h

MAIN_STACK  equ 5F00h
BLK_CODE    equ 5B00h          ; bank 5 copy of mem_chunk (block RAM)
BLK_BUF     equ 7000h          ; its 256-byte target (bank 5, above the screen)
SRAM_BUF    equ 9F00h          ; mem_chunk target in bank 2 (code must end below it; nx_hwtest.py checks)
FILL_BASE   equ 0C000h
FILL_LEN    equ 3000h          ; 12,288 bytes
FILL_VALUE  equ 0A5h
N_CHUNKS    equ 100
DMA_PORT    equ 6Bh
        if defined PROBE_MARK
MARKER      equ PROBE_MARK
        else
MARKER      equ 5Ah
        endif
        if defined FORCE_FOUND
FORCED      equ 1
        else
FORCED      equ 0
        endif

R_DONE      equ 5F80h
R_MACH      equ 5F82h
R_CORE      equ 5F84h
R_SUB       equ 5F86h
R_BOARD     equ 5F88h
R_DDMA      equ 5F8Ah
R_PROBE     equ 5F8Ch
R_LPF       equ 5F8Eh
R_TIMING    equ 5F90h
R_TLINE     equ 5F92h
R_CPU_LN    equ 5F94h
R_CPU_MHZ   equ 5F96h
R_SRAM_LN   equ 5F98h
R_SRAM_MHZ  equ 5F9Ah
R_BLK_LN    equ 5F9Ch
R_BLK_MHZ   equ 5F9Eh
R_FILL      equ 5FA0h
R_SPEED     equ 5FDCh
R_RUNS      equ 5FDEh
R_TCPU      equ 5FE0h
R_TMEM      equ 5FE4h
R_MARK      equ 5FE8h

start:
        di
        ld sp,MAIN_STACK
        ld hl,0
        ld (R_RUNS),hl
        jp run_all

; ---------------------------------------------------------------------------------------------------------------
; the detection probe data (before the code that uses it: pasmo wants PROBE_OFF known when it is used)
; zxnddma_compare.asm detect_dma, verbatim (the two 'dw' use our labels):
; ---------------------------------------------------------------------------------------------------------------
detect_dma:
        db 83h,0C3h                 ; stop, reset
        db 0D7h,04h                 ; zxnDDMA: port A bits 23:16 (this program: 16K bank 2 = physical 048000h)
        db 0DBh,0Bh                 ; zxnDDMA: port B bits 23:16: 0B8000h + ...
        db 0DFh,01h                 ; zxnDDMA: physical addresses
        db 83h,83h,83h,83h          ; finish anything a plain DMA was left
        db 83h,83h,83h,83h          ; in the middle of
        db 7Dh                      ; WR0: A to B, port A address, length
        dw probe_from
        dw 1                        ;   one byte
        db 14h,10h                  ; WR1, WR2: memory, increment
        db 0ADh                     ; WR4: continuous, port B address follows
        dw probe_to
        db 82h                      ; WR5: stop at the end
        db 0CFh,87h                 ; load, go
detect_dma_end:
DETECT_LEN  equ detect_dma_end-detect_dma
probe_from:
        db MARKER                   ; the marker
probe_to:
        db 0                        ; scratch: a plain DMA writes the marker here (must be in 8000h..9FFFh: page 60 then)
PROBE_OFF   equ probe_to and 1FFFh
have_ddma:
        db 0

; ---------------------------------------------------------------------------------------------------------------
; run_all - one complete run (also the target of key R)
; ---------------------------------------------------------------------------------------------------------------
run_all:
        di
        ld sp,MAIN_STACK
        ld hl,(R_RUNS)
        inc hl
        ld (R_RUNS),hl
        ld hl,0
        ld (R_DONE),hl
        db 0EDh,091h,07h,03h        ; nextreg 7,3 : 28 MHz
        db 0EDh,091h,0CCh,00h       ; nextreg CCh..CEh = 0 : no interrupt source may hold the DMA back (guide note 10)
        db 0EDh,091h,0CDh,00h
        db 0EDh,091h,0CEh,00h
        db 0EDh,091h,50h,0FFh       ; slots 0/1 = ROM (the 48K ROM font at 3D00h)
        db 0EDh,091h,51h,0FFh
        db 0EDh,091h,15h,00h        ; LoRes off, sprites off (the ULA screen is the display)
        db 0EDh,091h,68h,00h        ; ULA on
        db 0EDh,091h,69h,00h        ; Layer 2 off, ULA shadow off
        db 0EDh,091h,6Bh,00h        ; tilemap off
        ld bc,123Bh                 ; Layer 2 port: off, no paging over 0000h..3FFFh
        xor a
        out (c),a
        ld bc,1FFDh                 ; +3 paging: ROM bit 1 = 1, normal paging
        ld a,04h
        out (c),a
        ld bc,7FFDh                 ; 128 paging: ROM bit 0 = 1 -> ROM 3 = 48K BASIC (font at 3D00h), bank 0 at C000h
        ld a,10h
        out (c),a
        db 0EDh,091h,43h,00h        ; palette control: ULA palette for writing, auto-increment
        db 0EDh,091h,40h,00h        ; index 0
        ld hl,ula_pal
        ld b,32
ra_pal:
        ld a,(hl)
        db 0EDh,092h,41h            ; nextreg 41h,a : 8-bit colour
        inc hl
        djnz ra_pal
        xor a
        out (0FEh),a                ; border black
        ld hl,4000h                 ; pixels off
        ld de,4001h
        ld bc,1800h-1
        ld (hl),0
        ldir
        ld hl,5800h                 ; attributes: bright white ink on black paper
        ld de,5801h
        ld bc,300h-1
        ld (hl),47h
        ldir
        ld hl,R_MACH                ; result block 5F82h..5FDDh cleared (R_RUNS and later words are written below)
        ld de,R_MACH+1
        ld bc,5Ch-1
        ld (hl),0
        ldir
        ld hl,178Ch                 ; T_CPU = 5,052,300 = 004D178Ch
        ld (R_TCPU),hl
        ld hl,004Dh
        ld (R_TCPU+2),hl
        ld hl,0EBB0h                ; T_MEM = 4,910,000 = 004AEBB0h
        ld (R_TMEM),hl
        ld hl,004Ah
        ld (R_TMEM+2),hl
        ld hl,FORCED*256+MARKER
        ld (R_MARK),hl
        ; ---- title
        xor a
        call locate
        ld hl,s_title
        call print_str
        ld hl,(R_RUNS)
        ld b,1
        call print_dec
        ; ---- line 2: ids
        ld a,2
        call locate
        ld hl,s_machine
        call print_str
        ld a,00h
        call rd_nextreg
        ld l,a
        ld h,0
        ld (R_MACH),hl
        ld b,1
        call print_dec
        ld hl,s_core
        call print_str
        ld a,01h
        call rd_nextreg
        ld l,a
        ld h,0
        ld (R_CORE),hl
        rrca
        rrca
        rrca
        rrca
        and 0Fh
        ld l,a
        ld h,0
        ld b,1
        call print_dec
        ld a,'.'
        call print_char
        ld a,(R_CORE)
        and 0Fh
        ld l,a
        ld h,0
        ld b,2
        call print_dec0
        ld a,'.'
        call print_char
        ld a,0Eh
        call rd_nextreg
        ld l,a
        ld h,0
        ld (R_SUB),hl
        ld b,2
        call print_dec0
        ld hl,s_board
        call print_str
        ld a,0Fh
        call rd_nextreg
        ld l,a
        ld h,0
        ld (R_BOARD),hl
        ld b,1
        call print_dec
        ; ---- line 3: video
        ld a,07h
        call rd_nextreg
        ld l,a
        ld h,0
        ld (R_SPEED),hl
        ld a,03h
        call rd_nextreg
        ld (R_TIMING),a
        ld a,05h
        call rd_nextreg
        ld (R_TIMING+1),a
        ld hl,224
        ld a,(R_TIMING)
        rrca
        rrca
        rrca
        rrca
        and 07h                     ; display timing 0..7
        ld (vid_timing),a
        cp 2
        jr z,ra_t228
        cp 3
        jr nz,ra_t224
ra_t228:
        ld hl,228
ra_t224:
        ld (R_TLINE),hl
        call measure_lpf            ; HL = lines per frame
        ld (R_LPF),hl
        ld a,3
        call locate
        ld hl,s_video
        call print_str
        ld hl,(R_LPF)
        ld b,3
        call print_dec
        ld hl,s_lines
        call print_str
        ld a,(vid_timing)
        ld l,a
        ld h,0
        ld b,1
        call print_dec
        ld hl,s_50hz
        ld a,(R_TIMING+1)
        bit 2,a
        jr z,ra_hz
        ld hl,s_60hz
ra_hz:
        call print_str
        ; ---- line 4: zxnDDMA detection
        call detect
        ld a,4
        call locate
        ld a,(have_ddma)
        ld (R_DDMA),a
        xor a
        ld (R_DDMA+1),a
        ld a,(have_ddma)
        cp 2
        jr nz,ra_d1
        ld hl,s_forced
        jr ra_dprint
ra_d1:
        or a
        jr z,ra_d2
        ld hl,s_found
        jr ra_dprint
ra_d2:
        ld hl,s_notfound
        call print_str
        ld hl,s_plainok
        ld a,(R_PROBE)
        cp MARKER
        jr z,ra_dprint
        ld hl,s_nodma
ra_dprint:
        call print_str
        ; ---- line 5: CPU loop
        ld hl,cpu_chunk
        call timed_run              ; HL = lines
        ld (R_CPU_LN),hl
        ld de,k_cpu
        call mhz_from_lines         ; HL = MHz x 10
        ld (R_CPU_MHZ),hl
        ld a,5
        ld hl,s_cpu
        ld de,R_CPU_LN
        call print_mhz_line
        ; ---- line 6: SRAM memory loop
        ld hl,mem_chunk
        call timed_run
        ld (R_SRAM_LN),hl
        ld de,k_mem
        call mhz_from_lines
        ld (R_SRAM_MHZ),hl
        ld a,6
        ld hl,s_sram
        ld de,R_SRAM_LN
        call print_mhz_line
        ; ---- line 7: the same loop in block RAM (bank 5)
        ld hl,mem_chunk
        ld de,BLK_CODE
        ld bc,mem_chunk_end-mem_chunk
        ldir
        ld hl,BLK_BUF
        ld (BLK_CODE+1),hl          ; patch 'ld hl,buf' of the copy
        ld hl,BLK_CODE
        call timed_run
        ld (R_BLK_LN),hl
        ld de,k_mem
        call mhz_from_lines
        ld (R_BLK_MHZ),hl
        ld a,7
        ld hl,s_blk
        ld de,R_BLK_LN
        call print_mhz_line
        ; ---- lines 9..18: fills
        ld a,9
        ld (cur_row),a
        ld ix,R_FILL
        ld iy,fill_table
        ld b,5
ra_fill_m:
        push bc
        ld a,6                      ; SRAM: 16K bank 3 = 8K pages 6/7
        call do_fill
        ld a,14                     ; block RAM: 16K bank 7 = 8K pages 14/15
        call do_fill
        ld de,5
        add iy,de
        pop bc
        djnz ra_fill_m
        db 0EDh,091h,56h,12         ; restore slots 6/7 to 12/13 (brief)
        db 0EDh,091h,57h,13
        ; ---- 60 Hz warning
        ld a,(R_TIMING+1)
        bit 2,a
        jr z,ra_nowarn
        ld a,20
        call locate
        ld hl,s_warn60
        call print_str
ra_nowarn:
        ld a,22
        call locate
        ld hl,s_press
        call print_str
        ld hl,1
        ld (R_DONE),hl
        ; ---- wait for R (row FBh bit 3): first released, then pressed
ra_rel:
        ld a,0FBh
        in a,(0FEh)
        bit 3,a
        jr z,ra_rel
ra_key:
        ld a,0FBh
        in a,(0FEh)
        bit 3,a
        jr nz,ra_key
        jp run_all

; fill_table: 5 methods x (routine word, name word, needs zxnDDMA byte)
fill_table:
        dw fill_cpu,s_f_cpu
        db 0
        dw fill_ldir,s_f_ldir
        db 0
        dw fill_zxndma,s_f_zxndma
        db 0
        dw fill_ddma3,s_f_ddma3
        db 1
        dw fill_ddma2,s_f_ddma2
        db 1

; ---------------------------------------------------------------------------------------------------------------
; do_fill - A = 8K page of the target bank (6 or 14), IY -> fill_table entry, IX -> result entry (6 bytes, advanced),
; (cur_row) = the screen row (advanced). Pre-fills the region and the sentinel at F000h with NOT FILL_VALUE, times the
; fill from video line 0, verifies the first/middle/last byte.
; ---------------------------------------------------------------------------------------------------------------
do_fill:
        ld (fill_page),a
        db 0EDh,092h,56h            ; nextreg 56h,a
        inc a
        db 0EDh,092h,57h            ; nextreg 57h,a
        ld a,(cur_row)
        call locate
        ld hl,s_fill
        call print_str
        ld l,(iy+2)
        ld h,(iy+3)
        call print_str
        ld hl,s_sram_t
        ld a,(fill_page)
        cp 6
        jr z,df_tn
        ld hl,s_blk_t
df_tn:
        call print_str
        ld a,(iy+4)                 ; needs zxnDDMA?
        or a
        jr z,df_run
        ld a,(have_ddma)
        or a
        jr nz,df_run
        ld hl,s_skipped
        call print_str
        ld (ix+0),0
        ld (ix+1),0
        ld (ix+2),0
        ld (ix+3),0
        ld (ix+4),2
        ld (ix+5),0
        jr df_next
df_run:
        ld hl,FILL_BASE             ; pre-fill with the complement (+ the sentinel byte at F000h)
        ld de,FILL_BASE+1
        ld bc,FILL_LEN              ; 3000h bytes + 1 = C000h..F000h
        ld (hl),FILL_VALUE xor 0FFh
        ldir
        ld l,(iy+0)
        ld h,(iy+1)
        ld (df_call+1),hl
        call wait_line0
        ld a,FILL_VALUE
df_call:
        call 0
        call read_line              ; HL = lines (the fill must take less than one frame)
        ld (ix+0),l
        ld (ix+1),h
        ld de,(R_TLINE)             ; us = lines x Tline x 2 / 7
        ex de,hl                    ; HL = Tline, DE = lines
        add hl,hl                   ; HL = Tline x 2
        call mul16                  ; DE:HL = lines x (Tline x 2)
        ld (dvd),hl
        ld (dvd+2),de
        ld bc,7
        call div32
        ld hl,(dvd)                 ; us (fits 16 bits below 1024 lines)
        ld (ix+2),l
        ld (ix+3),h
        ld b,5
        call print_dec
        ld hl,s_us
        call print_str
        ld a,(0F000h)
        ld (ix+5),a
        ld (ix+4),0
        ld a,(FILL_BASE)
        cp FILL_VALUE
        jr nz,df_bad
        ld a,(FILL_BASE+FILL_LEN/2)
        cp FILL_VALUE
        jr nz,df_bad
        ld a,(FILL_BASE+FILL_LEN-1)
        cp FILL_VALUE
        jr z,df_next
df_bad:
        ld (ix+4),1
        ld hl,s_bad
        call print_str
df_next:
        ld de,6
        add ix,de
        ld a,(cur_row)
        inc a
        ld (cur_row),a
        ret
fill_page:
        db 0

; ---- fill (a): unrolled ld (de),a ; inc e (11 T per byte, draw_b.asm dr_span_fill style). A = value. T = 156231 incl. call
fill_cpu:
        ld de,FILL_BASE
        ld c,48
fc_page:
        ld b,32
fc_run:
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        inc e
        djnz fc_run
        inc d
        dec c
        jr nz,fc_page
        ret

; ---- fill (b): LDIR shifted by one. T = 258086 incl. call
fill_ldir:
        ld hl,FILL_BASE
        ld de,FILL_BASE+1
        ld (hl),a
        ld bc,FILL_LEN-1
        ldir
        ret

; ---- fill (c): plain zxnDMA, port A memory FIXED at fill_val (WR1 = 24h), 3-cycle default. Works on every core.
fill_zxndma:
        ld (fill_val),a
        ld hl,dma_plain
        ld bc,PLAIN_LEN*256+DMA_PORT
        otir
        ret
dma_plain:
        db 83h,0C3h                 ; stop, reset (guide note 1)
        db 7Dh                      ; WR0: A to B, port A address and length follow
        dw fill_val
        dw FILL_LEN
        db 24h                      ; WR1: port A memory, fixed address (the source of a fill)
        db 10h                      ; WR2: port B memory, up
        db 0ADh                     ; WR4: continuous, port B address follows
        dw FILL_BASE
        db 82h                      ; WR5: stop at the end
        db 0CFh,87h                 ; load, go
dma_plain_end:
PLAIN_LEN   equ dma_plain_end-dma_plain
fill_val:
        db 0

; ---- fill (d): zxnDDMA fill mode ($DF bit 3, $F7 value), 3-cycle default timing, MMU addresses (no physical flag)
fill_ddma3:
        ld (ddma3_val),a
        ld hl,dma_ddma3
        ld bc,DDMA3_LEN*256+DMA_PORT
        otir
        ret
dma_ddma3:
        db 83h,0C3h                 ; stop, reset
        db 0DFh,08h                 ; zxnDDMA mode flags: fill (bit 3) only
        db 0F7h                     ; zxnDDMA fill value:
ddma3_val:
        db 0
        db 65h                      ; WR0: A to B, block length follows (fill mode never reads port A)
        dw FILL_LEN
        db 14h                      ; WR1: memory, up (3 cycles after reset)
        db 10h                      ; WR2: memory, up
        db 0ADh                     ; WR4: continuous, port B address follows
        dw FILL_BASE
        db 82h                      ; WR5: stop at the end
        db 0CFh,87h                 ; load, go
dma_ddma3_end:
DDMA3_LEN   equ dma_ddma3_end-dma_ddma3

; ---- fill (e): the same with 2-cycle timing on both ports (WR1 54h,02h ; WR2 50h,02h)
fill_ddma2:
        ld (ddma2_val),a
        ld hl,dma_ddma2
        ld bc,DDMA2_LEN*256+DMA_PORT
        otir
        ret
dma_ddma2:
        db 83h,0C3h
        db 0DFh,08h
        db 0F7h
ddma2_val:
        db 0
        db 65h
        dw FILL_LEN
        db 54h,02h                  ; WR1: memory, up, timing byte: 2 cycles
        db 50h,02h                  ; WR2: memory, up, timing byte: 2 cycles
        db 0ADh
        dw FILL_BASE
        db 82h
        db 0CFh,87h
dma_ddma2_end:
DDMA2_LEN   equ dma_ddma2_end-dma_ddma2

; ---------------------------------------------------------------------------------------------------------------
; detect - zxnddma_compare.asm lines 181-199 translated verbatim; have_ddma = 0 / 1 (/ 2 when FORCE_FOUND).
; Also records probe_to and the page-60 byte in R_PROBE.
; ---------------------------------------------------------------------------------------------------------------
detect:
        xor a
        ld (have_ddma),a
        ld (probe_to),a             ; clear the two places the byte can land
        db 0EDh,091h,57h,60         ; nextreg $57,PROBE_PAGE
        ld (0E000h+PROBE_OFF),a
        ld hl,detect_dma
        ld bc,DETECT_LEN*256+DMA_PORT
        otir
        ld a,(0E000h+PROBE_OFF)
        ld (R_PROBE+1),a
        ld a,(probe_to)
        ld (R_PROBE),a
        db 0EDh,091h,57h,1          ; restore slot 7 (8K page 1)
        if FORCED
        ld a,2
        ld (have_ddma),a
        ret
        endif
        ld a,(R_PROBE+1)
        cp MARKER
        ret nz                      ; not there: no zxnDDMA
        ld a,1
        ld (have_ddma),a
        ret

; ---------------------------------------------------------------------------------------------------------------
; cpu_chunk - register-only loop, 50219 T including the call (see the header)
; ---------------------------------------------------------------------------------------------------------------
cpu_chunk:
        ld c,15
cc_outer:
        ld b,0
cc_inner:
        djnz cc_inner
        dec c
        jr nz,cc_outer
        ret

; ---------------------------------------------------------------------------------------------------------------
; mem_chunk - 8-way unrolled ld (hl),a ; inc l into a 256-byte page, 48796 T including the call. Position independent
; (copied to BLK_CODE; the 'ld hl' operand at +1 is patched to BLK_BUF there).
; ---------------------------------------------------------------------------------------------------------------
mem_chunk:
        ld hl,SRAM_BUF
        ld a,55h
        ld c,15
mc_outer:
        ld b,32
mc_inner:
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        djnz mc_inner
        dec c
        jr nz,mc_outer
        ret
mem_chunk_end:

; ---------------------------------------------------------------------------------------------------------------
; timed_run - HL = chunk routine. Waits for video line 0, calls it N_CHUNKS times, reads the line after each call and
; counts wraps. Out: HL = total lines = wraps x LPF + last line.
; ---------------------------------------------------------------------------------------------------------------
timed_run:
        ld (tr_call+1),hl
        ld hl,N_CHUNKS
        ld (tr_n),hl
        ld hl,0
        ld (tr_wraps),hl
        ld (tr_prev),hl
        call wait_line0
tr_loop:
tr_call:
        call 0
        call read_line              ; HL = line
        ld de,(tr_prev)
        ld (tr_prev),hl
        or a
        sbc hl,de
        jr nc,tr_nowrap
        ld hl,(tr_wraps)
        inc hl
        ld (tr_wraps),hl
tr_nowrap:
        ld hl,(tr_n)
        dec hl
        ld (tr_n),hl
        ld a,h
        or l
        jr nz,tr_loop
        ld hl,(tr_wraps)
        ld de,(R_LPF)
        call mul16                  ; HL = wraps x LPF (low word)
        ld de,(tr_prev)
        add hl,de
        ret
tr_n:
        dw 0
tr_wraps:
        dw 0
tr_prev:
        dw 0

; mhz_from_lines: HL = lines, DE -> K table (4 words: K224 lo, hi, K228 lo, hi) -> HL = MHz x 10 = K / lines
mhz_from_lines:
        ld b,h
        ld c,l                      ; BC = lines
        ld a,(R_TLINE)
        cp 228 and 0FFh
        jr nz,mf_224
        inc de
        inc de
        inc de
        inc de
mf_224:
        ex de,hl
        ld de,dvd
        push bc
        ld bc,4
        ldir
        pop bc
        ld a,b
        or c
        jr z,mf_zero                ; no lines: avoid dividing by 0
        ld h,b                      ; round: dividend += lines / 2
        ld l,c
        srl h
        rr l
        ld de,(dvd)
        add hl,de
        ld (dvd),hl
        jr nc,mf_div
        ld hl,(dvd+2)
        inc hl
        ld (dvd+2),hl
mf_div:
        call div32
        ld hl,(dvd)
        ret
mf_zero:
        ld hl,0
        ret
k_cpu:
        dw 0BAEh,000Ch              ; 789422 = round(5052300 x 35 / 224)
        dw 0D596h,000Bh             ; 775574 = round(5052300 x 35 / 228)
k_mem:
        dw 0B4D4h,000Bh             ; 767188 = round(4910000 x 35 / 224)
        dw 8040h,000Bh              ; 753728 = round(4910000 x 35 / 228)

; print_mhz_line: A = row, HL = label, DE -> (lines word, MHz x 10 word)
print_mhz_line:
        push de
        call locate
        call print_str
        pop de
        push de
        ex de,hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld b,4
        call print_dec
        ld hl,s_ln
        call print_str
        pop hl
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        call print_tenths
        ld hl,s_mhz
        jp print_str

; ---------------------------------------------------------------------------------------------------------------
; video line helpers (nextreg 1Eh bit 0 : 1Fh), zxnddma_compare.asm read_line logic
; ---------------------------------------------------------------------------------------------------------------
; read_line -> HL = current video line. 162 T without a retry (+ call 17). Destroys A, BC.
read_line:
        ld bc,243Bh
        ld a,1Eh
        out (c),a
        inc b
        in a,(c)
        and 1
        ld h,a
        dec b
        ld a,1Fh
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,1Eh
        out (c),a
        inc b
        in a,(c)
        and 1
        cp h
        jr nz,read_line
        ret

; wait_line0: wait until the line is not 0, then until it is 0 again (returns within one read of the start of line 0)
wait_line0:
        call read_line
        ld a,h
        or l
        jr z,wait_line0
wl_zero:
        call read_line
        ld a,h
        or l
        jr nz,wl_zero
        ret

; measure_lpf -> HL = lines per frame: from line 0, track the largest line seen until the counter returns to 0
measure_lpf:
        call wait_line0
        ld de,0
ml_loop:
        call read_line
        ld a,h
        or l
        jr z,ml_zero
        ex de,hl                    ; DE = last non-zero line
        jr ml_loop
ml_zero:
        ld a,d
        or e
        jr z,ml_loop                ; still in line 0
        ex de,hl
        inc hl
        ret

; rd_nextreg: A = register -> A = value
rd_nextreg:
        ld bc,243Bh
        out (c),a
        inc b
        in a,(c)
        ret

; ---------------------------------------------------------------------------------------------------------------
; arithmetic
; ---------------------------------------------------------------------------------------------------------------
; mul16: HL x DE -> DE:HL (32 bits). Destroys A, BC.
mul16:
        ld c,l
        ld b,h
        ld hl,0
        ld a,16
mu_loop:
        add hl,hl
        rl e
        rl d
        jr nc,mu_skip
        add hl,bc
        jr nc,mu_skip
        inc de
mu_skip:
        dec a
        jr nz,mu_loop
        ret

; div32: 32-bit dividend at dvd (little endian) / BC -> quotient at dvd, remainder HL. Destroys A, IX is NOT used (IY/IX
; are the fill loop's) - the dividend is addressed through HL' ... pasmo: use absolute addressing.
div32:
        ld hl,0
        ld a,32
dv_loop:
        push af
        ld a,(dvd)
        sla a
        ld (dvd),a
        ld a,(dvd+1)
        rla
        ld (dvd+1),a
        ld a,(dvd+2)
        rla
        ld (dvd+2),a
        ld a,(dvd+3)
        rla
        ld (dvd+3),a                ; carry = bit 31 out
        adc hl,hl                   ; remainder = remainder x 2 + bit ; carry = 17th bit
        jr c,dv_fits
        sbc hl,bc                   ; carry is clear here
        jr nc,dv_fits2
        add hl,bc
        jr dv_next
dv_fits:
        or a
        sbc hl,bc
dv_fits2:
        ld a,(dvd)
        or 1
        ld (dvd),a
dv_next:
        pop af
        dec a
        jr nz,dv_loop
        ret
dvd:
        dw 0,0

; div16: HL / BC -> HL = quotient, DE = remainder (BC <= 32767). Destroys A.
div16:
        ld de,0
        ld a,16
d16_loop:
        add hl,hl
        ex de,hl
        adc hl,hl
        or a
        sbc hl,bc
        jr nc,d16_fit
        add hl,bc
        ex de,hl
        jr d16_next
d16_fit:
        ex de,hl
        inc hl
d16_next:
        dec a
        jr nz,d16_loop
        ret

; ---------------------------------------------------------------------------------------------------------------
; text output: ULA screen, 48K ROM font (3D00h + 8 x (c - 32) = 3C00h + 8 x c)
; ---------------------------------------------------------------------------------------------------------------
; locate: A = row -> cursor at (row, 0)
locate:
        ld (cur_row),a
        xor a
        ld (cur_col),a
        ret

; print_str: HL -> zero-terminated text
print_str:
        ld a,(hl)
        or a
        ret z
        call print_char
        inc hl
        jr print_str

; print_char: A = character 32..127 at the cursor; cursor column + 1. Preserves HL, DE, BC.
print_char:
        push hl
        push de
        push bc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,3C00h
        add hl,de                   ; HL = glyph
        ld a,(cur_row)
        and 18h
        or 40h
        ld d,a
        ld a,(cur_row)
        and 07h
        rrca
        rrca
        rrca                        ; (row and 7) x 32
        ld e,a
        ld a,(cur_col)
        or e
        ld e,a                      ; DE = screen address of the cell's first pixel row
        ld b,8
pc_row:
        ld a,(hl)
        ld (de),a
        inc hl
        inc d
        djnz pc_row
        ld a,(cur_col)
        inc a
        ld (cur_col),a
        pop bc
        pop de
        pop hl
        ret

; print_dec: HL = value, B = minimum width (1..5), padded with spaces on the left. print_dec0: padded with zeros.
print_dec0:
        ld a,'0'
        jr pd_go
print_dec:
        ld a,' '
pd_go:
        ld (pad_char),a
        push bc
        ld de,dec_buf
        ld bc,10000
        call pd_digit
        ld bc,1000
        call pd_digit
        ld bc,100
        call pd_digit
        ld bc,10
        call pd_digit
        ld a,l
        add a,'0'
        ld (de),a
        pop bc
        ld a,5
        sub b
        ld c,a                      ; C = first position the width needs (5 - B)
        ld hl,dec_buf
        ld b,0                      ; B = 0 while still skipping leading zeros
        ld e,0                      ; E = position 0..4
pd_out:
        ld a,(hl)
        cp '0'
        jr nz,pd_digit_on
        ld a,b
        or a
        jr nz,pd_print0             ; a zero after a printed digit
        ld a,e
        cp 4
        jr z,pd_print0              ; the units digit is always printed
        cp c
        jr c,pd_skip                ; before the width: nothing
        ld a,(pad_char)
        call print_char
        jr pd_skip
pd_print0:
        ld a,'0'
        call print_char
        jr pd_skip
pd_digit_on:
        ld b,1
        call print_char
pd_skip:
        inc hl
        inc e
        ld a,e
        cp 5
        jr nz,pd_out
        ret
pd_digit:
        ld a,'0'-1
pd_sub:
        inc a
        or a
        sbc hl,bc
        jr nc,pd_sub
        add hl,bc
        ld (de),a
        inc de
        ret

; print_tenths: HL = value in tenths -> "nn.n" (whole part width 2, space padded)
print_tenths:
        ld bc,10
        call div16                  ; HL = whole, DE = tenths
        push de
        ld b,2
        call print_dec
        ld a,'.'
        call print_char
        pop de
        ld a,e
        add a,'0'
        jp print_char

; ---------------------------------------------------------------------------------------------------------------
; data
; ---------------------------------------------------------------------------------------------------------------
cur_row:    db 0
cur_col:    db 0
vid_timing: db 0
pad_char:   db ' '
dec_buf:    db 0,0,0,0,0
; ULA palette, 8-bit RRRGGGBB: ink 0..7, bright ink 8..15, paper 0..7, bright paper 8..15
ula_pal:
        db 000h,002h,0A0h,0A2h,014h,016h,0B4h,0B6h
        db 000h,003h,0E0h,0E3h,01Ch,01Fh,0FCh,0FFh
        db 000h,002h,0A0h,0A2h,014h,016h,0B4h,0B6h
        db 000h,003h,0E0h,0E3h,01Ch,01Fh,0FCh,0FFh
s_title:    db "KILLEMALL NEXT HWTEST H1 RUN ",0
s_machine:  db "MACHINE ",0
s_core:     db " CORE ",0
s_board:    db " BOARD ",0
s_video:    db "VIDEO ",0
s_lines:    db " LINES TIMING ",0
s_50hz:     db " 50HZ",0
s_60hz:     db " 60HZ",0
s_found:    db "ZXNDDMA FOUND",0
s_forced:   db "ZXNDDMA FORCED (NO PROBE)",0
s_notfound: db "ZXNDDMA NOT FOUND ",0
s_plainok:  db "(PLAIN DMA OK)",0
s_nodma:    db "(NO DMA)",0
s_cpu:      db "CPU LOOP     ",0
s_sram:     db "MEM SRAM     ",0
s_blk:      db "MEM BLOCKRAM ",0
s_ln:       db " LN  ",0
s_mhz:      db " MHZ",0
s_fill:     db "FILL ",0
s_f_cpu:    db "CPU    ",0
s_f_ldir:   db "LDIR   ",0
s_f_zxndma: db "ZXNDMA ",0
s_f_ddma3:  db "DDMA3  ",0
s_f_ddma2:  db "DDMA2  ",0
s_sram_t:   db "SRAM ",0
s_blk_t:    db "BLK  ",0
s_us:       db " US",0
s_bad:      db " BAD",0
s_skipped:  db "SKIPPED",0
s_warn60:   db "WARNING 60 HZ VIDEO",0
s_press:    db "PRESS R TO REPEAT",0
code_end:
