"""track_game.py - Kill'em all 128K in-game track (original, T3). Driving, fast, E minor, 32 bars, loops.
Same notation as track_menu.py. Channel C carries the drums (noise instruments) and is the one SFX pre-empt."""
SPEED = 5          # frames per row -> 150 bpm
ROWS = 32          # rows per pattern (2 bars)

INSTRUMENTS = [
    ("lead",  0x00, 7,  [(0, 15), (0, 14), (0, 13), (0, 12), (0, 12), (0, 11), (0, 11), (0, 11)]),
    ("bass",  0x00, 5,  [(0, 15), (0, 14), (0, 12), (0, 10), (0, 7), (0, 0)]),
    ("kick",  0x81, 5,  [(0, 15), (0, 13), (0, 10), (0, 6), (0, 3), (0, 0)]),          # noise 1 + low tone (slid down)
    ("snare", 0xC6, 6,  [(0, 14), (0, 12), (0, 9), (0, 6), (0, 4), (0, 2), (0, 0)]),   # noise 6, tone off
    ("hat",   0xC1, 2,  [(0, 7), (0, 4), (0, 0)]),                                      # noise 1, tone off
    ("stab",  0x00, 4,  [(12, 14), (7, 13), (0, 12), (0, 9), (0, 0)]),                  # octave/fifth stab
    ("pad",   0x00, 3,  [(0, 9), (0, 10), (0, 10), (0, 10)]),
]

# --- channel A: riff / lead -----------------------------------------------------------------------------
RIFF_E = "E-3*2 E-3*2 G-3*2 E-3*2 B-3*2 E-3*2 D-4*2 B-3*2"
RIFF_C = "C-3*2 C-3*2 E-3*2 C-3*2 G-3*2 C-3*2 B-3*2 G-3*2"
RIFF_D = "D-3*2 D-3*2 F#3*2 D-3*2 A-3*2 D-3*2 C-4*2 A-3*2"
RIFF_B = "B-2*2 B-2*2 D-3*2 B-2*2 F#3*2 B-2*2 A-3*2 F#3*2"
LEAD = "@0 " + " | ".join([
    RIFF_E, RIFF_E, RIFF_C, RIFF_D, RIFF_E, RIFF_E, RIFF_C, RIFF_B,
    # melody over the riff (bars 9-16)
    "E-4*4 G-4*4 B-4*4 A-4*4", "G-4*4 E-4*8 r*4", "C-4*4 E-4*4 G-4*4 A-4*4", "F#4*4 D-4*8 r*4",
    "E-4*4 G-4*4 B-4*4 D-5*4", "C-5*4 B-4*4 G-4*8", "A-4*4 G-4*4 F#4*4 E-4*4", "D-4*8 B-3*8",
    RIFF_E, RIFF_E, RIFF_C, RIFF_D, RIFF_E, RIFF_E, RIFF_C, RIFF_B,
    # climax (bars 25-32)
    "@5 E-4*4 r*4 E-4*4 r*4", "G-4*4 r*4 A-4*4 r*4", "C-4*4 r*4 C-4*4 r*4", "D-4*4 r*4 D-4*4 r*4",
    "@0 E-5*2 D-5*2 B-4*2 G-4*2 E-4*2 G-4*2 B-4*2 D-5*2", "E-5*4 D-5*4 B-4*8", "C-5*2 B-4*2 G-4*2 E-4*2 C-4*2 E-4*2 G-4*2 B-4*2", "B-4*4 A-4*4 F#4*4 D-4*4",
])

# --- channel B: bass gallop -----------------------------------------------------------------------------
def gallop(n1, n2):
    return "%s*2 %s*1 %s*1 %s*2 %s*2 %s*2 %s*1 %s*1 %s*2 %s*2" % (n1, n1, n1, n2, n1, n1, n1, n1, n2, n1)
G_E = gallop("E-1", "E-2"); G_C = gallop("C-1", "C-2"); G_D = gallop("D-1", "D-2"); G_B = gallop("B-1", "B-2")
G_A = gallop("A-1", "A-2"); G_G = gallop("G-1", "G-2")
BASS = "@1 " + " | ".join([
    G_E, G_E, G_C, G_D, G_E, G_E, G_C, G_B,
    G_E, G_E, G_C, G_D, G_E, G_C, G_A, G_B,
    G_E, G_E, G_C, G_D, G_E, G_E, G_C, G_B,
    G_E, G_G, G_C, G_D, G_E, G_E, G_C, G_B,
])

# --- channel C: drums -----------------------------------------------------------------------------------
K = "@2 sl40 C-2*2"      # kick: low C with a fast downward pitch slide
S = "@3 sl0 C-5*2"       # snare (tone off anyway)
H = "@4 sl0 C-5*2"       # closed hat
DRUM_A = " ".join([K, H, S, H, K, K, S, H])              # 8 x 2 rows = 16 rows
DRUM_B = " ".join([K, H, S, H, K, H, S, S])
DRUM_F = " ".join([K, S, K, S, S, S, S, S])              # fill
DRUMS = " | ".join([
    DRUM_A, DRUM_A, DRUM_A, DRUM_B, DRUM_A, DRUM_A, DRUM_A, DRUM_F,
    DRUM_A, DRUM_A, DRUM_A, DRUM_B, DRUM_A, DRUM_A, DRUM_A, DRUM_F,
    DRUM_A, DRUM_A, DRUM_A, DRUM_B, DRUM_A, DRUM_A, DRUM_A, DRUM_F,
    DRUM_A, DRUM_B, DRUM_A, DRUM_B, DRUM_A, DRUM_A, DRUM_B, DRUM_F,
])

SONG = {"name": "game", "speed": SPEED, "rows": ROWS, "instruments": INSTRUMENTS,
        "channels": [LEAD, BASS, DRUMS], "bars": 32, "loop_bar": 0}
