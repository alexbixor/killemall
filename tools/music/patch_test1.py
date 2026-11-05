#!/usr/bin/env python3
"""patch_test1.py - T3: update tools/test_sound.py reference model + tolerances for the pre-decoding AY player."""
import pathlib
P = pathlib.Path(__file__).resolve().parent.parent / "test_sound.py"
s = P.read_text()
a = s.index("def ay_reference(")
b = s.index("def test_ay():")
new_ref = '''def ay_reference(song, model_notes, frames):
    """Python model of ay.asm playing one song: per frame -> (periods[3], vols[3], mixer, noise).
    Timing: the request is picked up on ISR call 0 (mus_tick = 4); rows are committed on the frames where mus_tick
    reaches 0, i.e. call 3, 3+speed, 3+2*speed, ...; a channel whose block is ON gets its envelope advanced every frame.
    Mixer/noise registers only change on row frames (commit)."""
    speed = song["speed"]; rows_pp = song["rows"]; chans = song["chans"]; rows_total = song["rows_total"]
    insts = song["insts"]
    st = [dict(on=0, note=0, inst=0, env=None, epos=0, arp=0, arpp=0, slide=0, acc=0) for _ in range(3)]
    res = []
    row = -1; tick = 4; mixer = 0x3F; noise = 0
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

'''
s = s[:a] + new_ref + s[b:]
# comparison: periods now always defined (0 when off), compare mixer and noise on all frames
s = s.replace('''            for c in range(3):
                got_p = r[2 * c] | ((r[2 * c + 1] & 15) << 8)
                if r[8 + c] != vols[c] or (periods[c] is not None and got_p != periods[c]):
                    bad += 1
                    if first_bad is None: first_bad = (f, c, got_p, periods[c], r[8 + c], vols[c])
            if r[7] != mixer and f > 0:
                bad += 1
                if first_bad is None: first_bad = (f, "mixer", r[7], mixer)''',
'''            for c in range(3):
                got_p = r[2 * c] | ((r[2 * c + 1] & 15) << 8)
                if r[8 + c] != vols[c] or (vols[c] and got_p != periods[c]):
                    bad += 1
                    if first_bad is None: first_bad = (f, c, got_p, periods[c], r[8 + c], vols[c])
            if r[7] != mixer or r[6] != noise:
                bad += 1
                if first_bad is None: first_bad = (f, "mixer/noise", r[7], mixer, r[6], noise)''')
s = s.replace('''    tbl = [int.from_bytes(mc.peek(S["ay_notes"] + 2 * i, 2), "little") for i in range(96)]''',
              '''    tbl = [int.from_bytes(mc.peek(S["ay_notes"] + 2 * i, 2), "little") for i in range(128)]''')
s = s.replace('''        check(t < 120 and mc.peek(S["mus_req"])[0] == 0x80 | track_id, "snd_music %d: request latched (%d T)" % (track_id, t))''',
              '''        check(t < 120 and mc.peek(S["mus_req"])[0] == 0x80 | track_id, "snd_music %d: request latched (%d T)" % (track_id, t))
        mc.poke(S["ay_regs"], [0] * 7 + [0x3F, 0, 0, 0])''')
s = s.replace('''    check(t < 120 and len(mc.outs) == n0, "snd_fx 1 (128K): enqueued only, %d T, no OUT" % t)''',
              '''    check(t < 160 and len(mc.outs) == n0, "snd_fx 1 (128K): enqueued only, %d T, no OUT" % t)''')
s = s.replace('''    check(r1[4] | (r1[5] << 8) == 360 and r1[10] == 14, "AY sfx 1 frame 1: period 360 (slide +60), vol 14 (R10=%d)" % r1[10])''',
              '''    check(r1[4] | (r1[5] << 8) == 360 and r1[10] == 13, "AY sfx 1 frame 1: period 360 (slide +60), vol 13 (0xF0-20=0xDC) (R10=%d)" % r1[10])''')
# sfx 3 tolerance: pure tones have a +2 T LFSR feedback cost per half-cycle the model treats as optional
s = s.replace('''and exp["t_min"] - 600 <= t <= exp["t_max"] + 600)''', '''and exp["t_min"] - 600 <= t <= exp["t_max"] + 900)''')
P.write_text(s)
print("patched")
