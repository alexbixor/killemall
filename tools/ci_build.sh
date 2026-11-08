#!/bin/bash
# ci_build.sh - reproducible build of the three editions from a clean checkout (used by .github/workflows/build.yml and
# by hand).  Expects pasmo on PATH and a venv with Pillow + numpy in .venv/.  Writes everything under build/.
# Location-independent: every script resolves the repo root from its own path.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
mkdir -p build/next build/night src/48k/gen src/128k/gen
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

echo "== title screen (procedural art -> SCREEN\$)"
$PY tools/title_art.py build/title_src.png
$PY tools/scrconv.py png2scr build/title_src.png build/title.scr --strict

echo "== 48K"
# build_m25_48.sh ends with "pristine" checks against the older m2/m22/m23/m24 tapes, which a clean checkout does not have;
# the layout gates before them abort the script themselves (set -e + exit 1), so success = both tapes exist.
bash tools/build_m25_48.sh > build/ci_48k.out 2>&1 || true
test -s build/kea48.tap && test -s build/killemall48_m25.tap || { tail -30 build/ci_48k.out; exit 1; }
grep -E "^(tap bytes|hi_end|low_end|HTABN|TEX|COLBASE|dash|level_data)" build/ci_48k.out
grep -qE "TOO CLOSE|OVERFLOWS|: NO" build/ci_48k.out && { echo "48K layout gate failed"; exit 1; }

echo "== 128K"
bash tools/build128.sh > build/ci_128k.out 2>&1 || { tail -30 build/ci_128k.out; exit 1; }
grep -E "^(128K|bank)" build/ci_128k.out || true

echo "== Next edition B"
$PY tools/nx_textures.py --edition b --out build/next/assets_b > build/ci_next.out 2>&1 || { tail -30 build/ci_next.out; exit 1; }
$PY tools/nx_tables.py >> build/ci_next.out 2>&1          # build/next/tables_bank4.bin (SIN/COS/RD/RECIP + IM1 ISR)
$PY tools/nx_sprites_b.py --out build/next/assets_b/sprites_b.bin --out2 build/next/assets_b/sprites2_b.bin >> build/ci_next.out 2>&1
$PY tools/mapc.py next build/next/level01.bin assets/levels/01_entry.txt >> build/ci_next.out 2>&1
$PY tools/mapc.py next build/next/levels.bin assets/levels/0[1-8]_*.txt >> build/ci_next.out 2>&1
$PY tools/nx_build.py --src src/next/main_b.asm --out build/next/killemall_b.nex --bin-name main_b \
  --assets build/next/assets_b --level build/next/level01.bin --level-txt assets/levels/01_entry.txt \
  --sprites build/next/assets_b/sprites_b.bin --levels build/next/levels.bin --levels-txt assets/levels \
  --sprites2 build/next/assets_b/sprites2_b.bin >> build/ci_next.out 2>&1 || { tail -30 build/ci_next.out; exit 1; }

echo "== artefacts"
sha256sum build/kea48.tap build/killemall48_m25.tap build/kea128.tap build/killemall128_m2.tap build/next/killemall_b.nex | tee build/ci_sha256.txt
