#!/bin/bash
# m22_zes_argcheck.sh - validate the launcher's ZEsarUX 13.0 arguments on hal-ec2 (same version as the Deck), headless
cd ~/work/killemall
ZES=tools/zesarux/zesarux
strings $ZES | grep -E '^/dev/input/js' | head -3
ARGS=(--noconfigfile --vo null --ao null --machine 48k --nosplash --nowelcomemessage --disable-all-first-aid
      --joystickemulated Kempston --realjoystickpath /dev/input/js0 --cleareventlist
      --joystickevent -1 Up --joystickevent +1 Down --joystickevent -0 Left --joystickevent +0 Right
      --joystickevent -7 Up --joystickevent +7 Down --joystickevent -6 Left --joystickevent +6 Right
      --joystickevent 0 Fire --joystickevent 6 ExitEmulator
      --joystickkeybt 1 109 --joystickkeybt 4 122 --joystickkeybt 5 120 --joystickkeybt 7 13
      --quickexit --exit-after 6 build/killemall48_m22.tap)
( cd tools/zesarux && timeout 40 ./zesarux "${ARGS[@]/build\//$PWD/../../build/}" > /tmp/zes_argcheck.log 2>&1 ); echo "rc=$?"
grep -iE 'unknown|error|invalid|not valid|joystick|exit' /tmp/zes_argcheck.log | head -12
wc -l /tmp/zes_argcheck.log
