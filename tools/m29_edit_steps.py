#!/usr/bin/env python3
"""m29_edit_steps.py - M2.9 (4 Nov 2026): the same game speed on the 48K, the 128K and the Next ("1 2 3" item 2).

Problem (build/m25_notes.md 'Open finding for M3.0'): game logic ran once per RENDERED frame (main: render, game_tick), so the
player walked 0.15 cell per frame = 1.35 cells/s on the 48K (9 fps), 0.98 cells/s on the 128K (6.5 fps) and 2.9 cells/s on
the Next at 28 MHz (19 fps, "unplayable"). Every timer (fire 12, door message 25, enemy attack 25, HUD message 100,
weapon flash 5) had the same machine-dependent length.

Fix = a fixed time step driven by the 50 Hz interrupt counter `ticks` (kea48.asm isr), standard "fixed step" game loop:
  STEP = 5 ticks = 0.1 s. After each rendered frame `steps` runs game_tick once per 5 ticks elapsed since the last step
  (step_t, low byte of ticks: an 8-bit difference is exact below 5.1 s and any longer gap is capped anyway):
    elapsed <  5 : the machine is faster than 10 frames/s (Next @ 28 MHz) -> halt (wait for the next interrupt), re-check.
                   Drawing the same picture again would gain nothing, so the display is capped at 10 frames/s = 1 step/frame.
    5 <= e < 10  : one step (48K: 5.5 ticks/frame -> mostly 1 step, every ~10th frame 2 -> 10.0 steps/s average).
    e >= 10      : backlog capped at 2 steps (128K: 7.7 ticks/frame alternates 1 / 2 steps; a pause menu, tape load or the
                   2 s YOU DIED wait never bursts: at most 2 steps on the first frame after it).
  Result: 10 game steps per second on all three machines; walking 1.5 cells/s; the timers above are now tenths of a second
  (fire 1.2 s, messages 2.5 s / 10 s, enemy hit every 2.5 s). The 48K feels as before (it was 9 steps/s), the 128K gets
  ~40 % faster (correct), the Next can run at 28 MHz (tools/mknex.py stub: nextreg 7,3 instead of 7,0).
  Enemy walk animation (sprites_d.asm) toggles on bit 4 of ticks (every 0.32 s) instead of bit 2 of frames (0.44 s @ 9 fps).

Cost on the 48K high block (42 B free before, gate >= 40): steps 47 B + animation 2 B = +49 B, paid by three savings (-48 B):
  print (kea48.asm) was a 31 B copy of hud_b.asm print_char -> 9 B loop around print_char (same bytes on screen, HL/DE contract
  unchanged; BC now preserved instead of destroyed, no caller relied on BC) ........................................ -22 B
  wait_frames (game_d.asm) 23 B tick arithmetic -> 4 B `halt / djnz` (callers run with interrupts on: level_clear, player_dead)
  ............................................................................................................... -19 B
  dead variables sidex, sidey, botr (kea48.asm), tlat (sprites_b.asm): defined, never read or written (tools/m23_deadcode.py;
  only the retired M1 tools patch_band.py / patch_attr.py mention botr) ............................................ -7 B
  -> expected hi_end 0xFDC7, 41 B free. 128K: 432 B free before, unaffected by the gate.
The 128K image is generated from the same source by tools/make128.py (anchors untouched: start:, isr:, includes, load_level:,
xor a / call snd_music). Tests: tools/test_steps.py (new, Z80 core, both images), tools/m25_gates.sh, ZEsarUX speed probe
tools/m29_speed_probe.py (48K vs 128K cells/s must match).
Idempotent: run twice -> 'changed: nothing'. Each anchor must occur exactly once."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
changed = []

def edit(rel, pairs, must=None):
    p = ROOT / rel; s = p.read_text(); o = s
    for old, new in pairs:
        if new in s and (old in new or old not in s): continue   # already applied (handles new extending old, and new inside old)
        if old not in s: sys.exit("%s: anchor not found:\n%s" % (rel, old))
        assert s.count(old) == 1, (rel, old)
        s = s.replace(old, new)
    if must and must not in s: sys.exit("%s: expected text missing: %s" % (rel, must))
    if s != o: p.write_text(s); changed.append(rel)

# ---- 1. main loop: call steps instead of game_tick -------------------------------------------------------------------
MAIN_OLD = """        call render
        call game_tick
        ld a,(in_break)
"""
MAIN_NEW = """        call render
        call steps             ; M2.9 (4 Nov 2026): fixed-rate game logic, 10 steps/s on every machine (below)
        ld a,(in_break)
"""
# ---- 2. the steps routine, after resume ------------------------------------------------------------------------------
RESUME_OLD = """resume:
        call apply_opts
        call hud_redraw        ; the menu used rows 16..23: restore the HUD
        jp main

"""
STEPS = """resume:
        call apply_opts
        call hud_redraw        ; the menu used rows 16..23: restore the HUD
        jp main

; M2.9 steps (tools/m29_edit_steps.py, 4 Nov 2026): fixed time step. game_tick runs once per STEP ticks of the 50 Hz counter
; (0.1 s) since the last step, whatever the frame rate: faster than a step (Next @ 28 MHz) -> halt until the next interrupt
; (the picture would not change anyway: display capped at 10 frames/s); slower -> up to 2 steps per frame, the rest of a
; backlog (pause menu, tape load, YOU DIED wait) is dropped so the game never bursts. step_t = low byte of ticks at the last
; step: the 8-bit difference is exact below 5.1 s and anything longer is capped to 2 steps anyway. Always runs >= 1 step,
; so in_break (read by game_tick's in_read) is fresh for the caller. 47 B. Interrupts must be on (they are in main).
STEP    equ 5                  ; ticks per game step = 10 steps/s; the only speed knob (movement 0.15 cell/step = 1.5 cells/s)
steps:  ld a,(ticks)
        ld hl,step_t
        sub (hl)               ; A = ticks elapsed since the last step (mod 256)
        cp 3*STEP
        jr c,st_ok
        ld a,(ticks)           ; backlog >= 3 steps (stall): forget it, keep exactly 2 (a 0..4 tick remainder is kept)
        sub 2*STEP
        ld (hl),a
        ld a,2*STEP
st_ok:  cp STEP
        jp nc,st_two           ; >= 1 step due: game_d.asm st_two (split: code before COLBASE has only 7 B page slack)
        halt                   ; too early for a step: wait for the next 50 Hz interrupt (isr: ticks + 1), then look again
        jr steps
step_t: defb 0

"""
# ---- 3. print: loop around print_char (hud_b.asm) instead of a copy of it -------------------------------------------
PRINT_OLD = """; print zero-terminated string HL at screen address DE (ROM font)
print:  ld a,(hl)
        or a
        ret z
        push hl
        push de
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,ROMFONT
        add hl,bc
        ld b,8
pr1:    ld a,(hl)
        ld (de),a
        inc hl
        inc d
        djnz pr1
        pop de
        inc e
        pop hl
        inc hl
        jr print
"""
PRINT_NEW = """; print zero-terminated string HL at screen address DE (ROM font). M2.9: a loop around hud_b.asm print_char (which preserves
; HL, BC and advances DE one cell) instead of a 31 B copy of it: 9 B, same bytes on screen, pays for `steps`.
print:  ld a,(hl)
        or a
        ret z
        call print_char
        inc hl
        jr print
"""
# ---- 4. dead variables ------------------------------------------------------------------------------------------------
VARS_OLD = """deltay:     defw 0
sidex:      defw 0
sidey:      defw 0
dsp:        defb 0
"""
VARS_NEW = """deltay:     defw 0
dsp:        defb 0
"""
BOTR_OLD = """topr:       defb 0
botr:       defb 0
col:        defb 0
"""
BOTR_NEW = """topr:       defb 0
col:        defb 0
"""
TLAT_OLD = """tdepth: defw 0
tlat:   defw 0"""                      # the file's last line (no trailing newline in sprites_b.asm)
TLAT_NEW = """tdepth: defw 0"""
# ---- 5. walk animation on ticks (time) instead of rendered frames ----------------------------------------------------
ANIM_OLD = """        ld a,(frames)
        rrca
        rrca
        and 1
        add a,c                ; chase: walk A/B every 4 frames
"""
ANIM_NEW = """        ld a,(ticks)           ; M2.9: time-based (bit 4 of the 50 Hz counter), the same on every machine
        rrca
        rrca
        rrca
        rrca
        and 1
        add a,c                ; chase: walk A/B every 16 ticks = 0.32 s (was every 4 rendered frames)
"""
# ---- 6. wait_frames: halt loop ---------------------------------------------------------------------------------------
WAIT_OLD = """; wait_frames: B = 50 Hz ticks to wait (interrupts on; render keeps the screen alive is not needed - static)
wait_frames:
        ld hl,(ticks)
        ld e,b
        ld d,0
        add hl,de              ; HL = target tick
wf_l:   ld de,(ticks)
        push hl
        or a
        sbc hl,de              ; target - now, > 0 while waiting
        pop hl
        ret z
        jp m,wf_ret
        jr wf_l
wf_ret: ret
"""
WAIT_NEW = """; wait_frames: B = 50 Hz ticks to wait (interrupts on: level_clear / player_dead run from the main loop). M2.9: 4 B halt loop
; (was 23 B of tick arithmetic), pays for `steps`.
wait_frames:
        halt
        djnz wait_frames
        ret
; st_two: second half of kea48.asm steps (M2.9). HL = step_t, at least one step due: run it, then a second one if still due.
st_two: call st_one
        ld a,(ticks)
        ld hl,step_t
        sub (hl)
        cp STEP
        ret c                  ; one step was enough
st_one: ld a,(hl)              ; HL = step_t: step_t += STEP, then the game logic (tail call)
        add a,STEP
        ld (hl),a
        jp game_tick
"""
# ---- 7. comments that said "frames" where the unit is now the 0.1 s step ----------------------------------------------
GA_OLD = "; game_a.asm (T1) - game tick: input via in_read contract"
GA_NEW = "; game_a.asm (T1) - game tick = one fixed 0.1 s step since M2.9 (kea48.asm steps): input via in_read contract"
GE_OLD = "; adjacent (< 0.7 cell) -> attack: timer counts 25 frames then damage 10 (imp) / 15 (zombie), snd 8 then 4."
GE_NEW = "; adjacent (< 0.7 cell) -> attack: timer counts 25 steps (2.5 s since M2.9) then damage 10 (imp) / 15 (zombie), snd 8 then 4."
# ---- 8. Next: 28 MHz --------------------------------------------------------------------------------------------------
NEX_OLD = """STUB = bytes([0xED, 0x91, 0x07, 0x00,                         # nextreg 7,0  (Z80N)                  CPU 3.5 MHz: the game is frame-paced and
                                                              #   was designed for 3.5 MHz; NextZXOS launches .nex files at 28 MHz (nreg 07 = 33H
                                                              #   measured in ZEsarUX, 19 fps instead of 7) and the NEX loader does not reset it.
"""
NEX_NEW = """STUB = bytes([0xED, 0x91, 0x07, 0x03,                         # nextreg 7,3  (Z80N)                  CPU 28 MHz (M2.9, 4 Nov 2026): the game logic
                                                              #   is a fixed 10 steps/s from the 50 Hz counter now (kea48.asm steps), so speed no
                                                              #   longer depends on the frame rate; the display is capped at 10 frames/s by the
                                                              #   halt wait. M2.7 forced 3.5 MHz (nextreg 7,0) because 28 MHz gave 19 fps = 3x too fast.
"""
REL_OLD = """  The loader sets the CPU to 3.5 MHz itself (NextZXOS normally launches programs at 28 MHz), so the game runs at the
  speed it was designed for. Measured in the emulator: about 10 frames per second on the Next, 7 on a real 128K."""
REL_NEW = """  The game speed is the same on every machine (10 game steps per second from the 50 Hz interrupt), so the Next runs
  at its full 28 MHz. Measured in the emulator: 10 frames per second on the Next, about 7 on a 128K, 9 on a 48K."""

edit("src/48k/kea48.asm", [(MAIN_OLD, MAIN_NEW), (RESUME_OLD, STEPS), (PRINT_OLD, PRINT_NEW), (VARS_OLD, VARS_NEW), (BOTR_OLD, BOTR_NEW)],
     must="step_t: defb 0")
edit("src/common/sprites_b.asm", [(TLAT_OLD, TLAT_NEW)])
edit("src/common/sprites_d.asm", [(ANIM_OLD, ANIM_NEW)])
edit("src/common/game_d.asm", [(WAIT_OLD, WAIT_NEW)], must="djnz wait_frames")
edit("src/common/game_a.asm", [(GA_OLD, GA_NEW)])
edit("src/common/game_e.asm", [(GE_OLD, GE_NEW)])
edit("tools/mknex.py", [(NEX_OLD, NEX_NEW)], must="0x07, 0x03")
edit("tools/make_release.py", [(REL_OLD, REL_NEW)])
print("changed:", ", ".join(changed) if changed else "nothing")
