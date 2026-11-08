#!/bin/bash
# deck_zes_probe.sh - READ-ONLY: ZEsarUX 13 options we want for a one-click 48K launcher + joystick visibility
cd ~/Applications/zesarux || exit 1
export LD_LIBRARY_PATH=~/Applications/zesarux/libs
./zesarux --help 2>&1 | grep -E '^ *--(tape|realtape|noautoload|autoload|smartload|nowelcomemessage|nosplash|disable-all-first-aid|fullscreen|realvideo|joystickemulated|joystickevent|joystickkeybt|joystickkeyev|joystickindex|enablejoystick|disablejoystick|exit-after|quickexit|vo|ao|zoom|no-time-tests|disabletimexvideo|frameskip|forcevisiblehotkeys|nocursor|hidemousepointer|disableborder|border)' | cut -c1-110
echo "--- joystick devices"
ls -l /dev/input/js* 2>&1 | head
grep -A4 -iE 'Name=.*(Steam|Valve)' /proc/bus/input/devices | grep -E 'Name|Handlers' | head -12
echo "--- zesarux config file present?"
ls -la ~/.zesaruxrc 2>&1 | head -2
date -u +%H:%MZ
