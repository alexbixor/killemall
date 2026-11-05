#!/usr/bin/env python3
"""patch_ay2.py - T3: lower the snd_isr peak: (1) song start frame does not also decode; (2) faster register writes."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent.parent / "src/128k/ay.asm"
s = P.read_text()
# (1) mus_start: mus_tick = 5 so the start frame itself does nothing but set up (decodes on frames 1..3, first row on frame 4)
s = s.replace("""        ld a,4
        ld (mus_tick),a         ; decode A, B, C on the next 3 frames; first row sounds on the 4th""",
"""        ld a,5
        ld (mus_tick),a         ; this frame: setup only; decode A, B, C on the next 3 frames; first row on the 4th""")
s = s.replace("""        ld a,1
        ld (mus_on),a
        ret

; ---------------------------------------------------------------- music: one frame""",
"""        ld a,1
        ld (mus_on),a
        pop hl                  ; skip this frame's mus_frame (return to snd_isr past the 'call nz,mus_frame')
        jp isr_s2

; ---------------------------------------------------------------- music: one frame""")
s = s.replace("""isr_s1: ld a,(mus_on)
        or a
        call nz,mus_frame
        ld hl,(sfx_ptr)""", """isr_s1: ld a,(mus_on)
        or a
        call nz,mus_frame
isr_s2: ld hl,(sfx_ptr)""")
s = s.replace(""";   snd_music     A = 0 stop, 1 menu track, 2 game track. Honours opt_music (1/2 with opt_music = 0 -> stop).
;                 Non-blocking; the ISR picks the request up on its next call; the first row sounds 3 frames later.""",
""";   snd_music     A = 0 stop, 1 menu track, 2 game track. Honours opt_music (1/2 with opt_music = 0 -> stop).
;                 Non-blocking; the ISR picks the request up on its next call; the first row sounds 4 frames later.""")
# (2) register writes: OUTI-based (out (c),(hl) with B = high byte) is wrong here because B is the port high byte; keep
#     the out (c),e / out (c),a form but drop the per-register 'ld b,d' by using two pointers: not possible with one C.
#     Instead unroll fully once more but 12 registers with the loop counter test removed (saves 4 x 11 T): already tried
#     at 1539 B. Leave as is.
P.write_text(s)
print("patched")
