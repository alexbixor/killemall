#!/bin/bash
# m23_survey1.sh - READ-ONLY facts before M2.3 (floor lines + SPACE fire): launcher map, test floor detection, stack tool, init
cd ~/work/killemall
echo "--- launcher joystick lines"; grep -n -E 'joystick|JS=' tools/deck/launch-killemall.sh
echo "--- pad test expectations"; sed -n 100,125p tools/m22_pad_test.py
echo "--- chk48 floor scan"; sed -n 44,60p tools/chk48.py
echo "--- sprite_scale background detection"; grep -n -iE '0x55|0xAA|checker|floor|background|bg' tools/test_sprite_scale.py | head -12
echo "--- hud test floor refs"; grep -n -iE '0x55|0xAA|checker|floor' tools/test_game_hud.py tools/test_game_enemies.py tools/test_frontend.py | head -12
echo "--- m22_stack.py core"; grep -n -iE '65008|0xFDF0|sp|fill|water|lowest|depth' tools/m22_stack.py | head -20
echo "--- kea48 init 20..40"; sed -n 20,40p src/48k/kea48.asm
echo "--- kea48 836..846 (ld sp,hl)"; sed -n 836,846p src/48k/kea48.asm
echo "--- includes of gen files"; grep -n -E 'include' src/48k/kea48.asm src/128k/kea128_gen.asm | head -20
echo "--- build script"; cat tools/build_m22_48.sh | head -30
echo "--- shots usage"; sed -n 1,15p tools/m22_shots.py
echo "--- tests on in_keys defaults"; grep -n -E 'in_keys|0x7F|"M"|SPACE' tools/test_frontend.py | head -15
echo "--- fire strings anywhere"; grep -rn -iE 'fire' src/common/hud.asm src/common/title*.asm src/common/text*.asm 2>/dev/null | head -5
echo "--- status tail"; tail -5 build/m22_status.txt