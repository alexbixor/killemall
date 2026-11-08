#!/bin/bash
# m25_survey3.sh - read-only: full sym map gaps, DRAM layout, ray setup (rdx/rdy per column), ATTR_d, CLRBUF/COPYBUF code
cd ~/work/killemall || exit 1
echo "== sym gaps >= 48 B between consecutive labels (addr label gap_to_next)"
.venv/bin/python - <<'EOF'
import re
syms=[]
for l in open('build/kea48.sym'):
    m=re.match(r'(\w+)\s+EQU\s+([0-9A-F]+)H',l)
    if m: syms.append((int(m.group(2),16),m.group(1)))
syms=sorted(set(syms))
syms=[s for s in syms if 0x5C00<=s[0]<=0x10000]
for i,(a,n) in enumerate(syms[:-1]):
    gap=syms[i+1][0]-a
    if gap>=48: print("%04X %-22s %5d -> %s"%(a,n,gap,syms[i+1][1]))
print("last", "%04X %s"%syms[-1])
EOF
echo "== state.asm (DRAM)"; cat src/common/state.asm
echo "== ray loop head: per-column direction (kea48.asm 440-560)"; sed -n 436,470p src/48k/kea48.asm
echo "..."; grep -nE "rdx|rdy|plane|camx|CAMTAB|RAYTAB|col_loop|ray_col|64|ld b,64|ld a,64" src/48k/kea48.asm | head -40
echo "== ATTRTAB / ATTR_d"; grep -nE "ATTRTAB|ATTR_[0-9d]" src/48k/kea48.asm | head; sed -n "$(grep -n '^ATTRTAB' src/48k/kea48.asm | cut -d: -f1),+40p" src/48k/kea48.asm
echo "== CLRBUF/COPYBUF generated"; grep -nE -A30 "^CLRBUF" src/48k/gen/unrolled48.asm | head -60
echo "== IM2 / ISR / stack top"; grep -nE -i "im 2|0xfe|65024|65008|ld sp|ISR|isr|vector|ticks" src/48k/kea48.asm | head -20