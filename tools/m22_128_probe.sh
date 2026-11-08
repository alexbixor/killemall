#!/bin/bash
# m22_128_probe.sh - read-only: can the 128K edition take the M2.2 changes? (ROM 1 has no all-FF page -> SOLIDPG must be RAM there)
cd ~/work/killemall
echo "== 128.rom ROM1 (16384..32767) all-FF pages:"; python3 -c "
r=open('tools/zesarux/128.rom','rb').read()
for name,base in (('rom0',0),('rom1',16384)):
    rr=r[base:base+16384]
    print(name, [hex(p) for p in range(64) if rr[p*256:(p+1)*256]==b'\xff'*256])"
echo "== shim128 size / free below 49152 in the 128K image (last build symbols)"; ls -la build/kea128.sym 2>/dev/null && grep -E "^(hi_end|shim_end|SHIM_END|bank_init|load_level|snd_isr)\s" build/kea128.sym
echo "== shim128.asm tail (labels)"; grep -n "^[a-zA-Z_]*:" src/128k/shim128.asm | tail -8; wc -l src/128k/shim128.asm
echo "== 128K TEX / page tables"; grep -n "SOLIDPG\|TEXPG\|TEX\b" src/128k/*.asm | head
echo "== make128 remaining anchors"; sed -n 60,110p tools/make128.py
