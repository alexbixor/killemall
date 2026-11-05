#!/bin/bash
# M2.4 survey 5: can the low block grow downward (org 27904 -> lower)? who assumes 27904 / CLEAR 27903? (read-only)
cd ~/work/killemall || exit 1
echo "== 27904 / 27903 / 0x6D00 / 6D00 mentions"; grep -rnE "27904|27903|0x6D00|6D00|0x6B00|0x6A|TRAP" tools/*.py tools/*.sh src/48k/kea48.asm src/common/state.asm tools/gen48.py 2>/dev/null | grep -v "^tools/m2[0-9]_survey" | head -40
echo "== symbols in 0x6800..0x6CFF"; awk '{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); if (v>=0x6800 && v<0x6D00) print}' build/kea48.sym
echo "== symbols in 0x5B00..0x5CFF"; awk '{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); if (v>=0x5B00 && v<0x5D00) print}' build/kea48.sym
echo "== mktap48 BASIC loader"; grep -nE "CLEAR|clear|LOAD|USR|p1|start" tools/mktap48.py | head -20
echo "== make128"; grep -nE "27904|org|sprites48|include|CLEAR" tools/make128.py | head -20
echo "== test48 load_code"; grep -nE "def load_code|p1|27904|start" tools/test48.py | head -10
echo "== high block gaps >= 16 B between consecutive symbols (0xD000..0xFE00)"
.venv/bin/python - <<'EOF'
import re
sym={}
for l in open('build/kea48.sym'):
    m=re.match(r'(\S+)\s+EQU\s+0([0-9A-F]+)H',l)
    if m: sym[m.group(1)]=int(m.group(2),16)
inv={}
for k,v in sym.items(): inv.setdefault(v,[]).append(k)
addrs=sorted(a for a in inv if 0x8000<=a<0xFE00)
for a,b in zip(addrs,addrs[1:]):
    if b-a>=200: print(f'{a:04X} {inv[a]} -> {b:04X} {inv[b]}  {b-a} B')
EOF
echo "== fe_frame (unreferenced?)"; sed -n 44,60p src/common/frontend.asm; grep -rn "fe_frame" src | head
