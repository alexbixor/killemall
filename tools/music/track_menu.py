"""track_menu.py - Kill'em all 128K menu track (original, T3). Moody, slow, A minor, 32 bars, loops.

Notation (parsed by compile_music.py, see FORMAT.md for the binary form):
  per channel one string, tokens separated by whitespace, '|' is a cosmetic bar separator.
  C-4*8   note (C, octave 4) held for 8 rows (1 row = 1/16, 16 rows per bar)      C#4 / Db4 accidentals
  r*4     rest (note off, then empty rows)      -*4   hold the previous note 4 more rows
  @n      instrument n for the following notes  arpXY  arpeggio +X +Y semitones on following notes (arp00 = off)
  slN     pitch slide N (signed, period units per frame) on following notes (sl0 = off)
"""
SPEED = 8          # frames per row -> 93.75 bpm
ROWS = 32          # rows per pattern (2 bars)

INSTRUMENTS = [
    # name, mix (bit7 noise on + period in bits 0-4, bit6 tone off), loop, [(semitone_offset, volume) per frame]
    ("lead",  0x00, 7,  [(0, 13), (0, 13), (0, 12), (0, 12), (0, 11), (0, 11), (0, 10), (0, 10)]),
    ("bass",  0x00, 7,  [(0, 15), (0, 13), (0, 11), (0, 9), (0, 7), (0, 5), (0, 3), (0, 0)]),
    ("pad",   0x00, 11, [(0, 10), (0, 10), (0, 9), (0, 9), (0, 8), (0, 7), (0, 6), (0, 5), (0, 4), (0, 3), (0, 2), (0, 0)]),
    ("bell",  0x00, 9,  [(12, 14), (0, 13), (0, 11), (0, 10), (0, 9), (0, 8), (0, 7), (0, 6), (0, 4), (0, 0)]),
    ("soft",  0x00, 5,  [(0, 7), (0, 8), (0, 9), (0, 9), (0, 8), (0, 8)]),
]

# --- channel A: lead -------------------------------------------------------------------------------------
LEAD = """
@0
A-4*6 C-5*2 E-5*8   | D-5*4 C-5*4 B-4*8   | A-4*6 C-5*2 F-5*8   | E-5*4 D-5*4 B-4*8   |
A-4*6 C-5*2 E-5*4 A-5*4 | G-5*4 E-5*4 D-5*8 | C-5*6 D-5*2 C-5*8 | B-4*12 r*4          |
E-5*6 D-5*2 C-5*8   | B-4*4 C-5*4 A-4*8   | F-5*6 E-5*2 C-5*8   | D-5*4 B-4*4 G-4*8   |
F-5*6 E-5*2 D-5*8   | E-5*4 C-5*4 A-4*8   | G#4*4 B-4*4 E-5*8   | A-4*16              |
@3
E-5*16              | D-5*16              | C-5*16              | B-4*8 D-5*8         |
C-5*16              | B-4*16              | A-4*8 G#4*8         | A-4*16              |
@0
A-5*6 G-5*2 E-5*8   | D-5*4 E-5*4 C-5*8   | A-4*6 C-5*2 F-5*8   | E-5*4 D-5*4 B-4*8   |
F-5*6 E-5*2 D-5*8   | E-5*4 C-5*4 A-4*8   | G#4*4 B-4*4 E-5*4 D-5*4 | A-4*12 r*4      |
"""

# --- channel B: bass -------------------------------------------------------------------------------------
B_AM = "A-1*4 A-2*4 A-1*4 E-2*4"
B_F = "F-1*4 F-2*4 F-1*4 C-2*4"
B_G = "G-1*4 G-2*4 G-1*4 D-2*4"
B_E = "E-1*4 E-2*4 E-1*4 B-1*4"
B_DM = "D-1*4 D-2*4 D-1*4 A-1*4"
BASS = "@1 " + " | ".join([
    B_AM, B_AM, B_F, B_G, B_AM, B_AM, B_F, B_E,
    B_AM, B_AM, B_F, B_G, B_DM, B_AM, B_E, B_AM,
    B_AM, B_AM, B_F, B_G, B_AM, B_AM, B_E, B_AM,
    B_AM, B_AM, B_F, B_G, B_DM, B_AM, B_E, B_AM,
])

# --- channel C: arpeggiated chords (shared with SFX) ----------------------------------------------------
def chord(root, minor):
    return ("arp37 " if minor else "arp47 ") + "%s*8 %s*8" % (root, root)
C_AM = chord("A-3", True); C_F = chord("F-3", False); C_G = chord("G-3", False); C_E = chord("E-3", False); C_DM = chord("D-3", True)
CHORDS = "@2 " + " | ".join([
    C_AM, C_AM, C_F, C_G, C_AM, C_AM, C_F, C_E,
    C_AM, C_AM, C_F, C_G, C_DM, C_AM, C_E, C_AM,
    C_AM, C_AM, C_F, C_G, C_AM, C_AM, C_E, C_AM,
    C_AM, C_AM, C_F, C_G, C_DM, C_AM, C_E, C_AM,
])

SONG = {"name": "menu", "speed": SPEED, "rows": ROWS, "instruments": INSTRUMENTS,
        "channels": [LEAD, BASS, CHORDS], "bars": 32, "loop_bar": 0}
