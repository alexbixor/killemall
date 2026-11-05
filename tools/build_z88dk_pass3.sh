#!/bin/bash
# z88dk 2.4 build, pass 3: with pkg-config + libxml2-dev present. Logs to tools/z88dk-build3.log; prints a summary.
set -u
cd ~/work/killemall/tools/z88dk || exit 1
sudo -n apt-get install -y -qq pkg-config > /tmp/kea_apt3.log 2>&1; echo "## apt rc=$?"
export BUILD_SDCC=0 BUILD_SDCC_HTTP=0
./build.sh -e > ../z88dk-build3.log 2>&1; echo "## build rc=$? at $(date -u +%H:%MZ)"
echo "## bin: $(ls bin | wc -l) files; clibs: $(ls lib/clibs | grep -cE '\.lib$') libs; zx clibs: $(ls lib/clibs | grep -E '^zx(n)?_clib' | tr '\n' ' ')"
grep -nE 'fatal error|\*\*\*' ../z88dk-build3.log | head -3 | cut -c1-200
# smoke test: hello world for zx (48K) and zxn (Next)
export ZCCCFG=$PWD/lib/config PATH=$PWD/bin:$PATH
mkdir -p /tmp/kea_smoke && cd /tmp/kea_smoke
printf '#include <stdio.h>\nint main(void){printf("KILL EM ALL\\n");return 0;}\n' > hello.c
zcc +zx -vn -startup=31 -clib=sdcc_iy hello.c -o hello48 -create-app > zx.log 2>&1; echo "## zx hello rc=$? $(ls -1 hello48* 2>/dev/null | tr '\n' ' ')"
zcc +zxn -vn -startup=31 -clib=sdcc_iy hello.c -o hellonext -subtype=nex -create-app > zxn.log 2>&1; echo "## zxn hello rc=$? $(ls -1 hellonext* 2>/dev/null | tr '\n' ' ')"
tail -2 zx.log zxn.log | cut -c1-160
