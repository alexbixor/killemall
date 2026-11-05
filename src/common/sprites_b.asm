; sprites_b.asm (T1) - per-thing camera transform -> visible list (sorted far to near), then draw.
; vis entry (6 bytes): +0 hv (virtual height 2..192) +1 c0 (s8 left ray column) +2 nc (columns) +3 sprite data ptr (word) +5 thing idx
VISMAX  equ 16
; thing type -> base sprite id (enemies add 0/1 walk, 2 attack, 3 dead)
THSPR:  defb 0,0,4,4,4,4,4,0, 0,0,0,0,0,0,0,0, 8,9,10,11,8,12,13,13
; mul16: DE * BC -> DE:HL (unsigned 32-bit)
mul16:  ld hl,0
        ld a,16
m16_l:  add hl,hl
        rl e
        rl d
        jr nc,m16_n
        add hl,bc
        jr nc,m16_n
        inc de
m16_n:  dec a
        jr nz,m16_l
        ret
; draw_things: transform all things, build vis list, sort, draw. Uses cos7/sin7 = COSTAB/SINTAB >> 1 (s8).
draw_things:
        ld hl,(angidx)
        ld de,COSTAB
        add hl,de
        call half_s8
        ld (cos7),a
        ld hl,(angidx)
        ld de,SINTAB
        add hl,de
        call half_s8
        ld (sin7),a
        xor a
        ld (nvis),a
        ld ix,things
        ld b,NTHINGS
dt_l:   push bc
        ld a,(ix+0)
        or a
        jr z,dt_next
        call thing_xform
dt_next:
        ld de,8
        add ix,de
        pop bc
        djnz dt_l
        call vis_sort_draw
        jp draw_weapon
; half_s8: HL -> s16 word (256 = 1.0) -> A = word/2 as s8 (128 = 1.0 clamped to 127)
half_s8:
        ld a,(hl)
        inc hl
        ld d,(hl)
        sra d
        rra
        bit 7,a
        ret z
        inc d
        dec d
        ret nz                 ; negative: fine
        ld a,127               ; +128 -> clamp
        ret
cos7:   defb 0
sin7:   defb 0
nvis:   defb 0
; vis: VISMAX*6 list -> DRAM (state.asm, M2.2)
; thing_xform: IX -> thing. Appends a vis entry when on screen.
thing_xform:
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,(posx)
        or a
        sbc hl,de
        ld (tdx),hl
        ld a,h                 ; cull |dx| >= 11 cells (Chebyshev) before the multiplies
        add a,11
        cp 22
        ret nc
        ld l,(ix+3)
        ld h,(ix+4)
        ld de,(posy)
        or a
        sbc hl,de
        ld (tdy),hl
        ld a,h
        add a,11
        cp 22
        ret nc
; depth t = dx*cos + dy*sin
        ld hl,(tdx)
        ld a,(cos7)
        call muls_7
        push hl
        ld hl,(tdy)
        ld a,(sin7)
        call muls_7
        pop de
        add hl,de
        ld (tdepth),hl
        bit 7,h
        ret nz                 ; behind
        ld a,h
        or a
        jr nz,tx1
        ld a,l
        cp 48
        ret c                  ; nearer than 0.19 cell
tx1:    jp thing_xform2
tdx:    defw 0
tdy:    defw 0
tdepth: defw 0
