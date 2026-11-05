#!/bin/bash
# m25_survey2.sh - read-only: memory map blocks, FOV/ray constants, slot math, ATTR_d, sprite projection constants
cd ~/work/killemall || exit 1
echo "== sym: block boundaries (sorted by address, selected labels)"
grep -E "^(BUF|ATTRBUF|DRAM|zbuf|ROWTAB|LOWBLK|low_start|low_end|hi_start|hi_end|spr_table|level_data|SPG|SCHAIN|CHJ|HTABN|HTABF|BANDTAB|BAND_2|BAND_96|BANDC_104|BANDC_128|TEX|TEX0|SQLO|SQHI|RECIP|SINTAB|COSTAB|PLXTAB|PLYTAB|STEPTAB|CLRBUF|COPYBUF|ATTRCOPY|FL_D4|SOLIDPG|CODEINK|ATTR_d|menu|fe_|beeper|tune|hud_|draw_things|main|start|render|frontend_start|sound_start|game_start|dash|sprites_lo|sprites_hi)[A-Za-z0-9_]*\s+EQU" build/kea48.sym | awk '{print $3, $1}' | sort | head -120
echo "== all labels count"; wc -l build/kea48.sym
echo "== low block org / size (kea48.asm org lines)"
grep -nE "^\s*org|ORG|include|INCLUDE" src/48k/kea48.asm | head -40
echo "== gen48.py: FOV / ray angle / PLX / column constants"
grep -nE "FOV|fov|NRAY|64|angle|PLX|PLY|HORIZ|48|96|128|SLOT|slot|mask" tools/gen48.py | head -70
echo "== kea48.asm: ray loop column/slot/attr (lines 560-760)"
sed -n 560,600p src/48k/kea48.asm
echo "..."; sed -n 655,700p src/48k/kea48.asm
echo "..."; sed -n 725,770p src/48k/kea48.asm