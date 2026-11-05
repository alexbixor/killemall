#!/bin/bash
# m25_survey6.sh - read-only: calc_u squares idiom, side-dist table code, sprite projection centre, 128K sources, sizes
cd ~/work/killemall || exit 1
echo "== ray side-dist Y (kea48.asm 455-532)"; sed -n 455,532p src/48k/kea48.asm
echo "== calc_u squares idiom (740-830)"; sed -n 740,830p src/48k/kea48.asm
echo "== sprites_c.asm projection (centre column, lateral scale)"; sed -n 1,80p src/common/sprites_c.asm
echo "== constants 32/64/128 in game/sprite code"; grep -nE "\b(32|31|33|64|63|96)\b" src/common/game_*.asm src/common/sprites*.asm src/common/hud_b.asm | grep -vE "^\S+:\s*;|defb|32\*|\+32|sub 32|add a,32" | head -40
echo "== 128K sources"; ls src/128k/ 2>/dev/null; grep -nE "include" src/128k/*.asm 2>/dev/null | head -30
echo "== test_128 head"; sed -n 1,30p tools/test_128.py | grep -nE "^\"|build|tap|def |asm|sh" | head -20
echo "== sprite data sizes (bytes per spr_N run lists) from sym"
.venv/bin/python - <<'EOF'
import re
S={}
for l in open('build/kea48.sym'):
    m=re.match(r'(\w+)\s+EQU\s+([0-9A-F]+)H',l)
    if m: S[m.group(1)]=int(m.group(2),16)
tot=0
for i in range(14):
    a=S['spr_%d'%i]; b=S['spr_%d'%(i+1)] if i<13 else S['spr_14']
    print("spr_%d %d B"%(i,b-a)); tot+=b-a
print("ids 0..13 total",tot, "spr_14",S['spr_15']-S['spr_14'],"spr_15",S['SCHAIN']-S['spr_15'])
print("SCHAIN %d, draw_sprite..level_data %d, level_data..0x8000 %d"%(S['SCHAIN_END']-S['SCHAIN'], S['level_data']-S['draw_sprite'], 0x8000-S['level_data']))
print("DASH %d"%(S['spr_table']-S['DASH_RUNS']))
print("MOVX..RECIP %d, PLX..MOVX %d"%(S['RECIP']-S['MOVXTAB'], S['MOVXTAB']-S['PLXTAB']))
print("ATTR_0..ATTRCOPY %d, ATTRCOPY..COPYBUF %d, COPYBUF..BAND_2 %d"%(S['ATTRCOPY']-S['ATTR_0'], S['COPYBUF']-S['ATTRCOPY'], S['BAND_2']-S['COPYBUF']))
print("bands BAND_2..BANDC_104 %d, BANDC_104..SINTAB %d"%(S['BANDC_104']-S['BAND_2'], S['SINTAB']-S['BANDC_104']))
print("build_ftab..? ", S.get('bf_sp',0)-S['build_ftab'])
print("sprites_f ds_cols..hud_init %d"%(S['hud_init']-S['ds_cols']))
print("fl_set..HTABN padding: fl_end %04X HTABN %04X spare %d"%(S['fl_end'],S['HTABN'],S['HTABN']-S['fl_end']))
EOF
echo "== move_by / MOVXTAB users"; sed -n 215,260p src/48k/kea48.asm; sed -n 1,40p src/common/game_b.asm