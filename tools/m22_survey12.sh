#!/bin/bash
# m22_survey12.sh - read-only facts for writing the dashboard: init/cls order, hud callers, ammo cap, damage path, type tables, low-block spare
cd ~/work/killemall
echo "== hud/cls/init callers"; grep -n "hud_init\|hud_update\|hud_message\|call cls\|^cls:\|init_game:\|^start:\|call fe_run\|jp fe_run\|restart_level:\|level_done\|next_level" src/48k/kea48.asm src/common/*.asm | grep -v "^\S*:[0-9]*:;" | head -30
echo "== print routine"; awk '/^print:/{f=1} f{print; n++} n>14{exit}' src/48k/kea48.asm
echo "== ammo changes"; grep -n "(ammo)" src/common/*.asm | head
echo "== health changes (damage path)"; grep -n "(health)" src/common/*.asm | head
echo "== type tables"; grep -n "THSPR\|TYPEINK" src/common/*.asm tools/gen48.py | grep -v "^\S*:[0-9]*:;" | head -12
echo "== THSPR/TYPEINK data"; grep -n -A3 "^THSPR:\|^TYPEINK:" src/common/*.asm src/48k/gen/*.asm | head -16
echo "== pickup types"; grep -n "cp 2[0-9]\|cp 1[6-9]\|pick" src/common/game_c.asm src/common/game_d.asm | head -16
echo "== low block end / 32768 gap"; grep -E "^(lo_end|level_data|LEVEL_END|sprites_end|SCHAIN_END|spr_table)\s" build/kea48.sym; python3 - <<'EOF'
import re
syms=[]
for l in open('build/kea48.sym'):
    m=re.match(r'(\S+)\s+EQU\s+([0-9A-F]+)H',l)
    if m: syms.append((int(m.group(2),16),m.group(1)))
syms.sort()
lo=[s for s in syms if 27904<=s[0]<32768]
print("highest low-block symbols:", [(hex(a),n) for a,n in lo[-4:]])
EOF
echo "== kea48 block structure"; sed -n 930,945p src/48k/kea48.asm
echo "== level block size / nthings"; grep -n "1081\|LEVEL_BLK\|n_things\|nthings" tools/mklevelblk.py | head -5
echo "== stack depth guess: deepest call chain uses? (ISR push count)"; sed -n 116,154p src/48k/kea48.asm | grep -c "push"
echo "== m21_shots.py usage"; sed -n 1,25p tools/m21_shots.py
