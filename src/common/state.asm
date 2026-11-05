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
vis         equ DRAM+0x120      ; VISMAX*6 = 96 B vis list (sprites_b.asm)
door_log    equ DRAM+0x180      ; 48 B = 16 x (cell ptr, code) opened doors (game_b.asm)
fe_tmpk     equ DRAM+0x1B0      ; 16 B key redefine scratch (frontend.asm)
DRAM_END    equ DRAM+0x1C0      ; 0x5EC0; 0x5EC0..0x5EFF spare; 0x5F00..0x5FFF = SOLIDPG (kea48.asm, far-wall solid texture)
