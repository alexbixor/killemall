; game_d.asm (T1) - level clear, death, restart. Milestone B placeholders: fire_action, things_tick (filled in C).
level_clear:
        ld a,9
        call snd_fx
        IF DEFINED FLIP
        call fl_show0          ; lane F rule F7: the message + wait happen on screen 0
        ENDIF
        ld hl,msg_clear
        call hud_message
        call hud_update
        ld b,100
        call wait_frames
        ld hl,level
        inc (hl)
        ld a,(hl)
        cp NLEVELS             ; T6: levels 2..3 come from tape (kea48.asm load_level)
        jr c,lc_next
        jp menu2               ; T6: all levels cleared -> menu over the frozen view (menu resets SP)
lc_next:
        inc a                  ; level id 1..3 = level + 1
        call load_level
        jp restart_level
player_dead:
        ld a,10
        call snd_fx
        IF DEFINED FLIP
        call fl_show0          ; lane F rule F7
        ENDIF
        ld hl,msg_dead
        call hud_message
        call hud_update
        ld b,100               ; 2 s
        call wait_frames
        ld a,100
        ld (health),a
        ld a,50
        ld (ammo),a
        xor a
        ld (keys),a
        ld (shield),a          ; M2.2
        jp restart_level
; restart_level: restore doors, reload the current level's header/things, redraw the HUD. Falls into main via ret.
restart_level:
        call doors_restore
        call init_game
        xor a
        ld (door_cool),a
        jp hud_init
; wait_frames: B = 50 Hz ticks to wait (interrupts on: level_clear / player_dead run from the main loop). M2.9: 4 B halt loop
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
        IF DEFINED GLIDE
        call glide_mark        ; M2.9b: this step starts here (camera glides from it during the next frames)
        ENDIF
        jp game_tick
; msg_clear / msg_dead live in ../common/lowcode.asm since M2.8 (3 Nov 2026): 23 B moved out of the high block to pay for strafe.
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

