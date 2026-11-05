# Kill'em all — AY music format "KAM1" (lane T3)

Compact 3-channel AY-3-8912 song format, compiled by `tools/music/compile_music.py` from Python note data
(`tools/music/track_menu.py`, `tools/music/track_game.py`) into `src/gen/music_data.asm`, played by
`src/128k/ay.asm` (`snd_isr`, once per frame). All pointers are absolute 16-bit little-endian (the data is
assembled together with the player; relocation is the assembler's job).

## Song header (8 bytes)
| off | size | field |
|---|---|---|
| 0 | 1 | `speed` — frames per row (50 Hz frames; rows are 16th notes, so bpm = 750 / speed) |
| 1 | 1 | `rows` — rows per pattern (all patterns of a song have the same length, 1..255) |
| 2 | 2 | `order` → order list: pattern indices (bytes), `0FFh`, then the loop index (position in the order list to continue from) |
| 4 | 2 | `patterns` → pattern table: per pattern 3 words = stream pointers for channels A, B, C |
| 6 | 2 | `instruments` → instrument table: 16 words (pointers to instrument headers) |

## Channel stream tokens (one stream per channel per pattern)
A row consists of zero or more *prefix* tokens followed by exactly one *terminator* token.
Every stream covers exactly `rows` rows (the compiler enforces it); nothing spans a pattern boundary.

| token | meaning |
|---|---|
| `80h+i` (i = 0..15) | prefix: select instrument i for the following notes |
| `90h, xy` | prefix: arpeggio effect — per frame the note cycles note, note+x, note+y semitones (x = high nibble, y = low). `00` = off |
| `91h, s` | prefix: pitch slide — signed `s` is added to the tone period every frame (negative = up) |
| `01h..5Fh` | terminator: **note on** (value = 12·(octave−1) + semitone + 1; `01h` = C1 … `5Fh` = A#8, B8 is not representable). Restarts the instrument envelope. Clears arpeggio and slide unless this row also carried a `90h`/`91h` prefix |
| `60h` | terminator: **note off** (channel volume 0 until the next note) |
| `61h..7Fh` | terminator: `n − 60h` **empty rows** (1..31): nothing changes on this channel for that many rows |

## Instrument header
| off | size | field |
|---|---|---|
| 0 | 1 | `mix`: bit 7 = noise on (noise period = bits 0..4, written to R6), bit 6 = tone off (noise-only), bit 5 = **hard-sync off** (reserved, 0) |
| 1 | 1 | `len` — envelope length in frames (1..255) |
| 2 | 1 | `loop` — frame index to continue from after the last frame (`len−1` = hold the last frame, i.e. sustain) |
| 3 | len | envelope frames: `(semitone_offset << 4) | volume` — volume 0..15 per frame, semitone offset 0..15 added to the note (instrument arpeggios / octave hits) |

Note off simply mutes the channel (no release stage) — put the decay into the envelope.

## Tone period
`period = ay_notes[note] + slide_accumulator`, `ay_notes[n] = round(1773400 / (16 · f_n))` (12-bit, generated into
`music_data.asm`, 96 words, index 0 unused). Arpeggio/instrument offsets index the same table (clamped to 95).

## AY register use
R0..R5 tone periods, R6 noise period (last noise instrument / SFX wins), R7 mixer (`3Fh` base, bits 6..7 = 0 →
I/O port A input, bit n cleared = tone n on, bit 3+n cleared = noise n on), R8..R10 volumes (software envelopes
only; no hardware envelope, so R11..R13 are never written). All 11 registers are written every frame from a
shadow block (`ay_regs`), first `OUT (0FFFDh)` = register, then `OUT (0BFFDh)` = value.

## Channel C / SFX
While an AY SFX is active (`snd_fx` on 128K enqueues it; the ISR plays it) channel C's R4, R5, R10, the mixer bits
2 and 5 and R6 are overridden by the SFX; the music keeps advancing silently on C and resumes when the SFX ends.
AY SFX definition (in `ay.asm`): segments of 10 bytes `frames, period(2), dperiod(2, signed/frame), vol(4.4 fixed),
dvol(signed 4.4/frame), noise period (0 = none), flags (bit 0 = tone on)`; a `frames = 0` byte ends the SFX.

## Size
Menu track and game track together ≤ 6 KB (actual numbers in `build/t3_report.md`); player code ≤ 1.5 KB.
