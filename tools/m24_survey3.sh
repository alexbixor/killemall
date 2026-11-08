#!/bin/bash
# M2.4 survey 3: exact byte budget (run-list sizes per sprite, clip band sizes, paddings) - read-only
cd ~/work/killemall || exit 1
S=build/kea48.sym
echo "== sprite run-list sizes (symbol deltas)"
.venv/bin/python - <<'EOF'
import re
sym={}
for l in open('build/kea48.sym'):
    m=re.match(r'(\S+)\s+EQU\s+0([0-9A-F]+)H',l)
    if m: sym[m.group(1)]=int(m.group(2),16)
addrs=sorted(set(sym.values()))
def size(n):
    a=sym[n]; nxt=[x for x in addrs if x>a]; return nxt[0]-a
tot=0
for i in range(18):
    s=size(f'spr_{i}'); tot+=s; print(f'spr_{i:<3} {sym[f"spr_{i}"]:04X} {s:4d} B')
print('total run data', tot, 'spr_table', size('spr_table'))
for n in ['SPG','CHJ','NCTAB','STEPTAB','VSTEP','spr_table','SCHAIN','SCHAIN_END','level_data','start','SQLO','SQHI','RECIP','fl_set','FL_D4','fl_end','HTABN','HTABF','BANDTAB','SLOTM','TEX','hi_end','BUF','ATTRBUF','ATTRWIN','ROWTAB','ds_rmin','zbuf','SOLIDPG']:
    if n in sym: print(f'{n:12} {sym[n]:04X}')
# band routines: labels BND* / clip
bands=[(k,v) for k,v in sym.items() if re.match(r'(BND|bnd|band|B[0-9]|clip|CLIP)',k)]
bands.sort(key=lambda kv:kv[1])
print('band-ish labels', len(bands)); print(bands[:6], bands[-8:])
EOF
echo "== gen48: clip bands + HTAB quantisation"; grep -nE "CLIPSET|clip|def band|def htab|HTABN|HTABF|def bandtab|heights" tools/gen48.py | head -30
echo "== dash_data size"; grep -cE "defb|defw" src/common/dash_data.asm; head -3 src/common/dash_data.asm
echo "== weapon draw uses"; grep -nE "spr_table|ds_spr|run|u0|CHJ|dc_" src/common/hud_b.asm | head -12
echo "== stack margin tool"; .venv/bin/python tools/m22_stack.py 2>&1 | tail -3
