#!/usr/bin/env python3
"""wavcheck.py - T3: objective sanity checks of the rendered previews (no ears available): RMS, peak, dominant pitch per
window of the AY tracks vs the expected channel-A notes; beeper WAV activity."""
import json, pathlib, sys, wave
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

def load(path):
    with wave.open(str(path)) as w:
        n = w.getnframes(); rate = w.getframerate()
        data = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768
    return data, rate

def dom_freq(seg, rate):
    seg = seg - seg.mean()
    if np.max(np.abs(seg)) < 1e-4: return 0.0
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / rate)
    spec[freqs < 40] = 0
    return float(freqs[np.argmax(spec)])

def note_name(f):
    if f <= 0: return "-"
    n = int(round(12 * np.log2(f / 440.0))) + 57
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][n % 12] + str(n // 12)

for name in ("music_menu", "music_game", "sfx_48k", "sfx_ay"):
    p = ROOT / "build" / (name + ".wav")
    d, rate = load(p)
    rms = float(np.sqrt(np.mean(d ** 2))); peak = float(np.max(np.abs(d)))
    active = float(np.mean(np.abs(d) > 0.01))
    print("%-11s %6.1f s  rms %.3f  peak %.3f  active %.0f%%  clipped %d" % (name, len(d) / rate, rms, peak, 100 * active, int(np.sum(np.abs(d) > 0.999))))
    if name.startswith("music"):
        # dominant pitch in 0.5 s windows for the first 8 s
        row = []
        for i in range(0, 16):
            seg = d[int(i * 0.5 * rate):int((i + 0.5) * 0.5 * rate)]
            row.append(note_name(dom_freq(seg, rate)))
        print("   dominant pitch per 0.5 s (first 8 s):", " ".join(row))
    if name == "sfx_48k":
        # event boundaries: find bursts of activity
        env = np.convolve(np.abs(d), np.ones(441) / 441, mode="same")
        on = env > 0.02
        edges = np.flatnonzero(np.diff(on.astype(int)) == 1)
        print("   %d sound onsets at s: %s" % (len(edges), " ".join("%.2f" % (e / rate) for e in edges[:24])))
