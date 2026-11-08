#!/bin/bash
# m25_survey5.sh - read-only facts: FTX size, VISMAX clamp, ROM 0xFF page, exx/IX around CLRBUF, fe_quit, FAR_H, sysvars, spritec code-1
cd ~/work/killemall || exit 1
echo "== build_ftab full"; sed -n "$(grep -n '^build_ftab' src/48k/kea48.asm | cut -d: -f1),+45p" src/48k/kea48.asm | grep -nE "ld b,|push|ld sp|djnz|ret|FTX|FTY|defs|defw"
echo "== FTX/FTY/ftx_cache defs"; grep -nE "^(FTX|FTY|ftx_cache|fty_cache|SOLIDPG|FAR_H|ATTRBUF|BUF)\s" src/48k/kea48.asm
echo "== ROM 0x3800-0x3CFF all FF? (count of non-FF per page)"
.venv/bin/python - <<'EOF'
rom=open('tools/zesarux/48.rom','rb').read()
for p in range(0x38,0x3D):
    pg=rom[p*256:(p+1)*256]; print("page %02X non-FF %d"%(p,sum(1 for b in pg if b!=0xFF)))
EOF
echo "== VISMAX clamp"; grep -nE -B3 -A3 "VISMAX|nvis" src/common/sprites_b.asm src/common/sprites_c.asm | grep -E "cp|jr|ret|VISMAX|nvis" | head -20
echo "== exx / ix in render path (kea48.asm)"; grep -nE "\bexx\b|ixh|ixl|ld ix|push ix" src/48k/kea48.asm | head -30
echo "== fe_quit / BASIC return"; grep -nE -A6 "^fe_quit|^fe_exit0" src/common/frontend.asm | head -30; grep -nE -i "quit|ret to basic|0x1b7d|rst 8|ERR_SP|5C3D|23613" src/48k/kea48.asm src/common/*.asm | head
echo "== load_level"; sed -n "$(grep -n '^load_level' src/48k/kea48.asm | cut -d: -f1),+30p" src/48k/kea48.asm
echo "== spritec: run codes"; grep -nE "code|'o'|'#'|'\.'|run|def compile" tools/spritec.py | head -40
echo "== sprites_e.asm size/address math"; grep -nE "and 128|BUF/256|add a,BUF|rrca|and 7|and 3|SLOTM|zbuf|ROWTAB|inc e|ld h,|and 15|and 63" src/common/sprites_e.asm | head -40
echo "== sprites_f.asm address math"; grep -nE "and 128|BUF/256|add a,BUF|rrca|and 7|and 3|SLOTM|zbuf|ROWTAB|inc e|and 15|CHJ|ds_rmin|ds_rmax|ATTRBUF" src/common/sprites_f.asm | head -60
echo "== draw_weapon buf address"; grep -nE "BUF|128|inc e|ld de" src/common/hud_b.asm | head