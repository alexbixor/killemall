#!/usr/bin/env python3
"""diag_mt2.py - T3: render 2 s of the menu tune straight from a fresh capture (timestamps = absolute machine T-states,
frames padded to 69,888 T) and run the same spectral check -> isolates WAV-assembly bugs in test_sound.py from engine bugs."""
import json, pathlib, sys, wave
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from z80harness import Machine, ROOT, CALL_JP_T
import ayrender
mc = Machine(ROOT / "build/snd_test48.tap", ROOT / "build/snd_test48.sym")
S = mc.sym
model = json.loads((ROOT / "build/beeper_model.json").read_text())
mc.poke(S["opt_sfx"], [1]); mc.poke(S["opt_music"], [1])
mc.call("snd_music", a=1)
mc.poke(S["mt_outer"], [2])
FRAME = 69888
tog = []
frames = 100
for f in range(frames):
    n0 = len(mc.outs); t_start = mc.t
    mc.call("snd_menu_tick")
    for tt, port, v in mc.outs[n0:]:
        if (port & 0xFF) == 0xFE:
            tog.append((f * FRAME + (tt - t_start), (v >> 4) & 1))
pcm = ayrender.render_beeper(tog, frames * FRAME)
ayrender.write_wav("/tmp/mt_direct.wav", pcm)
d = np.asarray(pcm, dtype=float) / 32768
rate = 44100; FRAME_S = FRAME / 3.5e6
print("toggle count", len(tog), "first 10 toggles (t, level):", tog[:10])
# per-frame check on frame 1 (step 0: E6-1 = E5 lead 659 Hz nominal, bass E5-2 = E3 165 Hz)
seg = d[int(1 * FRAME_S * rate):int(12 * FRAME_S * rate)]; seg = seg - seg.mean()
spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); fr = np.fft.rfftfreq(len(seg), 1 / rate)
order = np.argsort(spec)[::-1][:8]
print("step 0 top peaks Hz:", [(round(float(fr[i])), round(float(spec[i] / spec[order[0]]), 2)) for i in order])
# expected: lead counter 33 -> half period 33*79+14 = 2621 T -> 3.5e6/5242 = 667.7 Hz ; bass 134 -> 134*79+14 = 10600 -> 165 Hz
print("expected lead %.0f Hz, bass %.0f Hz" % (3.5e6 / (2 * (33 * 79 + 14)), 3.5e6 / (2 * (134 * 79 + 14))))
# raw duty check on frame 1: fraction of time at level 1 within the burst by slot
f1 = [t for t in tog if FRAME <= t[0] < 2 * FRAME]
print("frame 1: %d writes spanning %d T (%.1f ms)" % (len(f1), f1[-1][0] - f1[0][0], (f1[-1][0] - f1[0][0]) / 3500))
