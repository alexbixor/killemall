#!/usr/bin/env python3
"""gen_beeper.py - T3 sound lane: generates the data block of src/common/beeper.asm.

Writes (between the GENERATED markers of beeper.asm):
  * sfx_tab + 10 SFX segment lists for the 48K beeper engine
  * the original 16-bar, 2-voice menu tune for snd_menu_tick (voice 1 per 1/8, voice 2 per 1/4)
Also writes build/beeper_model.json (expected SFX durations etc.) consumed by tools/test_sound.py.

SFX segment: db count, dw period, db slide, db noise_mask  (list terminated by db 0)
  half-cycle T-states = 143 (+2 on LFSR feedback) + 26 * (period + (lfsr & noise_mask)); period += slide per half-cycle.
Menu tune engine (snd_menu_tick): 2 voices time-multiplexed, loop pass = MT_ITER_T T-states (+14 T when a voice toggles),
a voice toggles every N passes -> half period ~ N*79 + 14 T.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ASM = ROOT / "src/common/beeper.asm"
CPU = 3_500_000
SFX_OVH = 143          # T-states per half-cycle outside the 26 T delay loop (model; measured by test_sound.py)
MT_ITER_T = 79         # T-states per burst-loop pass (both voices) without a toggle
MT_TOGGLE_T = 14       # extra T-states for the pass in which a voice toggles
MT_SPEED = 12          # frames per 1/8 note (125 bpm)
MAX_SFX_T = 140_000    # 40 ms

NOTE_NAMES = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7,
              "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}

def note_freq(name, shift=0):
    """'E6' -> Hz (A4 = 440); shift = octaves."""
    m = re.fullmatch(r"([A-G][#B]?)(\d)", name.upper())
    if not m:
        raise ValueError(name)
    semis = NOTE_NAMES[m.group(1)] + 12 * (int(m.group(2)) + shift) - (9 + 12 * 4)
    return 440.0 * 2 ** (semis / 12)

def tone_period(freq):
    """SFX period value for a pure tone at freq (half-cycle = SFX_OVH + 26*P)."""
    return max(1, round((CPU / (2 * freq) - SFX_OVH) / 26))

def tone_count(freq, ms):
    return max(1, round(ms * 1e-3 * freq * 2))

# ------------------------------------------------------------------ SFX definitions
# (count, period, slide, noise_mask)
def sfx_defs():
    s = {}
    s[1] = [(44, 4, 0, 0x3F), (24, 20, 3, 0x0F)]                                      # shot: white-ish noise burst + low thud
    s[2] = [(72, 96, -1, 0)]                                                            # door: rising slide ~660 -> 3,000 Hz
    s[3] = [(tone_count(f, 7), tone_period(f), 0, 0) for f in (note_freq("C6"), note_freq("E6"), note_freq("G6"), note_freq("C7"))]  # pickup arpeggio
    s[4] = [(7, 240, 0, 0x1F), (6, 300, 0, 0x1F)]                                      # player hurt: low gritty buzz
    s[5] = [(44, 28, 2, 0x07)]                                                          # enemy die: falling ~2,000 -> 560 Hz
    s[6] = [(6, 15, 0, 0)]                                                              # menu tick: click
    s[7] = [(6, 120, 0, 0), (1, 1200, 0, 0), (6, 120, 0, 0)]                            # locked / no ammo: dull double click
    s[8] = [(22, 50, 3, 0x3F)]                                                          # enemy attack: growl
    s[9] = [(tone_count(note_freq("G5"), 9), tone_period(note_freq("G5")), 0, 0),
            (tone_count(note_freq("C6"), 9), tone_period(note_freq("C6")), 0, 0),
            (tone_count(note_freq("E6"), 14), tone_period(note_freq("E6")), 0, 0)]      # level clear: 3-note fanfare
    s[10] = [(36, 36, 3, 0x07)]                                                         # player death: long fall
    return s

def sfx_model(segs):
    """Return (min_T, max_T, n_toggles) over all LFSR outcomes; checks periods stay in range."""
    tmin = tmax = 0; n = 0
    for count, period, slide, mask in segs:
        p = period
        for _ in range(count):
            if p < 1 or p > 4000:
                raise SystemExit("period out of range in segment %r" % (segs,))
            tmin += SFX_OVH + 26 * p
            tmax += SFX_OVH + 2 + 26 * (p + mask)
            n += 1
            p += slide
    return tmin, tmax, n

# ------------------------------------------------------------------ menu tune (original, 16 bars, E minor, 125 bpm)
# Voice 1 (lead): one symbol per 1/8 note; '-' = rest.  Written an octave high, shifted down by MEL_SHIFT.
MELODY = (
    # bar 1-4: motif
    "E6 - E6 G6 B6 - G6 E6 | D6 - D6 F#6 A6 - F#6 D6 | C6 - C6 E6 G6 - E6 C6 | B5 - D6 F#6 B6 - A6 G6 | "
    # bar 5-8: answer, climbing
    "E6 - E6 G6 B6 - E7 D7 | B6 - G6 - A6 - F#6 - | G6 - E6 G6 C7 - B6 A6 | B6 - - - F#6 - - - | "
    # bar 9-12: variation
    "E7 - D7 E7 B6 - G6 E6 | F#6 - A6 F#6 D6 - F#6 A6 | C7 - B6 C7 G6 - E6 C6 | B5 - D6 F#6 B6 A6 G6 F#6 | "
    # bar 13-16: cadence
    "E6 - G6 B6 E7 - B6 G6 | A6 - F#6 D6 A6 - F#6 D6 | G6 - E6 C6 G6 - B6 D7 | E7 - - - E6 - - - "
)
MEL_SHIFT = -1         # lead B4..E6
# Voice 2 (bass): one symbol per 1/4 note (64 entries), shifted by BASS_SHIFT.
BASS = (
    "E5 E5 B4 B4 | D5 D5 A4 A4 | C5 C5 G4 G4 | B4 B4 B4 B4 | "
    "E5 E5 B4 B4 | G5 G5 D5 D5 | C5 C5 G4 G4 | B4 B4 F#5 F#5 | "
    "E5 E5 B4 B4 | D5 D5 A4 A4 | C5 C5 G4 G4 | B4 B4 B4 B4 | "
    "E5 E5 B4 B4 | D5 D5 A4 A4 | C5 C5 G4 G4 | E5 E5 E5 E5 "
)
BASS_SHIFT = -2        # bass G2..G4

def parse_track(s, expect):
    toks = [t for t in s.replace("|", " ").split() if t]
    if len(toks) != expect:
        raise SystemExit("track has %d steps, expected %d" % (len(toks), expect))
    return toks

def mt_counter(freq):
    return max(2, min(255, round((CPU / (2 * freq) - MT_TOGGLE_T) / MT_ITER_T)))

def main():
    out = []
    model = {"sfx": {}, "sfx_ovh": SFX_OVH, "mt_iter_t": MT_ITER_T, "mt_toggle_t": MT_TOGGLE_T, "mt_speed": MT_SPEED}
    defs = sfx_defs()
    out.append("sfx_tab:")
    for i in range(1, 11):
        out.append("        dw sfx_%d" % i)
    for i in range(1, 11):
        segs = defs[i]
        tmin, tmax, n = sfx_model(segs)
        if tmax > MAX_SFX_T:
            raise SystemExit("sfx %d worst case %d T > %d" % (i, tmax, MAX_SFX_T))
        model["sfx"][i] = {"t_min": tmin, "t_max": tmax, "toggles": n, "segs": segs}
        out.append("sfx_%d:   ; %d half-cycles, %d..%d T (%.1f..%.1f ms)" % (i, n, tmin, tmax, tmin / 3500, tmax / 3500))
        for count, period, slide, mask in segs:
            out.append("        db %d" % count)
            out.append("        dw %d" % period)
            out.append("        db %d,%d" % (slide & 0xFF, mask))
        out.append("        db 0")
    # tune
    mel = parse_track(MELODY, 128)
    bass = parse_track(BASS, 64)
    freqs = {}
    for t in mel:
        if t != "-":
            freqs["m" + t] = note_freq(t, MEL_SHIFT)
    for t in bass:
        if t != "-":
            freqs["b" + t] = note_freq(t, BASS_SHIFT)
    keys = sorted(freqs, key=lambda k: freqs[k])
    counters = {k: mt_counter(freqs[k]) for k in keys}
    model["tune"] = {"melody": mel, "bass": bass, "mel_shift": MEL_SHIFT, "bass_shift": BASS_SHIFT,
                     "names": keys, "freqs": [freqs[k] for k in keys], "counters": [counters[k] for k in keys], "len": len(mel)}
    out.append("MT_LEN  equ %d" % len(mel))
    out.append("; counters (79 T loop passes per half-cycle): " + " ".join("%s=%d" % (k[1:], counters[k]) for k in keys))
    out.append("mt_mel:   ; voice 1, one byte per 1/8 note (0 = rest)")
    for b in range(16):
        out.append("        db " + ",".join(str(counters["m" + t]) if t != "-" else "0" for t in mel[b * 8:(b + 1) * 8]))
    out.append("mt_v2:    ; voice 2, one byte per 1/4 note")
    for b in range(8):
        out.append("        db " + ",".join(str(counters["b" + t]) if t != "-" else "0" for t in bass[b * 8:(b + 1) * 8]))
    block = "\n".join(out) + "\n"
    src = ASM.read_text()
    m0 = "; ---- GENERATED BY tools/music/gen_beeper.py (do not edit by hand) ----\n"
    m1 = "; ---- END GENERATED ----\n"
    a = src.index(m0) + len(m0); b = src.index(m1)
    ASM.write_text(src[:a] + block + src[b:])
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/beeper_model.json").write_text(json.dumps(model, indent=1))
    sfx_bytes = 20 + sum(1 + len(d) * 5 for d in defs.values())
    tune_bytes = len(mel) + len(bass)
    print("beeper data: SFX %d B, tune %d B (%d notes: %s)" % (sfx_bytes, tune_bytes, len(keys), " ".join(k[1:] for k in keys)))
    for i in range(1, 11):
        print("sfx %2d: %6d..%6d T  %.1f..%.1f ms" % (i, model["sfx"][i]["t_min"], model["sfx"][i]["t_max"], model["sfx"][i]["t_min"] / 3500, model["sfx"][i]["t_max"] / 3500))

if __name__ == "__main__":
    main()
