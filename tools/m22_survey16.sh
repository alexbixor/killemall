#!/bin/bash
# m22_survey16.sh - read-only: vis entry layout + hv/c0/nc computation, ray loop texture-page / floor-ink selection, low block pads
cd ~/work/killemall
echo "== sprites_b 40-100 (draw_things: hv, c0, nc, vis entry)"; sed -n 40,100p src/common/sprites_b.asm
echo "== sprites_d 12-40 + 80-96 (entry fields)"; sed -n 12,40p src/common/sprites_d.asm; echo ...; sed -n 80,96p src/common/sprites_d.asm
echo "== sprites_e 1-40 (entry read, ds_hv)"; sed -n 1,40p src/common/sprites_e.asm
echo "== sprites_e 76-134 (columns / width)"; sed -n 76,134p src/common/sprites_e.asm
echo "== kea48 ray loop: texture page / band / ld e,5"; grep -n "TEXPG\|BANDTAB\|ld e,5\|ld d,1\|ATTR_\|hv\b" src/48k/kea48.asm | head -30
echo "== gen48 low-block layout: org/align/defs/pad"; grep -n "org\|align\|defs\|pad\|% 256\|& 255\|SPG\|CHJ\|NCTAB\|STEPTAB\|VSTEP\|sprites48" tools/gen48.py | head -40
echo "== low block symbols tail"; python3 - <<'EOF'
import re
syms=[]
for l in open('build/kea48.sym'):
    m=re.match(r'(\S+)\s+EQU\s+([0-9A-F]+)H',l)
    if m: syms.append((int(m.group(2),16),m.group(1)))
syms.sort()
lo=[s for s in syms if 0x6D00<=s[0]<0x8000]
for a,n in lo[:12]: print(hex(a),n)
print('...')
for a,n in lo[-6:]: print(hex(a),n)
EOF
echo "== sprites48.asm head/tail"; head -5 src/48k/gen/sprites48.asm; echo ...; tail -5 src/48k/gen/sprites48.asm; grep -n "org\|align\|defs" src/48k/gen/sprites48.asm | head
