#!/usr/bin/env python3
"""test_sound.py - T3 sound lane unit tests on the Python Z80 core (z80 1.2.0, set_output_callback = port logger).

Beeper (build/snd_test48.tap, src/common/beeper.asm):
  * every SFX id 1..10: speaker bit toggles, only bit 4 of port 254 ever set (border 0), duration <= 140,000 T,
    interrupts disabled during the SFX and enabled on return, opt_sfx = 0 -> no OUT at all and ~30 T
  * snd_menu_tick: <= 3,000 T per call over a full 16-bar loop (1,536 frames), tune loops, stops when opt_music = 0
  * beeper toggle log of all 10 SFX + 4 s of menu tune -> build/sfx_48k.wav (+ mp3)
AY (build/snd_test128.tap, src/128k/ay.asm + src/gen/music_data.asm):
  * snd_isr cost per frame (max over the whole loop of both tracks) <= 4,000 T; every frame writes R0..R10
  * register stream matches a Python reference model of the KAM1 format row by row (tone period / volume per channel)
  * the song loops (pattern order restarts at the loop index) and the register stream is periodic
  * SFX pre-empts channel C and the music resumes afterwards; snd_fx with opt_sfx = 0 does nothing
  * register streams rendered with tools/music/ayrender.py -> build/music_menu.wav, build/music_game.wav (+ mp3)
Exit code 0 = all assertions passed. Run tools/snd_build.sh first (or pass --build).
"""
import json, os, pathlib, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "music"))
from z80harness import Machine, ROOT, CALL_JP_T
import ayrender

BUILD = ROOT / "build"
FAILS = []

def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)

def mp3(wav):
    out = wav.with_suffix(".mp3")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  ffmpeg failed:", r.stderr.strip()[:200]); return None
    return out

# ====================================================================================== beeper
def test_beeper():
    print("== 48K beeper (build/snd_test48.tap)")
    mc = Machine(BUILD / "snd_test48.tap", BUILD / "snd_test48.sym")
    model = json.loads((BUILD / "beeper_model.json").read_text())
    S = mc.sym
    code_bytes = S["fin"] - S["snd_isr"]
    print("  beeper.asm footprint: %d bytes (snd_isr..fin, code+data)" % code_bytes)
    check(code_bytes <= 820, "beeper footprint %d B <= 0.8 KB" % code_bytes)
    mc.poke(S["opt_sfx"], [1]); mc.poke(S["opt_music"], [1])
    wav_toggles = []; wav_t = 0
    worst = 0
    for i in range(1, 11):
        n0 = len(mc.outs)
        t = mc.call("snd_fx", a=i) - CALL_JP_T
        p254 = [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]
        others = [o for o in mc.outs[n0:] if (o[1] & 0xFF) != 0xFE]
        toggles = sum(1 for a, b in zip(p254, p254[1:]) if (a[2] ^ b[2]) & 16)
        exp = model["sfx"][str(i)]
        ok = (t <= 140_000 and toggles >= 4 and all(o[2] & ~0x10 == 0 for o in p254) and not others and mc.iff1()
              and p254[-1][2] == 0 and exp["t_min"] - 600 <= t <= exp["t_max"] + 900)
        check(ok, "sfx %2d: %6d T = %4.1f ms (model %d..%d), %2d toggles, border bits 0, ends silent, EI on return" % (
            i, t, t / 3500, exp["t_min"], exp["t_max"], toggles))
        worst = max(worst, t)
        base = wav_t
        for tt, _, v in p254:
            wav_toggles.append((base + (tt - p254[0][0]), (v >> 4) & 1))
        wav_t += t + 3_500_000 // 4            # 250 ms gap between effects in the preview
    print("  worst SFX: %d T = %.1f ms" % (worst, worst / 3500))
    # DI inside: run SFX 2 with a breakpoint in the middle (sfx_half) and look at iff1
    mc.m.set_breakpoint(S["sfx_half"])
    stub = bytes([0x3E, 2, 0xCD, S["snd_fx"] & 255, S["snd_fx"] >> 8, 0xC3, 0x00, 0x7F])
    mc.poke(0x7E00, stub); mc.m.pc = 0x7E00; mc.m.sp = 0xFE00
    mc._budget = 100_000; mc._t_base = mc.t; mc.m.ticks_to_stop = 100_000; mc.m.run()
    check(mc.m.pc == S["sfx_half"] and not mc.m.iff1, "interrupts disabled inside snd_fx (iff1=%s at sfx_half)" % mc.m.iff1)
    mc.m.clear_breakpoint(S["sfx_half"])
    # opt_sfx = 0
    mc.poke(S["opt_sfx"], [0]); n0 = len(mc.outs)
    t = mc.call("snd_fx", a=1) - CALL_JP_T
    check(len(mc.outs) == n0 and t < 60, "opt_sfx=0: snd_fx silent, %d T" % t)
    t = mc.call("snd_fx", a=0) - CALL_JP_T; t2 = mc.call("snd_fx", a=11) - CALL_JP_T
    mc.poke(S["opt_sfx"], [1]); n0 = len(mc.outs)
    t = mc.call("snd_fx", a=0) - CALL_JP_T; t2 = mc.call("snd_fx", a=11) - CALL_JP_T
    check(len(mc.outs) == n0, "ids 0 and 11 ignored (%d / %d T)" % (t, t2))
    # ---- menu tune
    tune = model["tune"]; mt_len = tune["len"]; speed = model["mt_speed"]
    t = mc.call("snd_music", a=1) - CALL_JP_T
    check(mc.peek(S["snd_playing"])[0] == 1 and t < 200, "snd_music 1: snd_playing=1 (%d T)" % t)
    frames = mt_len * speed + 5
    costs = []; n0 = len(mc.outs); positions = []
    for f in range(frames):
        costs.append(mc.call("snd_menu_tick") - CALL_JP_T)
        positions.append(mc.peek(S["mt_pos"])[0])
    tick_outs = [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]
    check(max(costs) <= 3000, "snd_menu_tick max %d T, avg %.0f T over %d frames (<= 3,000)" % (max(costs), sum(costs) / len(costs), frames))
    check(all(o[2] & ~0x10 == 0 for o in tick_outs) and len(tick_outs) > frames, "menu tune: %d speaker writes, border bits 0" % len(tick_outs))
    check(positions[0] == 0 and positions[speed] == 1 and positions[mt_len * speed] == 0,
          "tune steps every %d frames and loops after %d steps (pos@0=%d, @%d=%d, @%d=%d)" % (speed, mt_len, positions[0], speed, positions[speed], mt_len * speed, positions[mt_len * speed]))
    # expected melody frequency check on a sounding step: step 0 = voice1 counter 58 -> half period 58*45+25 T
    gaps = [b[0] - a[0] for a, b in zip(tick_outs, tick_outs[1:]) if 0 < b[0] - a[0] < 2000]
    check(len(gaps) > 50, "voice toggles inside bursts: %d short gaps, e.g. %s" % (len(gaps), gaps[:6]))
    # stop: opt_music = 0 while playing -> silence + playing flag cleared
    mc.poke(S["opt_music"], [0]); n0 = len(mc.outs)
    t = mc.call("snd_menu_tick") - CALL_JP_T
    check(mc.peek(S["snd_playing"])[0] == 0 and mc.outs[n0:][-1][2] == 0, "opt_music=0 while playing: stops, speaker 0 (%d T)" % t)
    t = mc.call("snd_menu_tick") - CALL_JP_T
    check(t < 40, "snd_menu_tick when not playing: %d T" % t)
    mc.poke(S["opt_music"], [1])
    t = mc.call("snd_music", a=0) - CALL_JP_T
    check(mc.peek(S["snd_playing"])[0] == 0, "snd_music 0: stops (%d T)" % t)
    t = mc.call("snd_isr") - CALL_JP_T
    check(t == 10, "snd_isr = ret (%d T)" % t)
    # ---- preview WAV: SFX 1..10 then 4 s of tune with the default (contract) burst and 4 s with mt_outer=3
    t0 = mc.call("snd_music", a=1)
    base = wav_t; n0 = len(mc.outs); tstart = mc.t
    for f in range(200):
        mc.call("snd_menu_tick"); mc.t = tstart + (f + 1) * 69_888   # exact 50 Hz frame grid for the preview
    for tt, _, v in [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]:
        wav_toggles.append((base + (tt - tstart), (v >> 4) & 1))
    wav_t = base + 200 * 69_888 + 3_500_000 // 2
    mc.poke(S["mt_outer"], [2])
    base = wav_t; n0 = len(mc.outs); tstart = mc.t
    for f in range(200):
        mc.call("snd_menu_tick"); mc.t = tstart + (f + 1) * 69_888
    for tt, _, v in [o for o in mc.outs[n0:] if (o[1] & 0xFF) == 0xFE]:
        wav_toggles.append((base + (tt - tstart), (v >> 4) & 1))
    wav_t = base + 200 * 69_888
    big = mc.call("snd_menu_tick") - CALL_JP_T
    print("  snd_menu_tick with mt_outer=2 (optional richer mode): %d T per frame" % big)
    samples = ayrender.render_beeper(wav_toggles, wav_t)
    wav = BUILD / "sfx_48k.wav"; ayrender.write_wav(wav, samples)
    m = mp3(wav)
    print("  wrote %s (%.1f s) %s" % (wav, len(samples) / 44100, m))
    return code_bytes, worst, max(costs), big

# ====================================================================================== AY reference model
def ay_reference(song, model_notes, frames):
    """Python model of ay.asm playing one song: per frame -> (periods[3], vols[3], mixer, noise).
    Timing: the request is picked up on ISR call 0 (mus_tick = 5, setup only); rows are committed on the frames where
    mus_tick reaches 0, i.e. call 4, 4+speed, 4+2*speed, ...; a channel whose block is ON gets its envelope advanced every frame.
    Mixer/noise registers only change on row frames (commit)."""
    speed = song["speed"]; rows_pp = song["rows"]; chans = song["chans"]; rows_total = song["rows_total"]
    insts = song["insts"]
    st = [dict(on=0, note=0, inst=0, env=None, epos=0, arp=0, arpp=0, slide=0, acc=0) for _ in range(3)]
    res = []
    row = -1; tick = 5; mixer = 0x3F; noise = 0
    for f in range(frames):
        tick -= 1
        if tick == 0:
            tick = speed; row += 1
            r_idx = row % rows_total
            for c in range(3):
                r = chans[c][r_idx]; s = st[c]
                if r["note"] is None: continue
                if "inst" in r: s["inst"] = r["inst"]
                if r["note"] == "off":
                    s["on"] = 0; continue
                s["on"] = 1; s["note"] = r["note"]
                s["arp"] = r.get("arp", 0) or 0; s["slide"] = r.get("slide", 0) or 0
                s["acc"] = 0; s["arpp"] = 0; s["epos"] = 0
                name, mix, loop, env = insts[s["inst"]]
                s["env"] = (mix, loop, env)
                tb = 1 << c; nb = tb << 3
                mixer |= tb | nb
                if not mix & 0x40: mixer &= ~tb
                if mix & 0x80: mixer &= ~nb
                if mix & 0x1F: noise = mix & 0x1F
        periods = [0, 0, 0]; vols = [0, 0, 0]
        for c in range(3):
            s = st[c]
            if not s["on"]:
                vols[c] = 0; periods[c] = 0; continue
            mix, loop, env = s["env"]
            off, vol = env[s["epos"]]
            s["epos"] = s["epos"] + 1 if s["epos"] + 1 < len(env) else loop
            n = s["note"] + off
            if s["arp"]:
                ph = s["arpp"]; s["arpp"] = (ph + 1) % 3
                if ph == 1: n += s["arp"] >> 4
                elif ph == 2: n += s["arp"] & 15
            p = model_notes[n]
            if s["slide"]:
                sl = s["slide"] - 256 if s["slide"] > 127 else s["slide"]
                s["acc"] += sl; p = p + s["acc"]
                if p < 0 or p > 0xFFF: p = 0xFFF
            periods[c] = p; vols[c] = vol
        res.append((periods, vols, mixer, noise))
    return res

def test_ay():
    print("== 128K AY (build/snd_test128.tap)")
    mc = Machine(BUILD / "snd_test128.tap", BUILD / "snd_test128.sym")
    S = mc.sym
    music = json.loads((BUILD / "music_model.json").read_text())
    player_bytes = S["ay_end"] - S["snd_menu_tick"]
    notes_bytes = S["music_menu"] - S["ay_notes"]
    menu_bytes = S["music_menu_end"] - S["music_menu"]; game_bytes = S["music_game_end"] - S["music_game"]
    print("  ay.asm player+SFX code/data: %d B; music_data.asm: notes %d B, menu %d B, game %d B (total data %d B)" % (
        player_bytes, notes_bytes, menu_bytes, game_bytes, notes_bytes + menu_bytes + game_bytes))
    check(player_bytes <= 1536, "player <= 1.5 KB (%d)" % player_bytes)
    check(notes_bytes + menu_bytes + game_bytes <= 6144, "music data <= 6 KB (%d)" % (notes_bytes + menu_bytes + game_bytes))
    # note table check
    tbl = [int.from_bytes(mc.peek(S["ay_notes"] + 2 * i, 2), "little") for i in range(128)]
    import importlib
    sys.path.insert(0, str(ROOT / "tools/music"))
    from compile_music import ay_period, compile_song
    check(tbl[46] == ay_period(46) == 252 and tbl[1] == 3389, "ay_notes: A4 period %d (440 Hz), C1 %d" % (tbl[46], tbl[1]))
    mc.poke(S["opt_sfx"], [1]); mc.poke(S["opt_music"], [1])
    results = {}
    for track_id, name in ((1, "menu"), (2, "game")):
        song = compile_song(importlib.import_module("track_" + name).SONG)
        info = music[name]
        loop_frames = info["frames_per_loop"]
        t = mc.call("snd_music", a=track_id) - CALL_JP_T
        check(t < 120 and mc.peek(S["mus_req"])[0] == 0x80 | track_id, "snd_music %d: request latched (%d T)" % (track_id, t))
        mc.poke(S["ay_regs"], [0] * 7 + [0x3F, 0, 0, 0])
        frames = loop_frames + 600
        costs = []; per_frame = []
        n0 = len(mc.outs)
        for f in range(frames):
            k = len(mc.outs)
            costs.append(mc.call("snd_isr") - CALL_JP_T)
            per_frame.append(mc.outs[k:])
        # parse register writes: pairs (FFFD reg, BFFD value)
        def regs_of(outs):
            regs = {}; sel = None
            for _, port, v in outs:
                if port == 0xFFFD: sel = v
                elif port == 0xBFFD and sel is not None: regs[sel] = v
                else: regs.setdefault("bad", []).append((port, v))
            return regs
        frames_regs = [regs_of(o) for o in per_frame]
        check(all(set(r.keys()) == set(range(12)) for r in frames_regs), "%s: every frame writes exactly R0..R11 (%d frames)" % (name, frames))
        check(max(costs) <= 4000, "%s: snd_isr max %d T, avg %.0f T, min %d T (<= 4,000)" % (name, max(costs), sum(costs) / len(costs), min(costs)))
        # compare with the reference model (frame 0 = request pickup; music starts on frame 0's call)
        ref = ay_reference(song, tbl, frames)
        bad = 0; first_bad = None
        for f in range(frames):
            periods, vols, mixer, noise = ref[f]; r = frames_regs[f]
            for c in range(3):
                got_p = r[2 * c] | ((r[2 * c + 1] & 15) << 8)
                if r[8 + c] != vols[c] or (vols[c] and got_p != periods[c]):
                    bad += 1
                    if first_bad is None: first_bad = (f, c, got_p, periods[c], r[8 + c], vols[c])
            if r[7] != mixer or r[6] != noise:
                bad += 1
                if first_bad is None: first_bad = (f, "mixer/noise", r[7], mixer, r[6], noise)
        check(bad == 0, "%s: register stream == Python reference model for %d frames (mismatches %d, first %s)" % (name, frames, bad, first_bad))
        # loop: once the song is running (first row at frame 4), frame f and f + loop_frames must be identical
        same = all(frames_regs[f] == frames_regs[f + loop_frames] for f in range(4, 600))
        check(same, "%s: stream periodic with the loop length %d frames (%.1f s)" % (name, loop_frames, loop_frames / 50))
        order_pos = int.from_bytes(mc.peek(S["mus_opos"], 2), "little") - S["%s_order" % name]
        print("  %s: order position after %d frames = %d (order length %d)" % (name, frames, order_pos, len(info["order"])))
        # render WAV: one full loop + 2 s
        events = []
        for f, r in enumerate(frames_regs[:loop_frames + 100]):
            for reg in range(11):
                events.append((f, reg, r[reg]))
        t0 = time.time()
        samples = ayrender.render_ay(events, loop_frames + 100)
        wav = BUILD / ("music_%s.wav" % name); ayrender.write_wav(wav, samples)
        m = mp3(wav)
        print("  wrote %s (%.1f s, render %.1f s) %s" % (wav, len(samples) / 44100, time.time() - t0, m))
        results[name] = dict(max_t=max(costs), avg_t=sum(costs) / len(costs), loop_frames=loop_frames, bytes=info["bytes"])
    # ---- SFX on channel C while the game track plays
    mc.call("snd_music", a=2); mc.call("snd_isr")
    for _ in range(40): mc.call("snd_isr")
    n0 = len(mc.outs)
    t = mc.call("snd_fx", a=1) - CALL_JP_T
    check(t < 160 and len(mc.outs) == n0, "snd_fx 1 (128K): enqueued only, %d T, no OUT" % t)
    sfx_frames = []
    for f in range(40):
        k = len(mc.outs); c = mc.call("snd_isr") - CALL_JP_T
        regs = {}; sel = None
        for _, port, v in mc.outs[k:]:
            if port == 0xFFFD: sel = v
            else: regs[sel] = v
        sfx_frames.append((c, regs))
    # shot: frame 0..2 noise 3 period 300.., frames 3..8 second segment, then C back to music
    r0 = sfx_frames[0][1]
    check(r0[4] | (r0[5] << 8) == 300 and r0[10] == 15 and r0[6] == 3 and not (r0[7] & 0x24), "AY sfx 1 frame 0: C period 300, vol 15, noise 3, mixer C tone+noise on (R7=%02x)" % r0[7])
    r1 = sfx_frames[1][1]
    check(r1[4] | (r1[5] << 8) == 360 and r1[10] == 13, "AY sfx 1 frame 1: period 360 (slide +60), vol 13 (0xF0-20=0xDC) (R10=%d)" % r1[10])
    r8 = sfx_frames[8][1]; r9 = sfx_frames[9][1]
    check(r8[6] == 12 and (r9[7] & 0x20), "AY sfx 1 ends after 9 frames: frame 8 noise 12, frame 9 noise C off (R7=%02x)" % r9[7])
    check(max(c for c, _ in sfx_frames) <= 4000, "snd_isr with SFX active: max %d T" % max(c for c, _ in sfx_frames))
    # all 10 AY SFX run to completion and stay <= 4000 T
    worst_sfx_t = 0; lengths = []
    for i in range(1, 11):
        mc.call("snd_fx", a=i)
        n = 0
        for f in range(200):
            worst_sfx_t = max(worst_sfx_t, mc.call("snd_isr") - CALL_JP_T)
            n += 1
            if int.from_bytes(mc.peek(S["sfx_ptr"], 2), "little") == 0: break
        lengths.append(n)
    check(all(1 < n < 60 for n in lengths), "all 10 AY SFX terminate: frames %s" % lengths)
    check(worst_sfx_t <= 4000, "snd_isr worst with each SFX: %d T" % worst_sfx_t)
    # opt_sfx = 0
    mc.poke(S["opt_sfx"], [0]); mc.call("snd_fx", a=5)
    check(int.from_bytes(mc.peek(S["sfx_req"], 2), "little") == 0, "opt_sfx=0: snd_fx ignored on 128K")
    mc.poke(S["opt_sfx"], [1])
    # stop
    mc.call("snd_music", a=0); k = len(mc.outs); mc.call("snd_isr")
    regs = {}; sel = None
    for _, port, v in mc.outs[k:]:
        if port == 0xFFFD: sel = v
        else: regs[sel] = v
    check(regs[8] == 0 and regs[9] == 0 and regs[10] == 0 and regs[7] == 0x3F, "snd_music 0: volumes 0, mixer 3F")
    mc.poke(S["opt_music"], [0]); mc.call("snd_music", a=1); mc.call("snd_isr")
    check(mc.peek(S["mus_on"])[0] == 0, "opt_music=0: snd_music 1 does not start")
    t = mc.call("snd_menu_tick") - CALL_JP_T
    check(t == 10, "snd_menu_tick (128K) = ret")
    # render an SFX demo too: the 10 AY SFX in a row on silence
    mc.poke(S["opt_music"], [1]); mc.call("snd_music", a=0); mc.call("snd_isr")
    events = []; frame = 0
    for i in range(1, 11):
        mc.call("snd_fx", a=i)
        for f in range(45):
            k = len(mc.outs); mc.call("snd_isr")
            sel = None
            for _, port, v in mc.outs[k:]:
                if port == 0xFFFD: sel = v
                else: events.append((frame, sel, v))
            frame += 1
    samples = ayrender.render_ay(events, frame)
    wav = BUILD / "sfx_ay.wav"; ayrender.write_wav(wav, samples); m = mp3(wav)
    print("  wrote %s (%.1f s) %s" % (wav, len(samples) / 44100, m))
    return player_bytes, notes_bytes + menu_bytes + game_bytes, results, worst_sfx_t

def main():
    if "--build" in sys.argv:
        subprocess.run(["bash", str(ROOT / "tools/snd_build.sh")], check=True)
    b = test_beeper()
    a = test_ay()
    summary = dict(beeper_bytes=b[0], sfx_worst_t=b[1], menu_tick_max_t=b[2], menu_tick_rich_t=b[3],
                   ay_player_bytes=a[0], ay_data_bytes=a[1], ay_tracks=a[2], ay_isr_sfx_worst_t=a[3], fails=FAILS)
    (BUILD / "test_sound_summary.json").write_text(json.dumps(summary, indent=1))
    print("== %d checks failed" % len(FAILS) if FAILS else "== ALL CHECKS PASSED")
    for f in FAILS: print("   -", f)
    sys.exit(1 if FAILS else 0)

if __name__ == "__main__":
    main()
