#!/usr/bin/env python3
"""ayrender.py - T3: minimal AY-3-8912 emulator rendering a recorded register stream to WAV (and a beeper toggle log).

AY model (ayumi-style): clock 1,773,400 Hz; the tone counters step at clock/8 and the output toggles every P steps,
so f = clock / (16 P) (P = 0 acts as 1); noise: 17-bit LFSR (taps 17, 14) shifted every 2*NP steps at clock/8
(f_noise = clock / (16 NP)); mixer R7 active-low (tone bit n, noise bit 3+n); volumes R8..R10 (0..15, logarithmic
AY table; bit 4 = hardware envelope, rendered as a constant volume 15 - the player never uses it).
Mono output, 44.1 kHz 16-bit, channels summed (ABC mono mix like a real 128K).

API:
  render_ay(events, frames, fps=50, rate=44100) -> int16 samples ; events = [(frame, reg, value), ...] in time order
  render_beeper(toggles, total_t, rate=44100, cpu=3_500_000) -> int16 samples ; toggles = [(t_states, level 0/1), ...]
  write_wav(path, samples, rate)
numpy is used when available (it is in .venv), pure Python fallback otherwise.
"""
import struct, wave

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

AY_CLOCK = 1_773_400
# AY-3-8910 volume table (relative amplitudes, ayumi/MAME style)
VOL_TABLE = [0.0, 0.0137, 0.0205, 0.0291, 0.0423, 0.0618, 0.0847, 0.1369, 0.1691, 0.2647, 0.3527, 0.4499, 0.5704, 0.6873, 0.8482, 1.0]

def write_wav(path, samples, rate=44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        if np is not None:
            w.writeframes(np.asarray(samples, dtype="<i2").tobytes())
        else:
            w.writeframes(struct.pack("<%dh" % len(samples), *samples))

def _to_pcm(out, gain):
    if np is not None:
        out = np.asarray(out, dtype=np.float64)
        out = out - out.mean()
        peak = float(np.max(np.abs(out))) or 1.0
        return np.clip(out / peak * 32767 * gain, -32767, 32767).astype("<i2")
    mean = sum(out) / len(out); out = [v - mean for v in out]
    peak = max(1e-9, max(abs(v) for v in out))
    return [int(max(-32767, min(32767, v / peak * 32767 * gain))) for v in out]

def render_ay(events, frames, fps=50.0, rate=44100, gain=0.85):
    """events: iterable of (frame_index, reg, value) in time order; frames: total frames to render."""
    regs = [0] * 16; regs[7] = 0x3F
    n_total = int(round(frames * rate / fps))
    out = [0.0] * n_total
    step_hz = AY_CLOCK / 8.0                     # tone/noise counter rate (221,675 Hz)
    phase = [0.0, 0.0, 0.0]
    tone_out = [0, 0, 0]
    noise_cnt = 0.0; lfsr = 1; noise_out = 0
    ev_i = 0; events = list(events)
    samples_per_frame = rate / fps
    steps_per_sample = step_hz / rate            # ~5.026 counter steps per output sample
    for frame in range(frames):
        while ev_i < len(events) and events[ev_i][0] <= frame:
            _, r, v = events[ev_i]; ev_i += 1
            regs[r & 15] = v & 255
        periods = [max(1, ((regs[2 * c + 1] & 15) << 8) | regs[2 * c]) for c in range(3)]
        nper = 2 * max(1, regs[6] & 31)
        mix = regs[7]
        vols = [VOL_TABLE[15 if regs[8 + c] & 16 else regs[8 + c] & 15] for c in range(3)]
        t_en = [not (mix >> c) & 1 for c in range(3)]
        n_en = [not (mix >> (3 + c)) & 1 for c in range(3)]
        s0 = int(round(frame * samples_per_frame)); s1 = min(int(round((frame + 1) * samples_per_frame)), n_total)
        for s in range(s0, s1):
            for c in range(3):
                phase[c] += steps_per_sample
                p = periods[c]
                if phase[c] >= p:
                    k = int(phase[c] // p)
                    phase[c] -= k * p
                    if k & 1:
                        tone_out[c] ^= 1
            noise_cnt += steps_per_sample
            if noise_cnt >= nper:
                k = int(noise_cnt // nper); noise_cnt -= k * nper
                for _ in range(min(k, 3)):
                    bit = (lfsr ^ (lfsr >> 3)) & 1          # taps 17 and 14
                    lfsr = (lfsr >> 1) | (bit << 16)
                noise_out = lfsr & 1
            acc = 0.0
            for c in range(3):
                t = tone_out[c] if t_en[c] else 1
                n = noise_out if n_en[c] else 1
                if t and n:
                    acc += vols[c]
            out[s] = acc
    return _to_pcm(out, gain)

def render_beeper(toggles, total_t, rate=44100, cpu=3_500_000, gain=0.7):
    """toggles: [(t_states, level)], level 0/1 = speaker bit. The speaker level is integrated (time-averaged) over each
    output sample period - exactly what the speaker cone/ear does - so ultrasonic multiplex carriers (snd_menu_tick
    alternates two voices at ~44 kHz) average out to the sum of the voices instead of aliasing. Then AC coupling."""
    n = int(total_t / cpu * rate) + 1
    out = [0.0] * n
    tog = sorted(toggles)
    level = 0.0; idx = 0
    tps = cpu / rate                                   # T-states per output sample
    for s in range(n):
        t0 = s * tps; t1 = t0 + tps
        acc = 0.0; t = t0
        while idx < len(tog) and tog[idx][0] < t1:
            tt = max(tog[idx][0], t0)
            acc += level * (tt - t); t = tt
            level = float(tog[idx][1]); idx += 1
        acc += level * (t1 - t)
        out[s] = acc / tps
    # AC coupling (1-pole high-pass ~30 Hz)
    hp = 0.0; prev = 0.0; r = 1.0 - 2 * 3.14159 * 30.0 / rate
    for i in range(n):
        x = out[i]
        hp = r * hp + (x - prev); prev = x
        out[i] = hp
    return _to_pcm(out, gain)

if __name__ == "__main__":
    # smoke: 2 s of A4 (period 252) on channel A -> /tmp/ay_smoke.wav
    ev = [(0, 0, 252), (0, 1, 0), (0, 7, 0x3E), (0, 8, 15)]
    write_wav("/tmp/ay_smoke.wav", render_ay(ev, 100))
    print("wrote /tmp/ay_smoke.wav")
