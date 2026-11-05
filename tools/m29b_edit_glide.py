#!/usr/bin/env python3
"""m29b_edit_glide.py - M2.9b (4 Nov 2026): camera glide between game steps, 128K and Next builds only (pasmo --equ GLIDE=1;
the 48K source assembles byte-identical because every change sits inside IF DEFINED GLIDE ... ENDIF).
Idempotent scripted edit of: src/48k/kea48.asm (main loop glide_in/glide_out around render; steps returns instead of halting),
src/common/game_d.asm (st_one marks the step start; glide code block), src/common/sprites.asm (things_init marks the level
start), tools/build128.sh (--equ GLIDE=1). Originals: build/pre_m29b/. Run twice -> second run changes nothing."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]

GLIDE_BLOCK = r'''
; ---------------------------------------------------------------- M2.9b glide (128K / Next builds only: pasmo --equ GLIDE=1)
; The game steps 10 times a second (steps / st_one). A machine that draws faster than that would show identical frames, so
; the camera is drawn at the position the player had at the START of the last step, moved toward its END by the fraction
; of the step time that has passed: (ticks - step_t) / STEP. The true position never changes: glide_in parks the true
; values in tpx..tfl and writes the camera values into posx/posy/angle/fl_ph for render; glide_out puts the true values
; back before the game logic runs. A machine slower than 10 steps/s also gains: its camera moves by the time elapsed,
; not by whole steps. ~170 B; the 48K build has none of it (41 B free until M3.0 moves level data to the SD card).
        IF DEFINED GLIDE
glide_render:                  ; main loop: camera glide around render (keeps the code before COLBASE the same size)
        call glide_in
        call render
        jp glide_out
glide_mark:                    ; st_one (before game_tick) and things_init: remember where this step starts
        ld hl,posx
        ld de,opx
        ld bc,5                ; posx, posy, angle are consecutive (kea48.asm)
        ldir
        ld a,(fl_ph)
        ld (ofl),a
        ret
glide_in:
        ld hl,posx             ; true values -> tpx, tpy, tang, tfl
        ld de,tpx
        ld bc,5
        ldir
        ld a,(fl_ph)
        ld (tfl),a
        ld a,(ticks)
        ld hl,step_t
        sub (hl)               ; ticks since the last step boundary: 0..STEP-1 after steps returned (an ISR may add 1: clamp)
        cp STEP
        jr c,gi1
        ld a,STEP-1
gi1:    ld hl,FRACTAB
        add a,l
        ld l,a
        jr nc,gi2
        inc h
gi2:    ld c,(hl)              ; C = elapsed / STEP in 1/256
        ld hl,(posx)
        ld de,(opx)
        call lerp16
        ld (posx),hl
        ld hl,(posy)
        ld de,(opy)
        call lerp16
        ld (posy),hl
        ld a,(angle)
        ld hl,oang
        call lerp8v
        ld (angle),a
        ld a,(fl_ph)
        ld hl,ofl
        call lerp8v
        ld (fl_ph),a
        ret
glide_out:
        ld hl,tpx
        ld de,posx
        ld bc,5
        ldir
        ld a,(tfl)
        ld (fl_ph),a
        ret
lerp16: or a                   ; HL = now, DE = at step start, C = fraction -> HL = DE + (HL - DE) * C / 256
        sbc hl,de
        ld a,l                 ; one step moves < 0.25 cell per axis: the difference fits a signed byte
        push de
        call lerp8
        pop de
        ld l,a                 ; sign-extend A into HL, add the start value
        rla
        sbc a,a
        ld h,a
        add hl,de
        ret
lerp8v: sub (hl)               ; A = now, (HL) = at step start -> A = (HL) + (A - (HL)) * C / 256 (8-bit, wraps: angles)
        push hl
        call lerp8
        pop hl
        add a,(hl)
        ret
lerp8:  or a                   ; A = signed difference, C = fraction -> A = A * C / 256 (signed, toward zero)
        jp p,l8p
        neg
        call mul8
        ld a,h
        neg
        ret
l8p:    call mul8
        ld a,h
        ret
mul8:   ld hl,0                ; HL = A * C (unsigned 8 x 8); keeps C
        ld d,0
        ld e,c
        ld b,8
m8l:    add hl,hl
        rla
        jr nc,m8n
        add hl,de
m8n:    djnz m8l
        ret
FRACTAB: defb 0,51,102,154,205 ; elapsed 0..4 ticks of a 5-tick step, in 1/256
opx:    defw 0                 ; position, angle and floor phase at the start of the last step
opy:    defw 0
oang:   defb 0
ofl:    defb 0
tpx:    defw 0                 ; true values parked while render draws the glided camera
tpy:    defw 0
tang:   defb 0
tfl:    defb 0
        ENDIF
'''

EDITS = [
    ("src/48k/kea48.asm",
     "        call render\n        call steps             ; M2.9 (4 Nov 2026): fixed-rate game logic, 10 steps/s on every machine (below)\n",
     "        IF DEFINED GLIDE\n        call glide_render      ; M2.9b (128K/Next): glide_in, render, glide_out (game_d.asm) - same 3 B as call render\n"
     "        ELSE\n        call render\n        ENDIF\n"
     "        call steps             ; M2.9 (4 Nov 2026): fixed-rate game logic, 10 steps/s on every machine (below)\n"),
    ("src/48k/kea48.asm",
     "        jp nc,st_two           ; >= 1 step due: game_d.asm st_two (split: code before COLBASE has only 7 B page slack)\n"
     "        halt                   ; too early for a step: wait for the next 50 Hz interrupt (isr: ticks + 1), then look again\n"
     "        jr steps\n",
     "        jp nc,st_two           ; >= 1 step due: game_d.asm st_two (split: code before COLBASE has only 7 B page slack)\n"
     "        IF DEFINED GLIDE\n"
     "        ret                    ; M2.9b: no step due -> draw another frame (the camera glides); 128K/Next only\n"
     "        ELSE\n"
     "        halt                   ; too early for a step: wait for the next 50 Hz interrupt (isr: ticks + 1), then look again\n"
     "        jr steps\n"
     "        ENDIF\n"),
    ("src/common/game_d.asm",
     "st_one: ld a,(hl)              ; HL = step_t: step_t += STEP, then the game logic (tail call)\n        add a,STEP\n        ld (hl),a\n        jp game_tick\n",
     "st_one: ld a,(hl)              ; HL = step_t: step_t += STEP, then the game logic (tail call)\n        add a,STEP\n        ld (hl),a\n"
     "        IF DEFINED GLIDE\n        call glide_mark        ; M2.9b: this step starts here (camera glides from it during the next frames)\n        ENDIF\n"
     "        jp game_tick\n"),
    ("src/common/game_d.asm",
     "; msg_clear / msg_dead live in ../common/lowcode.asm since M2.8 (3 Nov 2026): 23 B moved out of the high block to pay for strafe.",
     "; msg_clear / msg_dead live in ../common/lowcode.asm since M2.8 (3 Nov 2026): 23 B moved out of the high block to pay for strafe." + GLIDE_BLOCK),
    ("src/common/sprites.asm",
     "things_init:\n        ld hl,CMIN             ; M2.6 P2E: no sprite colour marks at the start of a level (48 B)\n",
     "things_init:\n        IF DEFINED GLIDE\n        call glide_mark        ; M2.9b: no stale camera on the first frame of a level\n        ENDIF\n"
     "        ld hl,CMIN             ; M2.6 P2E: no sprite colour marks at the start of a level (48 B)\n"),
    ("tools/build128.sh",
     "( cd src/48k && pasmo --tap ../128k/kea128_gen.asm ../../build/kea128.tap ../../build/kea128.sym )",
     "( cd src/48k && pasmo --equ GLIDE=1 --tap ../128k/kea128_gen.asm ../../build/kea128.tap ../../build/kea128.sym )   # M2.9b: camera glide (128K/Next only)"),
]

changed = 0
for rel, old, new in EDITS:
    p = ROOT / rel; s = p.read_text()
    if new in s and (old in new or old not in s):
        print("  = %s: already applied" % rel); continue
    if old not in s:
        sys.exit("ANCHOR MISSING in %s: %r" % (rel, old[:70]))
    if s.count(old) != 1:
        sys.exit("ANCHOR NOT UNIQUE in %s: %r" % (rel, old[:70]))
    p.write_text(s.replace(old, new, 1)); changed += 1
    print("  + %s: edited" % rel)
print("m29b_edit_glide: %d file edit(s) applied" % changed)
