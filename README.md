# Kill'em All

A first-person "Doom-look" ray-cast shooter for the **ZX Spectrum 48K**, **ZX Spectrum 128K** and
**ZX Spectrum Next**, written in Z80 / Z80N assembly with a Python asset pipeline. One game design, one
map/asset pipeline, three editions that each use everything their machine offers. Own title, own art,
own code - no third-party game assets.

| Edition | Machine | Renderer | Window | Measured fps | Output |
|---|---|---|---|---|---|
| 48K | 3.5 MHz Z80, 48 KB | ray-cast walls, 1-bit textures, attribute shading per 8x8 cell, masked sprites, textured ceiling | 192-px window + HUD | 6.5-7.9 | `killemall48.tap` |
| 128K | 3.5 MHz Z80, 128 KB paged | same core, double-buffered shadow-screen flip, 8 levels, 6 enemy types, 32x48 hi-res sprites blitted from bank 3, AY music | 192-px window + HUD | 5.9-7.3 | `killemall128.tap` |
| Next ("edition B") | Z80N 28 MHz | ray walker + wall/floor/ceiling painters into the 128x96 256-colour LoRes layer, software sprites with wall occlusion, 8 levels, 10 Hz game rules | 128x96 + HUD | 20-21 (ZEsarUX, core 3.02) | `killemall_b.nex` |

All frame rates above were **measured** on ZEsarUX with the tick counter, not estimated. The Next build
has not yet been timed on real hardware (core 3.03 / zero-wait-state) - `build/next/hwtest.nex` in the
release is the test kit for that, see `docs/` and the H1 notes.

## Status (8 Nov 2026)

- 48K: **FINAL v1.0** (closed 8 Nov 2026 13:15Z). Milestone M2.5 frozen: 3 levels, 3 enemy types, beeper SFX, loading screen,
  6.5-7.9 fps. Byte-identical build gated in CI. Reopened only by a bug report; no mouse (no memory left).
- 128K: **FINAL v1.0** (closed 8 Nov 2026 13:15Z). 8 levels, enemy types 1-6 with hand-drawn 32x48 art, shadow-screen flip,
  bank-3 hi-res blitter, AY music, Kempston mouse look, 5.9-7.3 fps. Not implemented by decision: the cheaper AY player
  (lane Q spec, +0.13 fps best case, not worth the risk). `killemall128_hires.tap` (2-px zombie route) stays experimental.
- Next: edition B playable and in active development (black bars + HUD/weapon flash fixed 8 Nov; Kempston/PS2 mouse look +
  vertical look merged 8 Nov, OFF by default - press I to toggle, W/S look, E recentre; Doom-class colour sprite art,
  hardware sprites (lane N6) and zxnDDMA pre-fill next). 20-21 fps on real hardware (core 3.03,
  zero wait state), matching ZEsarUX.

Pre-built tapes and `.nex` files are attached to the GitHub **Releases**; their sha256/md5 are listed there
and in the release notes so you can verify what you downloaded.

## Repository layout

```
src/48k/      48K engine (kea48.asm + includes) - the 128K build is generated from this source
src/128k/     128K shims: paging, shadow flip, bank 1 levels, bank 3 hi-res blitter
src/common/   shared engine pieces: ray pass, sprites, enemies (etab), state, floor, HUD
src/next/     Spectrum Next edition B: walker, drawers, game, HUD, hwtest kit
assets/       levels (text maps), sprite sheets, hi-res sprite art, music/SFX definitions  [CC BY 4.0]
tools/        Python + shell: map compiler, sprite packer, tape/.nex builders, oracles, test harnesses
docs/         engine specs (Next edition B v0.1/v0.2), enemies, content plan
DESIGN.md     the original design document (26 Oct 2026)
ARCH_M2.md    architecture notes for the 48K M2 engine
```

## Building

Toolchain: `pasmo` 0.5.3 (Debian/Ubuntu package), Python 3.11+ with Pillow, and for the test oracles a
headless [ZEsarUX](https://github.com/chernandezba/zesarux) build (TBBlue machine for the Next).

```bash
sudo apt install pasmo python3-venv
python3 -m venv .venv && .venv/bin/pip install pillow numpy
tools/build_m25_48.sh          # -> build/killemall48_m25.tap   (48K)
tools/build128.sh              # -> build/killemall128_m2.tap   (128K, FLIP + LEVELS8 + BANK3)
tools/build128_hires.sh        # -> build/killemall128_hires.tap (128K with hi-res zombies)
```

The Next build (`tools/nx_build.py`) packs textures, sprites and levels into a `.nex`:

```bash
.venv/bin/python tools/nx_textures.py --out build/next/assets_b        # palette, walls, floors
.venv/bin/python tools/nx_sprites_b.py --out build/next/assets_b/sprites_b.bin --out2 build/next/assets_b/sprites2_b.bin
.venv/bin/python tools/mapc.py next build/next/levels.bin assets/levels/0[1-8]_*.txt
.venv/bin/python tools/nx_build.py --src src/next/main_b.asm --out build/next/killemall_b.nex --bin-name main_b --equ MOUSE_B=1 \
   --assets build/next/assets_b --levels build/next/levels.bin --levels-txt assets/levels \
   --sprites build/next/assets_b/sprites_b.bin --sprites2 build/next/assets_b/sprites2_b.bin \
   --level build/next/level01.bin --level-txt assets/levels/01_entry.txt
```

Every build script ends with layout gates (page alignment, stack gap, bank overflow) that fail the build
loudly; `tools/gates_v1.sh` runs the full 48K release gate set.

## How it was developed

The engine was built **correct-first, then fast**: every renderer has a Python reference model and a
headless ZEsarUX oracle that compares the emulated frame byte-for-byte against the reference (0 differing
bytes required) before any optimisation. The `tools/nx_test_*.py` and `tools/test_*.py` scripts are those
oracles. Development ran as parallel "lanes" with disjoint file ownership; the commit history keeps one
commit per lane with the measured evidence in the message.

## Licence

Code: MIT (see `LICENSE`). Game assets under `assets/`: CC BY 4.0 (see `assets/LICENSE`).
