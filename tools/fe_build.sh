#!/bin/bash
# fe_build.sh - assemble the T2 standalone front-end test (state.asm + input.asm + frontend.asm + fe_stubs.asm) to
# build/fe_test.tap (org 32768, autostart BASIC loader, same pasmo invocation as tools/build48.sh), report the RAM cost,
# and check that input.asm + frontend.asm also assemble next to T3's real beeper.asm (duplicate labels / externals).
set -e
cd ~/work/killemall
pasmo --tapbas tools/fe_test_main.asm build/fe_test.tap build/fe_test.sym
ls -la build/fe_test.tap | awk '{print "tap bytes", $5}'
.venv/bin/python tools/fe_sizes.py build/fe_test.sym
if [ -f src/common/beeper.asm ]; then
  pasmo tools/fe_integ_check.asm build/fe_integ.bin build/fe_integ.sym && echo "integration check with beeper.asm: assembles ($(stat -c %s build/fe_integ.bin) bytes)"
fi
