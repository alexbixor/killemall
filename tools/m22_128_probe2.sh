#!/bin/bash
# m22_128_probe2.sh - read-only: test_128 anchor expectations, bank-1 RAM use near 0x5D00, pasmo defs-with-fill support
cd ~/work/killemall
echo "== test_128.py anchor assertions"; grep -n "anchor\|A1\|A5\|diff\|assert" tools/test_128.py | head -30
echo "== 128K sources touching 0x5Dxx/0x5Exx or 23808.."; grep -n "0x5[DE]\|5[DE][0-9A-F][0-9A-F]h\|238[0-9][0-9]\|239[0-9][0-9]\|24[0-4][0-9][0-9]" src/128k/*.asm | head
echo "== bank1.asm org/labels"; grep -n "org\|^[a-zA-Z_]*:" src/128k/bank1.asm | head -12
echo "== pasmo defs fill test"; printf '        org 32768\nx:      defs 4,255\n        defs ((($+255) and 65280) - $)\ny:      defs 256,255\n        end\n' > /tmp/fill.asm && pasmo --bin /tmp/fill.asm /tmp/fill.bin /tmp/fill.sym && python3 -c "
b=open('/tmp/fill.bin','rb').read(); print('bin', len(b), 'first4', list(b[:4]), 'tail all FF:', all(v==255 for v in b[-256:]))"; cat /tmp/fill.sym
echo "== shim128.asm head"; sed -n 1,28p src/128k/shim128.asm
