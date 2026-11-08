#!/bin/bash
# Kill'em All toolchain (option A, approved 26 Oct 2026): z88dk 2.4 from the GitHub https source tarball + ZEsarUX 13.0
# (Ubuntu 24 build) from GitHub releases. Everything under ~/work/killemall/tools, nothing system-wide, no sudo.
set -u
T=~/work/killemall/tools; mkdir -p "$T" && cd "$T"
echo "## $(date -u +%H:%M:%SZ) start"
if [ ! -x "$T/z88dk/bin/zcc" ]; then
  curl -sS -L -m 600 -o z88dk-src-2.4.tgz https://github.com/z88dk/z88dk/releases/download/v2.4/z88dk-src-2.4.tgz || { echo "z88dk download FAILED"; exit 1; }
  echo "## z88dk tarball: $(stat -c %s z88dk-src-2.4.tgz) bytes"
  tar xzf z88dk-src-2.4.tgz && cd z88dk && export BUILD_SDCC=0 BUILD_SDCC_HTTP=0
  (./build.sh -e > "$T/z88dk-build.log" 2>&1; echo "## z88dk build rc=$? at $(date -u +%H:%M:%SZ)")
  cd "$T"
fi
ls -1 "$T/z88dk/bin" 2>/dev/null | wc -l | sed 's/^/## z88dk bin files: /'
if [ ! -x "$T/zesarux/zesarux" ]; then
  curl -sS -L -m 600 -o zesarux.tgz https://github.com/chernandezba/zesarux/releases/download/ZEsarUX-13.0/ZEsarUX_linux-13.0-ubuntu24_x86_64.tar.gz || echo "zesarux download FAILED"
  echo "## zesarux tarball: $(stat -c %s zesarux.tgz 2>/dev/null) bytes"
  mkdir -p zesarux && tar xzf zesarux.tgz -C zesarux --strip-components=1 2>/dev/null
  find zesarux -maxdepth 2 -type f -name 'zesarux*' | head -3
fi
echo "## $(date -u +%H:%M:%SZ) done"
