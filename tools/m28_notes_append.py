#!/usr/bin/env python3
"""m28_notes_append.py - append the 3 Nov 2026 decisions to build/m25_notes.md (append-only file). Idempotent: skips if the
section marker is already present."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
p = ROOT / "build/m25_notes.md"
MARK = "## 3 Nov 2026 — M2.6 blood/stain shipped, M2.7 one-zip distribution + Next boot, M2.8 strafe fix"
s = p.read_text()
if MARK in s:
    print("notes: already appended"); raise SystemExit
sec = """
%s
- M2.6 Track 2 done (P2E per-cell colour, ceiling D5, coloured items, blood flash + muzzle flash, floor stain). Stain = corpse
  cells red WITHOUT BRIGHT (CMX bit 7 -> attr_write), decode 6 B + corpse colour 1 B; aw_fill (13 B) moved into the pre-TEX
  padding (gate af_end <= TEX). Gates 14/14 PASS 14:09Z (build/m26_gates_stain.out), stain stills oracle 0/23 diffs.
  Splatter stays 128K-only, later. User: "no, stain after the video" (video m26_blood_walk.mp4 sent 11:50Z, stain still 14:11Z).
- Deck push "Push" (16:16Z, tools/deck/deck_m26_install.sh): 48K f6ebd4e6ad229b9c 47,711 B, 128K d508e72912a60ddc 50,611 B;
  E1 tapes kept as *_e1.tap; both headless self-tests rc 0. The "ERROR ... Just kidding ;)" lines in the Deck logs are ZEsarUX
  splash jokes, not failures.
- M2.7 one distribution for 48K/128K/Next (user: SD card or emulator, never tape; one zip; friend with a REAL Next beta-tests):
  tools/mknex.py -> build/killemall128.nex (NEX V1.2, title.scr loading screen, banks 5/2/0/1, SP 65008, PC 0x6000 stub in
  bank 5: ROM 3 via 1FFD/7FFD, nextreg 7,0, jp 32768). tools/make_release.py -> build/release/killemall-<ver>.zip
  (KILLEMALL/killemall.nex + killemall48.tap + killemall128.tap + README.txt, SHA256SUMS). 0.27.0 sent 16:02Z (sha 7d9e91fa...),
  0.27.1 = + strafe fix (sha a4e9fc938129a196, 48,018 B). Per-level SD streaming NOT built (everything still fits in memory).
- Emulated Next (ZEsarUX 13.0 TBBlue) would not boot with --enable-divmmc (black screen, PC stuck < 0x2000): ZEsarUX's own
  "Autoconfigure Next SD" uses --enable-divmmc-PORTS only (read from the ZEsarUX main source via the GitHub API; raw URLs 404).
  Fixed in nex_diag.py / nex_probe.py / runnex.py. Proof chain tools/nex_play3.py (state-driven from the RENDERED screen; NextZXOS
  menus are not on the ULA layer, so attribute classification failed in nex_play2.py): Browser -> 17th entry killemall.nex ->
  ENTER -> fe_loop, 7FFD = 0x10, title attrs identical to title.scr -> START -> health 100/ammo 50 -> walk/fire work.
  NextZXOS launches .nex at 28 MHz (nextreg 7 = 0x33, 19.0 fps, 3x too fast): stub writes nextreg 7,0 -> 9.75 fps at 3.5 MHz
  (no contention on the Next, hence > 128K's 6.5). Picture build/m27_nex_tg.png. Real-HW result from the friend still pending.
- M2.8 strafe ("all good, but strafe is not working!" ~17:00Z): strafe was never wired - in_read delivered b6/b7 (0x40/0x80
  measured live, tools/m28_strafe_probe.py on the real tape) but game_tick tested bits 0..5 only. Fix tools/m28_edit_strafe.py
  (idempotent): helper `strafe` (A = heading offset) = move_by with B = 0 (fl_ph is forward distance only); Z = heading - 64,
  X = heading + 64 (turn-right P is angle + 6, so the right-hand side is + 64). Two wrong versions caught by
  tools/m28_strafe_check.py (v1 wrong sign; v2 block sat inside the back-key branch -> only strafed while reversing; found with
  tools/m28_strafe_dbg.py: direct call moved, game_tick(0x80) did not). Check: imp on the right slides to the centre under X
  (col 16.9 -> 10.8) and off to the right under Z (-> 22.2); angle and fl_ph untouched; 6 x 0.15 = 0.9 cell; Z+X cancel; walls stop.
  Cost +30 B high; msg_clear/msg_dead (23 B) moved to lowcode.asm. 48K hi_end 0xFDC6 (42 B free, gate 40), low 9 B free;
  128K hi_end 0xFC40 (432 B). Gates 16/16 PASS (build/m28_gates_strafe.out), 128K 6.51 fps tear 0/24, stain oracle PASS,
  KEA128=1 strafe check PASS. Deck push 17:41Z (deck_m28_install.sh): 48K a969b1afff57dd8e 47,718 B, 128K 409b0cb77c04766f
  50,618 B, M2.6 tapes kept as *_m26.tap, self-tests rc 0. Pad: L1/R1 + left-stick X were already mapped to Z/X.
- Open finding for M3.0: game speed is per rendered frame (0.15 cell per tick), so the 48K (9 fps) plays 38%% faster than the
  128K (6.5 fps) and the Next at 28 MHz (19 fps) was unplayable. A fixed-rate game tick from the 50 Hz ISR frame counter would make
  all three editions play at the same speed and let the Next render at 28 MHz for free.
""" % MARK
p.write_text(s.rstrip("\n") + "\n" + sec)
print("notes: appended %d lines" % sec.count("\n"))
