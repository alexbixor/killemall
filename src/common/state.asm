; state.asm - shared game state block (T1, frozen contract ARCH_M2.md). Other lanes read these labels.
; frames/ticks stay in kea48.asm (existing).
health:     defb 100        ; 0..100
ammo:       defb 50
keys:       defb 0          ; b0 red, b1 blue
kills:      defb 0
level:      defb 0          ; 0-based
opt_music:  defb 1
opt_sfx:    defb 1
opt_detail: defb 1          ; 1 dithered floor, 0 plain
opt_joy:    defb 0          ; 0 keyboard, 1 Kempston
in_break:   defb 0
shield:     defb 0          ; M2.2: 0..100, absorbs enemy hits while > 0 (shield pickup type 20, game_c.asm pi2)
        IF DEFINED MOUSE
opt_mouse:  defb 0          ; lane M (5 Nov 2026): 0 off, 1 mouse look (Kempston mouse / Next PS/2); 128K+Next builds only
        ENDIF                   ; (pasmo --equ MOUSE=1); appended so no other label moves, the 48K image is byte-identical
; M2.2: RAM-only tables live in the dead BASIC area 0x5D00..0x5FFF (PROG/VARS of the loader, never used again after
; RANDOMIZE USR 32768; the ROM tape loader only touches the stack) instead of the code image: 448 B less tape and 448 B more
; room for code in the high block. Every table below is written before it is read (things_init, render, ds_cols, ...).
DRAM        equ 0x5D00
ROWTAB      equ DRAM            ; 50 B (25 words), page aligned: sprites_f does ld h,ROWTAB/256 with L = source row
CMIN        equ DRAM+0x20       ; M2.6 P2E: 24 x (12 - first marked cell row | 0 = none, ink << 4 | last row + 1) sprite colour
                                ; marks per byte column (lowcode.asm dc_mark, attr.asm attr_write): 48 B 0x5D20..0x5D4F, one
                                ; page (ROWTAB holds 25 BYTES, 0x5D00..0x5D18; the old 32 B ds_rmin/ds_rmax slot is inside this range)
zbuf        equ DRAM+0x60       ; 64 B: per ray column wall virtual height 0..255 (0 = none)
things      equ DRAM+0xA0       ; NTHINGS*8 = 128 B runtime thing table (sprites.asm things_init)
        IF DEFINED LEVELS8
; lane K1 (6 Nov 2026, 128K only, pasmo --equ LEVELS8=1): NTHINGS 36 -> things grows in place to 288 B (0x5DA0..0x5EBF),
; so vis moves below DRAM into the dead 128K editor page (0x5B60..0x5BBF; only BANKM 0x5B5C lives there) and door_log +
; fe_tmpk take the old spare 0x5EC0..0x5EFF. The relocated low code block (lowcode.asm, LOWCODE 0x5BC0..) follows vis;
; the FLIP stack (FSTACK 0x5D00, grows down) keeps 0x5C26..0x5CFF (218 B, measured depth 16 B + ISR frames).
vis         equ 0x5B60          ; VISMAX*6 = 96 B vis list (sprites_b.asm)
LOWCODE     equ 0x5BC0          ; run-time copy of the low code block (src/128k/lowcode128.asm image in bank 1, B1_BOOT)
door_log    equ DRAM+0x1C0      ; 48 B = 16 x (cell ptr, code) opened doors (game_b.asm): 0x5EC0..0x5EEF
fe_tmpk     equ DRAM+0x1F0      ; 16 B key redefine scratch (frontend.asm): 0x5EF0..0x5EFF
        ELSE
vis         equ DRAM+0x120      ; VISMAX*6 = 96 B vis list (sprites_b.asm)
door_log    equ DRAM+0x180      ; 48 B = 16 x (cell ptr, code) opened doors (game_b.asm)
fe_tmpk     equ DRAM+0x1B0      ; 16 B key redefine scratch (frontend.asm)
        ENDIF
DRAM_END    equ DRAM+0x1C0      ; 0x5EC0; 0x5EC0..0x5EFF spare (LEVELS8: door_log + fe_tmpk); 0x5F00..0x5FFF = SOLIDPG (kea48.asm, far-wall solid texture)
