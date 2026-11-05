#!/bin/bash
# z88dk smoke test v2: the "new" (_DEVELOPMENT) libs need a stdio startup (CRT 31 = no stdio) -> use startup 0/1 or the
# classic lib (-clib=default). Try both libs for zx and zxn; print rc + produced files.
set -u
export ZCCCFG=~/work/killemall/tools/z88dk/lib/config PATH=~/work/killemall/tools/z88dk/bin:$PATH
mkdir -p /tmp/kea_smoke && cd /tmp/kea_smoke && rm -f hello* *.log
printf '#include <stdio.h>\nint main(void){printf("KILL EM ALL\\n");return 0;}\n' > hello.c
printf '#include <arch/zx.h>\n#include <string.h>\nint main(void){zx_cls(INK_WHITE|PAPER_BLACK);memset((void*)0x4000,0xAA,2048);while(1){}}\n' > fill.c
zcc +zx -vn -clib=sdcc_iy -startup=1 hello.c -o hello48_new -create-app > zx_new.log 2>&1;  echo "## zx new-lib hello rc=$? $(ls hello48_new* 2>/dev/null | tr '\n' ' ')"
zcc +zx -vn -clib=default hello.c -o hello48_cls -create-app > zx_cls.log 2>&1;              echo "## zx classic hello rc=$? $(ls hello48_cls* 2>/dev/null | tr '\n' ' ')"
zcc +zx -vn -clib=sdcc_iy -startup=31 fill.c -o fill48 -create-app > zx_fill.log 2>&1;        echo "## zx new-lib fill (no stdio) rc=$? $(ls fill48* 2>/dev/null | tr '\n' ' ')"
zcc +zxn -vn -clib=sdcc_iy -startup=1 hello.c -o hellonext -subtype=nex -create-app > zxn_new.log 2>&1; echo "## zxn new-lib hello rc=$? $(ls hellonext* 2>/dev/null | tr '\n' ' ')"
zcc +zxn -vn -clib=sdcc_iy -startup=31 fill.c -o fillnext -subtype=nex -create-app > zxn_fill.log 2>&1; echo "## zxn new-lib fill rc=$? $(ls fillnext* 2>/dev/null | tr '\n' ' ')"
for f in zx_new zx_cls zx_fill zxn_new zxn_fill; do [ -s $f.log ] && { echo "-- $f.log:"; head -3 $f.log | cut -c1-160; }; done
echo "## $(date -u +%H:%MZ)"
