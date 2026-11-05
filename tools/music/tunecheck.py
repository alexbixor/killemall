#!/usr/bin/env python3
"""tunecheck.py - T3: objective check of the 48K menu-tune render in build/sfx_48k.wav (no ears available).
The last 200 frames of the WAV are the mt_outer=2 section (12.4 ms of tone per 20 ms frame; tune steps 16..33).
Per complete 1/8-note step: is the expected lead note the strongest component in the 300..1500 Hz band, and is the
expected bass note a strong component (>= 50% of the strongest bin) in the 60..300 Hz band? The 50 Hz burst gating
(on/off every frame) puts strong 50 Hz harmonics into the low band - that buzz is inherent to the tick approach."""
import json, pathlib, re, wave
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
model = json.loads((ROOT / "build/beeper_model.json").read_text())
with wave.open(str(ROOT / "build/sfx_48k.wav")) as w:
    rate = w.getframerate(); d = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
FRAME_S = 69888 / 3.5e6
sec = d[-int(200 * FRAME_S * rate):]
NOTE_NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
def f_of(n, shift):
    m = re.fullmatch(r"([A-G]#?)(\d)", n); return 440.0 * 2 ** ((NOTE_NAMES[m.group(1)] + 12 * (int(m.group(2)) + shift) - 57) / 12)
def engine_f(f):
    n = max(2, min(255, round((3.5e6 / (2 * f) - model["mt_toggle_t"]) / model["mt_iter_t"])))
    return 3.5e6 / (2 * (n * model["mt_iter_t"] + model["mt_toggle_t"]))
mel = model["tune"]["melody"]; bass = model["tune"]["bass"]; speed = model["mt_speed"]
ok_l = tot_l = ok_b = tot_b = 0; rows = []
for step in range(17, 33):
    f0 = step * speed - 200; f1 = f0 + speed
    seg = sec[int(f0 * FRAME_S * rate):int(f1 * FRAME_S * rate)]
    seg = seg - seg.mean()
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); fr = np.fft.rfftfreq(len(seg), 1 / rate)
    hi = (fr >= 300) & (fr <= 1500); lo = (fr >= 60) & (fr <= 300)
    n1 = mel[step % len(mel)]; n2 = bass[(step // 2) % len(bass)]
    res = []
    if n1 != "-":
        f = engine_f(f_of(n1, model["tune"]["mel_shift"])); tot_l += 1
        fpk = fr[hi][np.argmax(spec[hi])]
        good = abs(fpk - f) / f < 0.03; ok_l += good
        res.append("lead %s=%.0fHz: band max %.0fHz %s" % (n1, f, fpk, "ok" if good else "NO"))
    if n2 != "-":
        f = engine_f(f_of(n2, model["tune"]["bass_shift"])); tot_b += 1
        band = (fr > f * 0.97) & (fr < f * 1.03)
        rel = spec[band].max() / spec[lo].max()
        good = rel >= 0.5; ok_b += good
        res.append("bass %s=%.0fHz: %.2f of low-band max %s" % (n2, f, rel, "ok" if good else "weak"))
    rows.append("step %2d: %s" % (step, "   ".join(res)))
print("\n".join(rows))
print("lead note = strongest 300-1500 Hz component: %d / %d steps; bass note strong in 60-300 Hz: %d / %d" % (ok_l, tot_l, ok_b, tot_b))
