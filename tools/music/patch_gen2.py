#!/usr/bin/env python3
"""patch_gen2.py - T3: switch gen_beeper.py from note-index tables to direct counter tables (one-off patch)."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
P = ROOT / "tools/music/gen_beeper.py"
s = P.read_text()
old = s[s.index("    keys = sorted(freqs, key=lambda k: freqs[k])"):s.index("    block = \"\\n\".join(out) + \"\\n\"")]
new = '''    keys = sorted(freqs, key=lambda k: freqs[k])
    counters = {k: mt_counter(freqs[k]) for k in keys}
    model["tune"] = {"melody": mel, "bass": bass, "mel_shift": MEL_SHIFT, "bass_shift": BASS_SHIFT,
                     "names": keys, "freqs": [freqs[k] for k in keys], "counters": [counters[k] for k in keys], "len": len(mel)}
    out.append("MT_LEN  equ %d" % len(mel))
    out.append("; counters (45 T loop iterations per half-cycle): " + " ".join("%s=%d" % (k[1:], counters[k]) for k in keys))
    out.append("mt_mel:   ; voice 1, one byte per 1/8 note (0 = rest)")
    for b in range(16):
        out.append("        db " + ",".join(str(counters["m" + t]) if t != "-" else "0" for t in mel[b * 8:(b + 1) * 8]))
    out.append("mt_v2:    ; voice 2, one byte per 1/4 note")
    for b in range(8):
        out.append("        db " + ",".join(str(counters["b" + t]) if t != "-" else "0" for t in bass[b * 8:(b + 1) * 8]))
'''
s = s.replace(old, new)
s = s.replace('''    tune_bytes = len(counters) + len(mel) + len(bass)''', '''    tune_bytes = len(mel) + len(bass)''')
P.write_text(s)
B = ROOT / "src/common/beeper.asm"
b = B.read_text()
b = b.replace("MT_ITER  equ 50", "MT_ITER  equ 48")
b = b.replace("Default 50/0 = ~0.65 ms", "Default 48/0 = ~0.62 ms")
B.write_text(b)
print("ok")
